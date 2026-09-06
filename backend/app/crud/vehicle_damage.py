from sqlalchemy.orm import Session

from app.db_models.vehicle_damage import VehicleDamage


def list_by_claim(db: Session, claim_id: str) -> list[VehicleDamage]:
    return (
        db.query(VehicleDamage)
        .filter(VehicleDamage.Claim_ID == claim_id)
        .order_by(VehicleDamage.Damage_ID)
        .all()
    )
