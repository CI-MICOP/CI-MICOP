from sqlalchemy.orm import Session

from app.db_models.vehicle import Vehicle


def get(db: Session, vehicle_id: str) -> Vehicle | None:
    return db.query(Vehicle).filter(Vehicle.Vehicle_ID == vehicle_id).first()


def list_by_customer(db: Session, customer_id: str) -> list[Vehicle]:
    return db.query(Vehicle).filter(Vehicle.Customer_ID == customer_id).order_by(Vehicle.Vehicle_ID).all()
