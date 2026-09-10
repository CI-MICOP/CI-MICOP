from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.claim import Claim
from app.db_models.surveyor_inspection import SurveyorInspection


def get(db: Session, claim_id: str) -> Claim | None:
    return db.query(Claim).filter(Claim.Claim_ID == claim_id).first()


def create(db: Session, claim: Claim) -> Claim:
    db.add(claim)
    return claim


def update(db: Session, claim: Claim, data: dict) -> Claim:
    """Sets attributes only - does not commit, so callers can compose this
    with other writes (e.g. a claim_decision_audit insert) into one
    transaction, matching services/claim_decision.py's single-commit
    requirement."""
    for field, value in data.items():
        setattr(claim, field, value)
    return claim


def generate_claim_id(db: Session, attempts: int = 20) -> str:
    """Server-generated primary key - never accepted from the browser."""
    for _ in range(attempts):
        candidate = f"CLM-{uuid4().hex[:10].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Claim_ID")


def generate_claim_number(db: Session, claim_date: date, attempts: int = 20) -> str:
    """CLM-YYYY-XXXXXXXX, checked against the claims.Claim_Number unique
    constraint before being handed back (collision here is effectively
    impossible, but the check keeps the guarantee explicit rather than
    assumed)."""
    for _ in range(attempts):
        candidate = f"CLM-{claim_date.year}-{uuid4().hex[:8].upper()}"
        exists = db.query(Claim.Claim_Number).filter(Claim.Claim_Number == candidate).first()
        if exists is None:
            return candidate
    raise RuntimeError("Could not generate a unique Claim_Number")


def list_by_customer(db: Session, customer_id: str, skip: int = 0, limit: int = 100) -> list[Claim]:
    return (
        db.query(Claim)
        .filter(Claim.Customer_ID == customer_id)
        .order_by(Claim.Claim_Date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_by_surveyor(db: Session, employee_id: str, skip: int = 0, limit: int = 100) -> list[Claim]:
    """Claims that have at least one inspection assigned to this surveyor."""
    return (
        db.query(Claim)
        .join(SurveyorInspection, SurveyorInspection.Claim_ID == Claim.Claim_ID)
        .filter(SurveyorInspection.Surveyor_ID == employee_id)
        .order_by(Claim.Claim_Date.desc())
        .distinct()
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_all(db: Session, skip: int = 0, limit: int = 100, claim_status: str | None = None) -> list[Claim]:
    query = db.query(Claim)
    if claim_status:
        query = query.filter(Claim.Claim_Status == claim_status)
    return query.order_by(Claim.Claim_Date.desc()).offset(skip).limit(limit).all()


def surveyor_is_assigned(db: Session, claim_id: str, employee_id: str) -> bool:
    return (
        db.query(SurveyorInspection)
        .filter(SurveyorInspection.Claim_ID == claim_id, SurveyorInspection.Surveyor_ID == employee_id)
        .first()
        is not None
    )
