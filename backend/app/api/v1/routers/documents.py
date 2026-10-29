from dataclasses import replace

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_customer_id
from app.crud import claim as crud_claim
from app.crud import document as crud_document
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.document import DocumentOut
from app.schemas.document_analysis import DocumentAnalysisOut, DocumentCompletenessOut
from app.schemas.document_consistency import DocumentConsistencyOut, EntityConsistencyOut
from app.schemas.entity_extraction import EntityCandidateOut, EntityExtractionResultOut
from app.services import (
    claim_photos,
    customer_identity_documents,
    document_analysis,
    document_consistency,
    document_upload,
    entity_extraction,
)
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/documents", tags=["documents"])

_IDENTITY_PREVIEW_EXTENSIONS = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}


def _hidden_from(current_user: AuthenticationUser, document) -> bool:
    """Customer accident photos are customer evidence: a surveyor captures
    their own photos and never sees the customer's (they stay available to
    the customer and to claims officers). The claim's other documents - RC,
    driving licence, policy, FIR, estimates - stay visible to the surveyor
    assigned to the claim."""
    return current_user.Role == "Surveyor" and document.Document_Type == claim_photos.CUSTOMER_ACCIDENT_PHOTO_TYPE


def _get_visible_document_or_404(db: Session, document_id: str, current_user: AuthenticationUser):
    """A document on a claim the caller may access (the customer's own
    claim, a claim assigned to the surveyor, or any claim for officers),
    checked against the database. A missing document, one on someone
    else's claim and one hidden from the caller all get the same 404, so
    a guessed ID reveals nothing about another customer's documents."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document = crud_document.get(db, document_id)
    if document is None:
        raise not_found
    try:
        get_claim_or_403(db, document.Claim_ID, current_user)
    except HTTPException as exc:
        raise not_found from exc
    if _hidden_from(current_user, document):
        raise not_found
    return document


def _without_accident_photos(completeness, claim_type: str):
    """Completeness as a surveyor may see it: whether the customer's
    accident photos are present is not disclosed, so that type is left out
    of the required/present/missing lists and the ratio."""
    label = claim_photos.CUSTOMER_ACCIDENT_PHOTO_TYPE
    required = [t for t in completeness.required if t != label]
    present = [t for t in completeness.present if t != label]
    missing = [t for t in completeness.missing if t != label]
    if not completeness.available or required == completeness.required:
        return replace(completeness, required=required, present=present, missing=missing)
    return replace(
        completeness,
        required=required,
        present=present,
        missing=missing,
        ratio=(len(present) / len(required)) if required else 1.0,
        explanation=(
            f"{len(present)} of {len(required)} required document type(s) are present for this "
            f"'{claim_type}' claim (customer accident photos are not shown to surveyors)."
        ),
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    claim_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    customer_id: str = Depends(require_customer_id),
    db: Session = Depends(get_db),
):
    """Customer document upload for an existing claim. Customer_ID always
    comes from the authenticated JWT via require_customer_id; claim
    ownership is re-checked against the database, never trusted from the
    request."""
    return await document_upload.upload_document_for_customer(db, customer_id, claim_id, document_type, file)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    claim_id: str = Query(..., description="Claim to list documents for"),
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_claim_or_403(db, claim_id, current_user)
    return [d for d in crud_document.list_by_claim(db, claim_id) if not _hidden_from(current_user, d)]


@router.get("/identity")
def list_identity_documents(
    customer_id: str = Depends(require_customer_id),
    db: Session = Depends(get_db),
):
    """The Customer Portal's "My Documents" identity section: this
    customer's own RC, Driving Licence and Insurance Policy documents
    imported directly onto their record (services/document_import.py).
    Customer_ID always comes from the authenticated JWT, never the
    request - see services/customer_identity_documents.py. Registered
    ahead of /{document_id} below so "identity" is never read as a
    document ID."""
    return customer_identity_documents.list_identity_documents(db, customer_id)


@router.get("/identity/{document_id}/content")
def read_identity_document_content(
    document_id: str,
    customer_id: str = Depends(require_customer_id),
    db: Session = Depends(get_db),
):
    """One of this customer's own identity documents, for the in-dashboard
    viewer. Served inline from the server-side record, never by path or
    public URL."""
    content, media_type, _ = customer_identity_documents.read_identity_document_content(db, customer_id, document_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="identity-document{_IDENTITY_PREVIEW_EXTENSIONS[media_type]}"',
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox",
        },
    )


@router.get("/{document_id}", response_model=DocumentOut)
def read_document(
    document_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_visible_document_or_404(db, document_id, current_user)


@router.post("/{document_id}/analyze", response_model=DocumentAnalysisOut)
def analyze_document(
    document_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 5.8.12: on-demand OCR/text-extraction for this ONE document
    (see services/document_analysis.py). Genuinely extracts and persists
    Extracted_Text/OCR_Confidence_Score - never fabricates either. The
    completeness figure returned here is computed live from the claim's
    current documents but NOT persisted (see analyze_claim_documents in
    officer.py for the claim-level endpoint that does persist it) - this
    keeps a single-document view from silently rewriting every other
    document row on the claim. Analysis-only: never touches
    Final_Decision, Approved_Amount, or claim_decision_audit."""
    document = _get_visible_document_or_404(db, document_id, current_user)

    result = document_analysis.analyze_document(db, document)

    claim = crud_claim.get(db, document.Claim_ID)
    documents = [d for d in crud_document.list_by_claim(db, document.Claim_ID) if not _hidden_from(current_user, d)]
    completeness = document_analysis.calculate_claim_document_completeness(claim.Claim_Type, documents)
    if current_user.Role == "Surveyor":
        completeness = _without_accident_photos(completeness, claim.Claim_Type)

    # Step 5.8.13-A: best-effort, deterministic, read-time-only entity
    # extraction from the text just produced above - never persisted, never
    # compared against the claim's structured data (that is Step 5.8.13-B).
    entities = entity_extraction.extract_entities(
        result.text, document_type=document.Document_Type, ocr_confidence=result.confidence
    )

    # Step 5.8.13-B: deterministic MATCH/MISMATCH/UNAVAILABLE comparison
    # against the claim's own structured vehicle/policy data. Re-reads
    # every relevant document's already-persisted Extracted_Text (the
    # commit above already made this document's own text visible) - it
    # does not re-run OCR/extraction itself.
    consistency = document_consistency.compare_claim_documents(db, claim)

    return DocumentAnalysisOut(
        Document_ID=document.Document_ID,
        Document_Type=document.Document_Type,
        extraction_status=result.status,
        extracted_text=result.text,
        ocr_confidence=result.confidence,
        mismatch_indicator=document.Document_Mismatch_Indicator,
        completeness=DocumentCompletenessOut(
            available=completeness.available,
            required_document_types=completeness.required,
            present_document_types=completeness.present,
            missing_document_types=completeness.missing,
            completeness_ratio=completeness.ratio,
            explanation=completeness.explanation,
        ),
        entities=EntityExtractionResultOut(
            status=entities.status,
            entities=[
                EntityCandidateOut(
                    entity_type=e.entity_type,
                    value=e.value,
                    normalized_value=e.normalized_value,
                    confidence=e.confidence,
                    source=e.source,
                    reason=e.reason,
                )
                for e in entities.entities
            ],
            limitations=entities.limitations,
        ),
        consistency=DocumentConsistencyOut(
            registration=EntityConsistencyOut(
                status=consistency.registration.status,
                structured_value=consistency.registration.structured_value,
                extracted_value=consistency.registration.extracted_value,
                matched_document_type=consistency.registration.matched_document_type,
                matched_document_id=consistency.registration.matched_document_id,
                explanation=consistency.registration.explanation,
                outcome=consistency.registration.outcome or None,
            ),
            policy=EntityConsistencyOut(
                status=consistency.policy.status,
                structured_value=consistency.policy.structured_value,
                extracted_value=consistency.policy.extracted_value,
                matched_document_type=consistency.policy.matched_document_type,
                matched_document_id=consistency.policy.matched_document_id,
                explanation=consistency.policy.explanation,
                outcome=consistency.policy.outcome or None,
            ),
        ),
        limitations=result.limitations,
    )
