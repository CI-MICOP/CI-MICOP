from sqlalchemy.orm import Session

from app.db_models.repair_estimate import RepairEstimate


def list_by_claim(db: Session, claim_id: str) -> list[RepairEstimate]:
    return (
        db.query(RepairEstimate)
        .filter(RepairEstimate.Claim_ID == claim_id)
        .order_by(RepairEstimate.Estimate_ID)
        .all()
    )
