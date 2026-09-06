from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles
from app.crud import accident as crud_accident
from app.crud import evidence as crud_evidence
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.claim_detail import AccidentOut, EvidenceOut, VehicleDamageOut
from app.schemas.surveyor import SurveyorInspectionOut, SurveyorInspectionUpdate
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/surveyor", tags=["surveyor"])

_surveyor_or_admin = require_roles("Surveyor", "Admin")


@router.get("/inspections", response_model=list[SurveyorInspectionOut])
def list_my_inspections(
    current_user: AuthenticationUser = Depends(_surveyor_or_admin),
    db: Session = Depends(get_db),
):
    if current_user.Role == "Admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin has no assigned inspections; use /claims to browse all claims",
        )
    return crud_inspection.list_by_surveyor(db, current_user.Employee_ID)


@router.get("/claims/{claim_id}")
def read_assigned_claim_detail(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_surveyor_or_admin),
    db: Session = Depends(get_db),
):
    """Accident, damage, and evidence information for a claim the
    surveyor is assigned to inspect."""
    get_claim_or_403(db, claim_id, current_user)
    return {
        "accidents": [AccidentOut.model_validate(a) for a in crud_accident.list_by_claim(db, claim_id)],
        "vehicle_damage": [
            VehicleDamageOut.model_validate(d) for d in crud_vehicle_damage.list_by_claim(db, claim_id)
        ],
        "evidence": [EvidenceOut.model_validate(e) for e in crud_evidence.list_by_claim(db, claim_id)],
        "inspections": [
            SurveyorInspectionOut.model_validate(i) for i in crud_inspection.list_by_claim(db, claim_id)
        ],
    }


@router.patch("/inspections/{inspection_id}", response_model=SurveyorInspectionOut)
def update_inspection(
    inspection_id: str,
    payload: SurveyorInspectionUpdate,
    current_user: AuthenticationUser = Depends(_surveyor_or_admin),
    db: Session = Depends(get_db),
):
    inspection = crud_inspection.get(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    if current_user.Role == "Surveyor" and inspection.Surveyor_ID != current_user.Employee_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only update inspections assigned to you",
        )

    update_data = payload.model_dump(exclude_unset=True)
    return crud_inspection.update(db, inspection, update_data)
