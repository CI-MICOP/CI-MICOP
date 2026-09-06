"""Central RBAC ownership check for claim-scoped resources.

Used by every router that returns claim or claim-child data, so the
access rules live in exactly one place:
- Admin and Claims Officer: full access (claim processing role).
- Customer: only claims on their own Customer_ID.
- Surveyor: only claims with a surveyor_inspections row assigned to
  their Employee_ID.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import claim as crud_claim
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.claim import Claim


def get_claim_or_403(db: Session, claim_id: str, current_user: AuthenticationUser) -> Claim:
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    if current_user.Role in ("Admin", "Claims Officer"):
        return claim

    if current_user.Role == "Customer":
        if claim.Customer_ID == current_user.Customer_ID:
            return claim

    if current_user.Role == "Surveyor":
        if crud_claim.surveyor_is_assigned(db, claim_id, current_user.Employee_ID):
            return claim

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this claim",
    )
