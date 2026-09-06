from sqlalchemy.orm import Session

from app.db_models.surveyor_inspection import SurveyorInspection


def get(db: Session, inspection_id: str) -> SurveyorInspection | None:
    return db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == inspection_id).first()


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
