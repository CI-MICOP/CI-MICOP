from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_customer_id
from app.crud import customer as crud_customer
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.customer import CustomerOut

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/me", response_model=CustomerOut)
def read_my_customer_profile(
    customer_id: str = Depends(require_customer_id), db: Session = Depends(get_db)
):
    customer = crud_customer.get(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer profile not found")
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def read_customer(
    customer_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.Role == "Customer" and current_user.Customer_ID != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own customer record",
        )
    if current_user.Role == "Surveyor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")

    customer = crud_customer.get(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer
