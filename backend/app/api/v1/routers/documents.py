from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.crud import document as crud_document
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.document import DocumentOut
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    claim_id: str = Query(..., description="Claim to list documents for"),
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_claim_or_403(db, claim_id, current_user)
    return crud_document.list_by_claim(db, claim_id)


@router.get("/{document_id}", response_model=DocumentOut)
def read_document(
    document_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = crud_document.get(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    get_claim_or_403(db, document.Claim_ID, current_user)
    return document
