from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.evidence import Evidence


def get(db: Session, evidence_id: str) -> Evidence | None:
    return db.query(Evidence).filter(Evidence.Evidence_ID == evidence_id).first()


def list_by_claim(db: Session, claim_id: str) -> list[Evidence]:
    return db.query(Evidence).filter(Evidence.Claim_ID == claim_id).order_by(Evidence.Evidence_ID).all()


def create(db: Session, evidence: Evidence) -> Evidence:
    db.add(evidence)
    return evidence


def generate_evidence_id(db: Session, attempts: int = 20) -> str:
    """EVD-YYYYMMDD-XXXXXX, checked against the primary key before use -
    never accepted from the browser."""
    today = date.today().strftime("%Y%m%d")
    for _ in range(attempts):
        candidate = f"EVD-{today}-{uuid4().hex[:6].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Evidence_ID")
