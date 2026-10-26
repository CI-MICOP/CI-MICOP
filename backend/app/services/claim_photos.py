"""The photos the evidence photo checks read, from both places they are
stored.

Surveyors upload photos as `evidence` rows (services/evidence_upload.py);
customers take accident photos with the portal camera and they are stored
as "Accident Photos" `documents` rows (services/document_upload.py). The
duplicate and quality checks (evidence_duplication / evidence_quality)
read both, and every photo keeps a label saying where it came from - a
customer photo is never relabelled as surveyor evidence or the reverse.

Nothing here compares WHAT two photos show (same vehicle, same damage):
that would need an image-recognition model, which this application does
not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.crud import evidence as crud_evidence
from app.db_models.document import Document
from app.db_models.evidence import Evidence
from app.services import document_storage, evidence_storage

CUSTOMER_ACCIDENT_PHOTO_TYPE = "Accident Photos"
CUSTOMER_PHOTO_LABEL = "Accident Photo (customer upload)"
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


@dataclass
class ClaimPhoto:
    # Same attribute names as Evidence, so the checks treat both alike.
    Evidence_ID: str
    Claim_ID: str
    Evidence_Type: str
    File_Name: str
    path: Path | None


def _stored_path(storage, claim_id: str, item_id: str, file_name: str) -> Path | None:
    try:
        return storage.storage_path_for(claim_id, item_id, file_name)
    except ValueError:
        return None


def from_evidence(evidence: Evidence) -> ClaimPhoto:
    """A surveyor (or other evidence-table) photo; its Evidence_Type is kept."""
    return ClaimPhoto(
        Evidence_ID=evidence.Evidence_ID, Claim_ID=evidence.Claim_ID, Evidence_Type=evidence.Evidence_Type,
        File_Name=evidence.File_Name,
        path=_stored_path(evidence_storage, evidence.Claim_ID, evidence.Evidence_ID, evidence.File_Name),
    )


def from_customer_document(document: Document) -> ClaimPhoto:
    return ClaimPhoto(
        Evidence_ID=document.Document_ID, Claim_ID=document.Claim_ID, Evidence_Type=CUSTOMER_PHOTO_LABEL,
        File_Name=document.Document_Name,
        path=_stored_path(document_storage, document.Claim_ID, document.Document_ID, document.Document_Name),
    )


def _is_customer_photo(document: Document) -> bool:
    return document.Document_Type == CUSTOMER_ACCIDENT_PHOTO_TYPE and document.Document_Name.lower().endswith(
        _IMAGE_EXTENSIONS
    )


def claim_photos(db: Session, claim_id: str) -> list[ClaimPhoto]:
    """This claim's surveyor evidence photos, then its customer accident photos."""
    customer = [d for d in crud_document.list_by_claim(db, claim_id) if _is_customer_photo(d)]
    return [from_evidence(e) for e in crud_evidence.list_by_claim(db, claim_id)] + [
        from_customer_document(d) for d in customer
    ]


def all_photos(db: Session) -> list[ClaimPhoto]:
    customer = [d for d in crud_document.list_by_type(db, CUSTOMER_ACCIDENT_PHOTO_TYPE) if _is_customer_photo(d)]
    return [from_evidence(e) for e in crud_evidence.list_all(db)] + [from_customer_document(d) for d in customer]


def read_bytes(photo: ClaimPhoto) -> bytes | None:
    """None when the stored file is missing, unreadable or empty."""
    if photo.path is None:
        return None
    try:
        content = photo.path.read_bytes()
    except OSError:
        return None
    return content or None
