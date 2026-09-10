from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.vehicle_damage import VehicleDamage


def get(db: Session, damage_id: str) -> VehicleDamage | None:
    return db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).first()


def list_by_claim(db: Session, claim_id: str) -> list[VehicleDamage]:
    return (
        db.query(VehicleDamage)
        .filter(VehicleDamage.Claim_ID == claim_id)
        .order_by(VehicleDamage.Damage_ID)
        .all()
    )


def create(db: Session, damage: VehicleDamage) -> VehicleDamage:
    db.add(damage)
    return damage


def generate_damage_id(db: Session, attempts: int = 20) -> str:
    """DMG-YYYYMMDD-XXXXXX, checked against the primary key before use -
    never accepted from the browser."""
    today = date.today().strftime("%Y%m%d")
    for _ in range(attempts):
        candidate = f"DMG-{today}-{uuid4().hex[:6].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Damage_ID")
