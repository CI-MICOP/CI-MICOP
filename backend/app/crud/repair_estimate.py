from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.repair_estimate import RepairEstimate


def get(db: Session, estimate_id: str) -> RepairEstimate | None:
    return db.query(RepairEstimate).filter(RepairEstimate.Estimate_ID == estimate_id).first()


def list_by_claim(db: Session, claim_id: str) -> list[RepairEstimate]:
    return (
        db.query(RepairEstimate)
        .filter(RepairEstimate.Claim_ID == claim_id)
        .order_by(RepairEstimate.Estimate_ID)
        .all()
    )


def create(db: Session, estimate: RepairEstimate) -> RepairEstimate:
    db.add(estimate)
    return estimate


def generate_estimate_id(db: Session, attempts: int = 20) -> str:
    """EST-YYYYMMDD-XXXXXX, checked against the primary key before use -
    same convention as Document_ID/Inspection_ID/Damage_ID/Evidence_ID,
    never accepted from the browser."""
    today = date.today().strftime("%Y%m%d")
    for _ in range(attempts):
        candidate = f"EST-{today}-{uuid4().hex[:6].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Estimate_ID")
