from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_customer_id
from app.crud import vehicle as crud_vehicle
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.vehicle import VehicleOut

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("/me", response_model=list[VehicleOut])
def list_my_vehicles(customer_id: str = Depends(require_customer_id), db: Session = Depends(get_db)):
    return crud_vehicle.list_by_customer(db, customer_id)


@router.get("/{vehicle_id}", response_model=VehicleOut)
def read_vehicle(
    vehicle_id: str,
    current_user: AuthenticationUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = crud_vehicle.get(db, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    if current_user.Role == "Customer" and vehicle.Customer_ID != current_user.Customer_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own vehicles",
        )
    if current_user.Role == "Surveyor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")

    return vehicle
