"""Business logic for the customer document-upload endpoint.

Mirrors the existing services/claim_creation.py pattern: the router stays
a thin HTTP wrapper, and the actual rules - ownership checks, allow-listed
document types, file validation, ID generation, and the file/database
transaction - live here in one place. See
docs/project_documentation/CUSTOMER_DOCUMENT_UPLOAD.md for the full
rationale.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import claim as crud_claim
from app.crud import document as crud_document
from app.db_models.claim import Claim
from app.db_models.document import Document
from app.services import document_storage

# Maps the frontend's existing DOCUMENT_CATEGORIES keys (see
# frontend/src/components/customer/documentCategories.js) to the
# Document_Type value stored in the database. Kept here as the single
# source of truth rather than trusting an arbitrary client-supplied
# string - this is a controlled allow-list, not free text.
ALLOWED_DOCUMENT_TYPES: dict[str, str] = {
    "fir_copy": "FIR",
    "driving_licence": "Driving Licence",
    "rc_book": "RC",
    "insurance_policy": "Insurance Policy",
    "repair_estimate": "Repair Estimate",
    "accident_photos": "Accident Photos",
    "survey_report": "Survey Report",
}

# Extension -> acceptable magic-byte signatures. Content is sniffed from
# the actual bytes, never trusted from the browser-supplied MIME type.
_ALLOWED_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


def _get_owned_claim(db: Session, customer_id: str, claim_id: str) -> Claim:
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    if claim.Customer_ID != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only upload documents to your own claim",
        )
    return claim


async def _read_limited(upload_file: UploadFile, max_bytes: int) -> bytes:
    """Reads in bounded chunks so an oversized upload is rejected without
    first buffering the whole thing into memory."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload_file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds the maximum allowed size of {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_extension(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in _ALLOWED_SIGNATURES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed extensions: .pdf, .jpg, .jpeg, .png",
        )
    return ext


def _validate_signature(ext: str, content: bytes) -> None:
    signatures = _ALLOWED_SIGNATURES[ext]
    if not any(content.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file's content does not match its extension.",
        )


async def upload_document_for_customer(
    db: Session,
    customer_id: str,
    claim_id: str,
    document_type: str,
    upload_file: UploadFile,
) -> Document:
    # 1-2. Authentication is enforced by the router's dependency; ownership here.
    _get_owned_claim(db, customer_id, claim_id)

    # 3. Document type.
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported document_type. Allowed values: {sorted(ALLOWED_DOCUMENT_TYPES)}",
        )
    document_type_label = ALLOWED_DOCUMENT_TYPES[document_type]

    # 4. File validation: extension, then bounded read, then emptiness, then signature.
    ext = _validate_extension(upload_file.filename or "")
    content = await _read_limited(upload_file, settings.DOCUMENT_MAX_UPLOAD_BYTES)
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    _validate_signature(ext, content)

    # 5-6. Generate Document_ID and a safe, server-controlled storage path.
    document_id = crud_document.generate_document_id(db)
    stored_path = document_storage.storage_path_for(claim_id, document_id, upload_file.filename or "upload")

    document = Document(
        Document_ID=document_id,
        Claim_ID=claim_id,
        Document_Type=document_type_label,
        Document_Name=(upload_file.filename or "upload")[:255],
        Document_Submitted_Date=date.today(),
        Document_Status="Submitted",
        # No OCR/consistency/verification process has run yet - these are
        # safe "nothing has happened" defaults, never fabricated results.
        OCR_Confidence_Score=Decimal("0.0000"),
        Extracted_Text="",
        Document_Completeness=Decimal("0.0000"),
        Document_Mismatch_Indicator=False,
        Verification_Status="Pending",
    )

    # 7. Save the physical file first...
    try:
        document_storage.save_file(stored_path, content)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The file could not be stored. No document was saved.",
        ) from exc

    # 8-9. ...then the metadata row, in one transaction. If the database
    # write fails, the file just written must not be left orphaned.
    try:
        crud_document.create(db, document)
        db.commit()
    except Exception as exc:
        db.rollback()
        document_storage.delete_file(stored_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved. No file was retained.",
        ) from exc

    db.refresh(document)
    return document
