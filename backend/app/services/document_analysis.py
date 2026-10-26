"""Step 5.8.12: document completeness + OCR pipeline.

Two clearly separated responsibilities (see
docs/project_documentation/DOCUMENT_COMPLETENESS_AND_OCR.md):

  A. OCR / text extraction - a genuine evidence-extraction utility
     (extract_document_text and friends). Uses PyMuPDF for native PDF
     text/rasterization and pytesseract (Tesseract) for OCR on images and
     scanned PDF pages.
  B. Deterministic document completeness - a static, rule-based
     calculation (get_required_document_types /
     calculate_claim_document_completeness), not machine learning.

Neither makes, nor feeds into, a claim decision. This module has no
access to Claim.Final_Decision/Approved_Amount and never touches them.

Tesseract itself is a separate system-level executable - installing the
`pytesseract` Python package does NOT install it. Every OCR call here is
guarded so a machine without Tesseract degrades to an honest "unavailable"
result instead of crashing (see docs, Section 7/14).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import document as crud_document
from app.db_models.claim import Claim
from app.db_models.document import Document
from app.services import claim_copy_retention, document_storage

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
PDF_EXTENSION = ".pdf"

# A page's own embedded text must be at least this long before it is
# trusted as "real" text rather than a stray watermark/page-number that
# should still be treated as a scanned page needing OCR.
_MIN_NATIVE_TEXT_CHARS = 10

# Text pulled from a PDF's own embedded text layer is the exact source
# text, not a probabilistic OCR guess - 1.0 states "not inferred", it is
# not a fabricated OCR confidence score.
_NATIVE_TEXT_CONFIDENCE = 1.0


@dataclass
class ExtractionResult:
    text: str
    confidence: float  # genuine 0.0-1.0, or an honest 0.0
    # extracted_native | extracted_ocr | extracted_ocr_no_confidence | partial | empty | unavailable,
    # or copy_not_retained (analyze_document, for a copy that is not kept - see claim_copy_retention)
    status: str
    limitations: list[str]


@dataclass
class _PageExtraction:
    text: str
    confidence: float | None  # None = nothing usable/scoreable extracted from this page
    method: str  # native | ocr | unavailable


@dataclass
class CompletenessResult:
    available: bool
    required: list[str]
    present: list[str]
    missing: list[str]
    ratio: float | None
    explanation: str


# ---------------------------------------------------------------------------
# Safe file resolution (reuses the existing storage abstraction - never
# reconstructs a path independently)
# ---------------------------------------------------------------------------


def resolve_document_path(document: Document) -> Path:
    """Re-derives this document's expected physical path via the same
    storage_path_for() used at upload time (services/document_storage.py) -
    including its own root-escape check. Never accepts a client-supplied
    path."""
    return document_storage.storage_path_for(document.Claim_ID, document.Document_ID, document.Document_Name)


# ---------------------------------------------------------------------------
# A. OCR / text extraction
# ---------------------------------------------------------------------------


def _tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def calculate_ocr_confidence(raw_confidences: list) -> float | None:
    """Tesseract reports -1 for boxes with no valid confidence (page/
    block/paragraph/line-level rows, not actual recognized words) - those
    must never be averaged in as if they were real values. Returns None,
    never a fabricated number, if nothing valid remains."""
    valid = []
    for raw in raw_confidences:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            valid.append(value)
    if not valid:
        return None
    return (sum(valid) / len(valid)) / 100.0


def extract_text_from_image(path: Path) -> ExtractionResult:
    if not _tesseract_available():
        return ExtractionResult(
            text="", confidence=0.0, status="unavailable",
            limitations=["Tesseract OCR engine is not installed/available on this server."],
        )
    try:
        with Image.open(path) as raw_image:
            # Minimal, deterministic preprocessing only - grayscale
            # conversion, no speculative computer-vision pipeline.
            image = raw_image.convert("L")
            text = pytesseract.image_to_string(image).strip()
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception as exc:
        return ExtractionResult(
            text="", confidence=0.0, status="unavailable",
            limitations=[f"OCR failed to process this image ({exc.__class__.__name__})."],
        )

    confidence = calculate_ocr_confidence(data.get("conf", []))
    if confidence is None:
        status = "extracted_ocr_no_confidence" if text else "empty"
        limitation = (
            "OCR extracted text but no valid confidence values were returned."
            if text
            else "OCR produced no recognizable text."
        )
        return ExtractionResult(text=text, confidence=0.0, status=status, limitations=[limitation])

    return ExtractionResult(
        text=text, confidence=confidence, status="extracted_ocr" if text else "empty", limitations=[]
    )


def _rasterize_pdf_page(page: "fitz.Page") -> Image.Image:
    pixmap = page.get_pixmap(dpi=200)
    mode = "RGBA" if pixmap.alpha else "RGB"
    image = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
    return image.convert("L")


def _extract_pdf_page(page: "fitz.Page") -> _PageExtraction:
    native_text = (page.get_text() or "").strip()
    if len(native_text) >= _MIN_NATIVE_TEXT_CHARS:
        return _PageExtraction(text=native_text, confidence=_NATIVE_TEXT_CONFIDENCE, method="native")

    if not _tesseract_available():
        # Preserve whatever short native text exists rather than discarding it.
        return _PageExtraction(text=native_text, confidence=None, method="unavailable")

    try:
        image = _rasterize_pdf_page(page)
        ocr_text = pytesseract.image_to_string(image).strip()
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception:
        return _PageExtraction(text=native_text, confidence=None, method="unavailable")

    confidence = calculate_ocr_confidence(data.get("conf", []))
    combined_text = ocr_text or native_text
    if confidence is None:
        return _PageExtraction(text=combined_text, confidence=None, method="unavailable")
    return _PageExtraction(text=ocr_text, confidence=confidence, method="ocr")


def extract_text_from_pdf(path: Path) -> ExtractionResult:
    try:
        pdf = fitz.open(path)
    except Exception as exc:
        return ExtractionResult(
            text="", confidence=0.0, status="unavailable",
            limitations=[f"The PDF could not be opened ({exc.__class__.__name__})."],
        )

    try:
        if pdf.is_encrypted:
            return ExtractionResult(
                text="", confidence=0.0, status="unavailable",
                limitations=["This PDF is password-protected and cannot be read."],
            )
        if pdf.page_count == 0:
            return ExtractionResult(text="", confidence=0.0, status="empty", limitations=["This PDF has no pages."])

        pages: list[_PageExtraction] = []
        limitations: list[str] = []
        for index in range(pdf.page_count):
            try:
                pages.append(_extract_pdf_page(pdf[index]))
            except Exception:
                pages.append(_PageExtraction(text="", confidence=None, method="unavailable"))
                limitations.append(f"Page {index + 1} could not be processed.")
    finally:
        pdf.close()

    text = "\n".join(page.text for page in pages if page.text).strip()
    scored = [page.confidence for page in pages if page.confidence is not None]

    ocr_missing = any(page.method == "unavailable" for page in pages) and not _tesseract_available()
    if ocr_missing:
        limitations.append(
            "Tesseract OCR engine is not installed/available on this server - "
            "scanned/image pages could not be processed."
        )

    if not scored:
        # A scanned PDF that could not be OCR'd is "unavailable", not "empty":
        # "empty" tells the reader the document has no text, which is only
        # known when OCR actually ran (same as extract_text_from_image).
        status = "unavailable" if text or ocr_missing else "empty"
        if not text and not limitations:
            limitations.append("No page produced extractable text.")
        return ExtractionResult(text=text, confidence=0.0, status=status, limitations=limitations)

    confidence = sum(scored) / len(scored)
    if len(scored) < len(pages):
        limitations.append(f"{len(pages) - len(scored)} of {len(pages)} page(s) could not be analyzed.")
        status = "partial"
    else:
        status = "extracted_native" if all(page.method == "native" for page in pages) else "extracted_ocr"
    return ExtractionResult(text=text, confidence=confidence, status=status, limitations=limitations)


def extract_document_text(path: Path) -> ExtractionResult:
    ext = path.suffix.lower()
    if ext == PDF_EXTENSION:
        return extract_text_from_pdf(path)
    if ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(path)
    return ExtractionResult(
        text="", confidence=0.0, status="unavailable",
        limitations=[f"Unsupported file type for analysis: {ext or 'unknown'}."],
    )


def extract_document_bytes(content: bytes, extension: str) -> ExtractionResult:
    """Extracts text from an upload that must not be stored (see
    services/claim_copy_retention.py). PyMuPDF and Pillow are given a file
    path, so the bytes are written to a private temporary directory that is
    removed when this returns - normally or by an exception. Nothing is
    written to DOCUMENT_STORAGE_ROOT. (pytesseract also writes and deletes
    its own short-lived temporary images while OCR runs.)"""
    with tempfile.TemporaryDirectory(prefix="ci-micop-copy-") as directory:
        path = Path(directory) / f"copy{extension.lower()}"
        path.write_bytes(content)
        return extract_document_text(path)


# ---------------------------------------------------------------------------
# B. Deterministic document completeness (rule-based, not ML)
# ---------------------------------------------------------------------------

# Document_Type values exactly as stored by the live upload endpoint - see
# ALLOWED_DOCUMENT_TYPES in services/document_upload.py. This mapping is
# built only from those existing labels, never invented ones.
_BASE_REQUIRED_DOCUMENT_TYPES = frozenset({"Driving Licence", "RC", "Insurance Policy"})

# ASSUMPTION - no existing business rule in this repository defines
# per-claim-type required documents, so this is a documented, conservative
# design choice (see docs/project_documentation/DOCUMENT_COMPLETENESS_AND_OCR.md,
# Section 10), not a discovered fact:
#   - every claim needs proof of driver/vehicle/policy identity (the base set)
#   - "Own Damage" additionally needs evidence of the damage/repair cost
#   - "Third Party" and "Theft" additionally need a police FIR, since both
#     involve an external party or a criminal act
# Claim types are exactly CLAIM_TYPES from frontend/src/pages/customer/NewClaimPage.jsx.
REQUIRED_DOCUMENT_TYPES_BY_CLAIM_TYPE: dict[str, frozenset[str]] = {
    "Own Damage": _BASE_REQUIRED_DOCUMENT_TYPES | {"Repair Estimate", "Accident Photos"},
    "Third Party": _BASE_REQUIRED_DOCUMENT_TYPES | {"FIR", "Accident Photos"},
    "Theft": _BASE_REQUIRED_DOCUMENT_TYPES | {"FIR"},
}


def get_required_document_types(claim_type: str) -> frozenset[str]:
    """Any claim type not explicitly covered above falls back to the
    conservative base set rather than guessing at a business rule."""
    return REQUIRED_DOCUMENT_TYPES_BY_CLAIM_TYPE.get(claim_type, _BASE_REQUIRED_DOCUMENT_TYPES)


def calculate_claim_document_completeness(claim_type: str, documents: list[Document]) -> CompletenessResult:
    required = get_required_document_types(claim_type)

    if not documents:
        # Zero documents is NOT the same as "0% complete" - there is no
        # analyzable document set at all yet (Phase 10).
        return CompletenessResult(
            available=False,
            required=sorted(required),
            present=[],
            missing=sorted(required),
            ratio=None,
            explanation="No documents have been uploaded for this claim yet - completeness cannot be assessed.",
        )

    present_types = {doc.Document_Type for doc in documents}
    present_required = required & present_types
    missing_required = required - present_types
    ratio = (len(present_required) / len(required)) if required else 1.0

    return CompletenessResult(
        available=True,
        required=sorted(required),
        present=sorted(present_required),
        missing=sorted(missing_required),
        ratio=ratio,
        explanation=(
            f"{len(present_required)} of {len(required)} required document type(s) are present "
            f"for this '{claim_type}' claim."
        ),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def analyze_document(db: Session, document: Document) -> ExtractionResult:
    """Runs OCR/native-text extraction for ONE document and persists the
    genuinely extracted result. Does not touch Document_Completeness -
    that is a claim-wide fact (see analyze_claim_documents), not a side
    effect of analyzing a single document in isolation. Never touches
    Document_Status/Verification_Status - those reflect the human
    submission/verification workflow, not the automated OCR step."""
    if not claim_copy_retention.is_copy_retained(document.Document_Type):
        return _analyze_unretained_copy(db, document)
    path = resolve_document_path(document)
    if not path.exists():
        result = ExtractionResult(
            text="", confidence=0.0, status="unavailable",
            limitations=["The stored file for this document could not be found."],
        )
    else:
        result = extract_document_text(path)

    crud_document.update_analysis_fields(
        db,
        document,
        Extracted_Text=result.text,
        OCR_Confidence_Score=Decimal(str(round(result.confidence, 4))),
    )
    db.commit()
    db.refresh(document)
    return result


_COPY_NOT_RETAINED_NOTE = (
    "This copy was read when it was uploaded and is not kept, so it cannot be read again. "
    "Only the registration / policy-number details found in it were saved, and they are shown here."
)


def _analyze_unretained_copy(db: Session, document: Document) -> ExtractionResult:
    """RC / licence / policy copy: never re-reads or overwrites what was kept
    at upload. A file stored before copies stopped being kept is still read,
    and only its verification record is saved from it."""
    path = resolve_document_path(document)
    if path.exists():
        result = extract_document_text(path)
        record = claim_copy_retention.verification_record(result.text)
        crud_document.update_analysis_fields(
            db, document, Extracted_Text=record, OCR_Confidence_Score=Decimal(str(round(result.confidence, 4)))
        )
        db.commit()
        db.refresh(document)
        return ExtractionResult(
            text=record, confidence=result.confidence, status=result.status,
            limitations=result.limitations + [
                "This copy was stored before copies stopped being kept; only its registration / "
                "policy-number details were saved from it."
            ],
        )
    limitations = [_COPY_NOT_RETAINED_NOTE]
    if not document.Extracted_Text:
        limitations.append(
            "No registration or policy number was found when it was uploaded, or its text could not be read then."
        )
    return ExtractionResult(
        text=document.Extracted_Text or "",
        confidence=float(document.OCR_Confidence_Score or 0),
        status="copy_not_retained",
        limitations=limitations,
    )


def analyze_claim_documents(db: Session, claim: Claim) -> tuple[list[Document], list[ExtractionResult], CompletenessResult]:
    """Officer/Admin batch entry point: OCR every document currently on
    the claim, then persist ONE claim-level completeness ratio onto every
    one of that claim's Document rows - the schema has no claim-level
    completeness column (see Section 9 of the docs), so this is the
    documented, chosen way to represent it without a migration."""
    documents = crud_document.list_by_claim(db, claim.Claim_ID)
    results = [analyze_document(db, document) for document in documents]

    completeness = calculate_claim_document_completeness(claim.Claim_Type, documents)
    if completeness.available:
        value = Decimal(str(round(completeness.ratio, 4)))
        for document in documents:
            crud_document.update_analysis_fields(db, document, Document_Completeness=value)
        db.commit()

    return documents, results, completeness
