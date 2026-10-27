"""Read-only access for the assigned surveyor to a claim's customer
documents (Claim Details -> Claim Documents).

Security boundary - checked on every request, independently, from the
JWT and the database (nothing the browser sends is trusted):
  1. authenticated, with the Surveyor role (the router's dependency);
  2. the claim exists and is assigned to this surveyor - otherwise 404,
     the same answer for "no such claim" and "not yours", so another
     customer's claim is not disclosed;
  3. the surveyor's inspection has reached its scheduled date
     (surveyor_workflow.schedule_reached, 00:00 IST on Inspection_Date);
  4. the document belongs to that claim and is a type surveyors may view -
     customer accident photos never are (they are customer evidence, kept
     apart from surveyor-captured evidence);
  5. the stored file is re-derived from the server-side row
     (document_storage.storage_path_for, which refuses paths outside the
     storage root) and served only if its bytes are a PDF, JPEG or PNG.

Viewing is repeatable: there is no view count or one-time link, so the
surveyor can reopen a document as often as needed while the checks above
pass - and as soon as one fails (assignment removed, role changed), the
next request is refused. Viewing never writes anything: documents,
evidence, inspection status and workflow progress are unchanged. Each
successful view is recorded in the application log (surveyor, claim,
document, time - never the content).

RC, driving-licence and policy copies are not stored at all
(services/claim_copy_retention.py), so they are listed with their
verification status but have no file to open.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import claim as crud_claim
from app.crud import document as crud_document
from app.crud import surveyor_inspection as crud_inspection
from app.services import claim_copy_retention, document_storage, surveyor_workflow
from app.services.claim_photos import CUSTOMER_ACCIDENT_PHOTO_TYPE

audit_log = logging.getLogger("ci_micop.audit.document_access")

# Always listed in the panel, so a missing one shows as "Not uploaded".
EXPECTED_DOCUMENT_TYPES = ("RC", "Driving Licence", "Insurance Policy", "FIR", "Repair Estimate")
# Never shown to surveyors through this panel (or anywhere else).
HIDDEN_DOCUMENT_TYPES = frozenset({CUSTOMER_ACCIDENT_PHOTO_TYPE})

# Served inline only when the stored bytes are one of these.
_PREVIEWABLE = ((b"%PDF-", "application/pdf"), (b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))

AVAILABLE = "available"
NOT_UPLOADED = "not_uploaded"
NOT_RETAINED = "not_retained"
UNAVAILABLE = "unavailable"
UNSUPPORTED = "unsupported"


def _not_found(detail: str = "Claim not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def documents_locked_message(inspection) -> str:
    date = surveyor_workflow._long_date(inspection.Inspection_Date)
    return f"Customer documents become available on the scheduled inspection date, {date} (India Standard Time)."


def authorize(db: Session, claim_id: str, employee_id: str, now: datetime | None = None):
    """The claim and the surveyor's inspection, if this surveyor may view the
    claim's documents now. Raises 404 (not assigned / no such claim) or 409
    (before the scheduled date)."""
    claim = crud_claim.get(db, claim_id)
    if claim is None or not crud_claim.surveyor_is_assigned(db, claim_id, employee_id):
        raise _not_found()
    inspection = surveyor_workflow.own_inspection(crud_inspection.list_by_claim(db, claim_id), employee_id)
    if inspection is None:
        raise _not_found()
    if not surveyor_workflow.schedule_reached(inspection, now):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=documents_locked_message(inspection))
    return claim, inspection


def _stored_file(document) -> tuple[Path | None, str | None]:
    """(path, media type) of the document's stored file, or (None, reason)."""
    if not claim_copy_retention.is_copy_retained(document.Document_Type):
        return None, NOT_RETAINED
    try:
        path = document_storage.storage_path_for(document.Claim_ID, document.Document_ID, document.Document_Name)
    except ValueError:
        return None, UNAVAILABLE
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return None, UNAVAILABLE
    media_type = next((media for magic, media in _PREVIEWABLE if head.startswith(magic)), None)
    return (path, media_type) if media_type else (None, UNSUPPORTED)


def _verification(document) -> str:
    # Reported as recorded; existing or being opened never makes a document "Verified".
    return document.Verification_Status or "Pending"


def _entry(document) -> dict:
    path, media_or_reason = _stored_file(document)
    return {
        "document_id": document.Document_ID,
        "document_type": document.Document_Type,
        "submitted_date": document.Document_Submitted_Date,
        "availability": AVAILABLE if path else media_or_reason,
        "media_type": media_or_reason if path else None,
        "verification_status": _verification(document),
    }


def list_claim_documents(db: Session, claim_id: str, employee_id: str) -> dict:
    """The Claim Documents panel: every expected type (marked "not_uploaded"
    when absent) plus any other visible document on the claim."""
    authorize(db, claim_id, employee_id)
    documents = [
        d
        for d in crud_document.list_by_claim(db, claim_id)
        # The claim check is repeated here so a row of another claim can never be listed.
        if d.Claim_ID == claim_id and d.Document_Type not in HIDDEN_DOCUMENT_TYPES
    ]
    entries = [_entry(d) for d in documents]
    present = {d.Document_Type for d in documents}
    missing = [
        {
            "document_id": None,
            "document_type": document_type,
            "submitted_date": None,
            "availability": NOT_UPLOADED,
            "media_type": None,
            "verification_status": None,
        }
        for document_type in EXPECTED_DOCUMENT_TYPES
        if document_type not in present
    ]
    order = {document_type: index for index, document_type in enumerate(EXPECTED_DOCUMENT_TYPES)}
    items = sorted(entries + missing, key=lambda e: (order.get(e["document_type"], len(order)), e["document_type"]))
    return {"claim_id": claim_id, "documents": items}


def read_document_content(db: Session, claim_id: str, document_id: str, employee_id: str) -> tuple[bytes, str, object]:
    """(bytes, media type, document) for one viewable document of the claim.
    A document of another claim, a hidden type or an unknown ID is a 404."""
    authorize(db, claim_id, employee_id)
    document = crud_document.get(db, document_id)
    if document is None or document.Claim_ID != claim_id or document.Document_Type in HIDDEN_DOCUMENT_TYPES:
        raise _not_found("Document not found")
    path, media_or_reason = _stored_file(document)
    if path is None:
        if media_or_reason == UNSUPPORTED:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="This document cannot be previewed in the browser.",
            )
        raise _not_found(
            "Only the verification details of this copy were kept; there is no file to view."
            if media_or_reason == NOT_RETAINED
            else "The file for this document is not available."
        )
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise _not_found("The file for this document is not available.") from exc
    audit_log.info(
        "surveyor_document_view surveyor=%s claim=%s document=%s at=%s",
        employee_id,
        claim_id,
        document_id,
        surveyor_workflow.now_ist().isoformat(),
    )
    return content, media_or_reason, document
