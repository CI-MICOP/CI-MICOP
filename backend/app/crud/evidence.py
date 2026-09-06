from sqlalchemy.orm import Session

from app.db_models.evidence import Evidence


def list_by_claim(db: Session, claim_id: str) -> list[Evidence]:
    return db.query(Evidence).filter(Evidence.Claim_ID == claim_id).order_by(Evidence.Evidence_ID).all()
