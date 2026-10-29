"""The Customer Portal's "My Documents" identity-document section: the
authenticated customer's own RC, Driving Licence and Insurance Policy
documents that were imported directly onto their customer record ahead
of any claim (services/document_import.py) - distinct from, and additive
to, the existing per-claim document list (services/document_upload.py,
DocumentsPage's claim-by-claim table), which is unaffected by this
module. Mirrors services/surveyor_documents.py's list_claim_documents in
shape and vocabulary (available / not_uploaded / unavailable /
unsupported), but scoped to a customer rather than a claim.

Customer_ID is always the one resolved from the authenticated JWT
(api/v1/deps.require_customer_id) - never one supplied by the browser -
so a customer can only ever see this response for their own account.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.services import claim_copy_retention, document_storage

IDENTITY_DOCUMENT_TYPES = claim_copy_retention.NOT_RETAINED_DOCUMENT_TYPES
EXPECTED_DOCUMENT_TYPES = ("RC", "Driving Licence", "Insurance Policy")

_PREVIEWABLE = ((b"%PDF-", "application/pdf"), (b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))

AVAILABLE = "available"
NOT_UPLOADED = "not_uploaded"
UNAVAILABLE = "unavailable"
UNSUPPORTED = "unsupported"


def _stored_file(document) -> tuple[Path | None, str | None]:
    try:
        path = document_storage.storage_path_for(document.Customer_ID, document.Document_ID, document.Document_Name)
    except ValueError:
        return None, UNAVAILABLE
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return None, UNAVAILABLE
    media_type = next((media for magic, media in _PREVIEWABLE if head.startswith(magic)), None)
    return (path, media_type) if media_type else (None, UNSUPPORTED)


def _entry(document) -> dict:
    path, media_or_reason = _stored_file(document)
    return {
        "document_id": document.Document_ID,
        "document_type": document.Document_Type,
        "submitted_date": document.Document_Submitted_Date,
        "expiry_date": document.Document_Expiry_Date,
        "availability": AVAILABLE if path else media_or_reason,
        "media_type": media_or_reason if path else None,
        "verification_status": document.Verification_Status or "Pending",
    }


def list_identity_documents(db: Session, customer_id: str) -> dict:
    """RC / Driving Licence / Insurance Policy only, one entry per type -
    the most recently imported/uploaded document of that type, each
    marked "not_uploaded" when the customer has none yet."""
    documents = [
        d
        for d in crud_document.list_identity_documents_by_customer(db, customer_id)
        if d.Document_Type in IDENTITY_DOCUMENT_TYPES
    ]
    latest_by_type = {d.Document_Type: d for d in sorted(documents, key=lambda d: d.Document_ID)}
    entries = [_entry(d) for d in latest_by_type.values()]
    present = set(latest_by_type)
    missing = [
        {
            "document_id": None,
            "document_type": document_type,
            "submitted_date": None,
            "expiry_date": None,
            "availability": NOT_UPLOADED,
            "media_type": None,
            "verification_status": None,
        }
        for document_type in EXPECTED_DOCUMENT_TYPES
        if document_type not in present
    ]
    order = {document_type: index for index, document_type in enumerate(EXPECTED_DOCUMENT_TYPES)}
    items = sorted(entries + missing, key=lambda e: (order.get(e["document_type"], len(order)), e["document_type"]))
    return {"customer_id": customer_id, "documents": items}


def read_identity_document_content(db: Session, customer_id: str, document_id: str) -> tuple[bytes, str, object]:
    """(bytes, media type, document) for one of this customer's own
    identity documents. A document belonging to another customer, a
    claim-scoped document, or an unknown ID is the same 404, so a guessed
    ID never discloses another customer's document."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document = crud_document.get(db, document_id)
    if (
        document is None
        or document.Claim_ID is not None
        or document.Customer_ID != customer_id
        or document.Document_Type not in IDENTITY_DOCUMENT_TYPES
    ):
        raise not_found
    path, media_or_reason = _stored_file(document)
    if path is None:
        if media_or_reason == UNSUPPORTED:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="This document cannot be previewed in the browser.",
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The file for this document is not available.")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The file for this document is not available."
        ) from exc
    return content, media_or_reason, document
