from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.accident import Accident


def list_by_claim(db: Session, claim_id: str) -> list[Accident]:
    return db.query(Accident).filter(Accident.Claim_ID == claim_id).order_by(Accident.Accident_ID).all()


def create(db: Session, accident: Accident) -> Accident:
    db.add(accident)
    return accident


def generate_accident_id(db: Session, attempts: int = 20) -> str:
    for _ in range(attempts):
        candidate = f"ACC-{uuid4().hex[:10].upper()}"
        exists = db.query(Accident.Accident_ID).filter(Accident.Accident_ID == candidate).first()
        if exists is None:
            return candidate
    raise RuntimeError("Could not generate a unique Accident_ID")
