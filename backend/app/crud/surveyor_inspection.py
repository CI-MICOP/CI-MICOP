from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.surveyor_inspection import SurveyorInspection


def get(db: Session, inspection_id: str) -> SurveyorInspection | None:
    return db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == inspection_id).first()


def create(db: Session, inspection: SurveyorInspection) -> SurveyorInspection:
    db.add(inspection)
    return inspection


def generate_inspection_id(db: Session, attempts: int = 20) -> str:
    """INSP-YYYYMMDD-XXXXXX, checked against the primary key before use -
    never accepted from the browser."""
    today = date.today().strftime("%Y%m%d")
    for _ in range(attempts):
        candidate = f"INSP-{today}-{uuid4().hex[:6].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Inspection_ID")


def list_by_surveyor(db: Session, employee_id: str) -> list[SurveyorInspection]:
    return (
        db.query(SurveyorInspection)
        .filter(SurveyorInspection.Surveyor_ID == employee_id)
        .order_by(SurveyorInspection.Inspection_Date.desc())
        .all()
    )


def list_by_claim(db: Session, claim_id: str) -> list[SurveyorInspection]:
    return (
        db.query(SurveyorInspection)
        .filter(SurveyorInspection.Claim_ID == claim_id)
        .order_by(SurveyorInspection.Inspection_ID)
        .all()
    )


def update(db: Session, inspection: SurveyorInspection, data: dict) -> SurveyorInspection:
    for field, value in data.items():
        setattr(inspection, field, value)
    db.commit()
    db.refresh(inspection)
    return inspection
