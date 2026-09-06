from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.crud import claim as crud_claim
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.claim import ClaimOut, ClaimSummaryOut
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=list[ClaimSummaryOut])
def list_claims(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Claims visible to the current user:
    - Customer: only their own claims.
    - Surveyor: only claims with an inspection assigned to them.
    - Claims Officer / Admin: all claims (claim processing role).
    """
    if current_user.Role == "Customer":
        return crud_claim.list_by_customer(db, current_user.Customer_ID, skip, limit)
    if current_user.Role == "Surveyor":
        return crud_claim.list_by_surveyor(db, current_user.Employee_ID, skip, limit)
    return crud_claim.list_all(db, skip, limit)


@router.get("/{claim_id}", response_model=ClaimOut)
def read_claim(
    claim_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_claim_or_403(db, claim_id, current_user)
