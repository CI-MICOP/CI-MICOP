from sqlalchemy.orm import Session

from app.db_models.accident import Accident


def list_by_claim(db: Session, claim_id: str) -> list[Accident]:
    return db.query(Accident).filter(Accident.Claim_ID == claim_id).order_by(Accident.Accident_ID).all()
