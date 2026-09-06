from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_customer_id
from app.crud import policy as crud_policy
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.policy import PolicyOut

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/me", response_model=list[PolicyOut])
def list_my_policies(customer_id: str = Depends(require_customer_id), db: Session = Depends(get_db)):
    return crud_policy.list_by_customer(db, customer_id)


@router.get("/{policy_id}", response_model=PolicyOut)
def read_policy(
    policy_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = crud_policy.get(db, policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    if current_user.Role == "Customer" and policy.Customer_ID != current_user.Customer_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own policies",
        )
    if current_user.Role == "Surveyor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")

    return policy
