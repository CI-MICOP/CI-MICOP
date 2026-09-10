"""Business logic for the surveyor evidence-upload endpoint.

Mirrors services/document_upload.py's pattern (ownership check,
allow-listed type validation, magic-byte content validation, ID
generation, and the file+database transaction) for a surveyor's own
claim-evidence file uploads. See
docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import evidence as crud_evidence
from app.db_models.evidence import Evidence
from app.services import evidence_storage
from app.services.claim_access import get_claim_assigned_to_surveyor_or_403

# Real values observed in the approved dataset
# (ai_ml/datasets/CI_MICOP_15_Tables_Complete/10_evidence.xlsx, 1301 rows).
EVIDENCE_TYPE_VALUES = {"Survey Photo", "Damage Photo", "Accident Photo"}
EVIDENCE_SOURCE_VALUES = {"Customer", "Surveyor"}

# Evidence here is photographic - PDF/document-style evidence is already
# handled by the separate Customer Document Upload workflow. Content is
# sniffed from the actual bytes, never trusted from the browser-supplied
# MIME type.
_ALLOWED_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


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
            detail="Unsupported file type. Allowed extensions: .jpg, .jpeg, .png",
        )
    return ext


def _validate_signature(ext: str, content: bytes) -> None:
    signatures = _ALLOWED_SIGNATURES[ext]
    if not any(content.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file's content does not match its extension.",
        )


async def upload_evidence_for_surveyor(
    db: Session,
    employee_id: str,
    claim_id: str,
    evidence_type: str,
    evidence_date: date,
    evidence_source: str,
    upload_file: UploadFile,
) -> Evidence:
    get_claim_assigned_to_surveyor_or_403(db, claim_id, employee_id)

    if evidence_type not in EVIDENCE_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported evidence_type. Allowed values: {sorted(EVIDENCE_TYPE_VALUES)}",
        )
    if evidence_source not in EVIDENCE_SOURCE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported evidence_source. Allowed values: {sorted(EVIDENCE_SOURCE_VALUES)}",
        )

    ext = _validate_extension(upload_file.filename or "")
    content = await _read_limited(upload_file, settings.EVIDENCE_MAX_UPLOAD_BYTES)
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    _validate_signature(ext, content)

    evidence_id = crud_evidence.generate_evidence_id(db)
    stored_path = evidence_storage.storage_path_for(claim_id, evidence_id, upload_file.filename or "upload")

    evidence = Evidence(
        Evidence_ID=evidence_id,
        Claim_ID=claim_id,
        Evidence_Type=evidence_type,
        File_Name=(upload_file.filename or "upload")[:255],
        Evidence_Date=evidence_date,
        Evidence_Source=evidence_source,
        # No OCR/image-analysis process has run yet - these are honest
        # "not yet analyzed" placeholders, never fabricated AI output.
        # Image_Quality/Evidence_Confidence_Score = 0 (not a real score);
        # Damage_Severity = "Pending" (the dataset's own vocabulary has no
        # neutral value here - see schemas/surveyor.py's PENDING sentinel
        # for the same convention already used for inspections); the
        # boolean flags default to False ("not flagged", not "verified").
        Image_Quality=Decimal("0.0000"),
        Vehicle_Damage_Detected=False,
        Damage_Severity="Pending",
        Location_Match=False,
        Duplicate_Evidence_Indicator=False,
        Evidence_Confidence_Score=Decimal("0.0000"),
        Verification_Status="Pending",
    )

    try:
        evidence_storage.save_file(stored_path, content)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The file could not be stored. No evidence record was saved.",
        ) from exc

    try:
        crud_evidence.create(db, evidence)
        db.commit()
    except Exception as exc:
        db.rollback()
        evidence_storage.delete_file(stored_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The evidence could not be saved. No file was retained.",
        ) from exc

    db.refresh(evidence)
    return evidence
