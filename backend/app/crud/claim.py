from sqlalchemy.orm import Session

from app.db_models.claim import Claim
from app.db_models.surveyor_inspection import SurveyorInspection


def get(db: Session, claim_id: str) -> Claim | None:
    return db.query(Claim).filter(Claim.Claim_ID == claim_id).first()


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
