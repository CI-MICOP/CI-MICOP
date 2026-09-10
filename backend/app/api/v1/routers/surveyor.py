from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles, require_surveyor_employee_id
from app.crud import accident as crud_accident
from app.crud import evidence as crud_evidence
from app.crud import repair_estimate as crud_repair_estimate
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.surveyor_inspection import SurveyorInspection
from app.schemas.claim_detail import AccidentOut, EvidenceOut, RepairEstimateOut, VehicleDamageOut
from app.schemas.surveyor import (
    DAMAGE_OBSERVED_VALUES,
    DAMAGE_SEVERITY_VALUES,
    REPAIR_RECOMMENDATION_VALUES,
    VEHICLE_CONDITION_VALUES,
    RepairEstimateCreate,
    SurveyorInspectionCreate,
    SurveyorInspectionOut,
    SurveyorInspectionUpdate,
    VehicleDamageCreate,
)
from app.services import evidence_upload, inspection_creation, repair_estimate_creation, vehicle_damage_creation
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/surveyor", tags=["surveyor"])

_surveyor_or_admin = require_roles("Surveyor", "Admin")


def _assert_ready_for_submission(inspection: SurveyorInspection, update_data: dict) -> None:
    """A survey report may only be marked submitted once the inspection
    actually records real findings - never fabricated, but also never
    silently accepted while still at its initial "Pending" placeholders.
    """
    effective_vehicle_condition = update_data.get("Vehicle_Condition", inspection.Vehicle_Condition)
    effective_damage_observed = update_data.get("Damage_Observed", inspection.Damage_Observed)
    effective_damage_severity = update_data.get("Damage_Severity", inspection.Damage_Severity)
    effective_repair_recommendation = update_data.get("Repair_Recommendation", inspection.Repair_Recommendation)

    missing = []
    if effective_vehicle_condition not in VEHICLE_CONDITION_VALUES:
        missing.append("Vehicle_Condition")
    if effective_damage_observed not in DAMAGE_OBSERVED_VALUES:
        missing.append("Damage_Observed")
    if effective_damage_observed == "Yes" and effective_damage_severity not in DAMAGE_SEVERITY_VALUES:
        missing.append("Damage_Severity")
    if effective_repair_recommendation not in REPAIR_RECOMMENDATION_VALUES:
        missing.append("Repair_Recommendation")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit an incomplete inspection. Missing/incomplete field(s): {', '.join(missing)}",
        )


@router.post("/inspections", response_model=SurveyorInspectionOut, status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: SurveyorInspectionCreate,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """Surveyor starts a new inspection. Surveyor_ID always comes from the
    authenticated JWT - a surveyor can never create an inspection under
    another surveyor's identity, nor for a claim they are not assigned
    to (see services/inspection_creation.py for the assignment rule)."""
    return inspection_creation.create_inspection_for_surveyor(db, employee_id, payload)


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
        "repair_estimates": [
            RepairEstimateOut.model_validate(r) for r in crud_repair_estimate.list_by_claim(db, claim_id)
        ],
        "inspections": [
            SurveyorInspectionOut.model_validate(i) for i in crud_inspection.list_by_claim(db, claim_id)
        ],
    }


@router.post("/vehicle-damage", response_model=VehicleDamageOut, status_code=status.HTTP_201_CREATED)
def create_vehicle_damage(
    payload: VehicleDamageCreate,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """Surveyor records a vehicle-damage observation. Vehicle_ID always
    comes from the claim itself (never the browser), and Surveyor_ID/
    assignment is enforced the same way as inspection creation - see
    services/vehicle_damage_creation.py."""
    return vehicle_damage_creation.create_vehicle_damage_for_surveyor(db, employee_id, payload)


@router.post("/repair-estimates", response_model=RepairEstimateOut, status_code=status.HTTP_201_CREATED)
def create_repair_estimate(
    payload: RepairEstimateCreate,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """Surveyor records a repair estimate. Vehicle_ID always comes from
    the claim itself (never the browser), and Surveyor_ID/assignment is
    enforced the same way as vehicle-damage creation - see
    services/repair_estimate_creation.py. Multiple estimates per claim
    are supported (no unique constraint on Claim_ID)."""
    return repair_estimate_creation.create_repair_estimate_for_surveyor(db, employee_id, payload)


@router.post("/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    claim_id: str = Form(...),
    evidence_type: str = Form(...),
    evidence_date: date = Form(...),
    evidence_source: str = Form(...),
    file: UploadFile = File(...),
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """Surveyor uploads an evidence file for a claim they are assigned
    to. Only metadata is stored in PostgreSQL - the file itself is saved
    to local disk (see services/evidence_storage.py)."""
    return await evidence_upload.upload_evidence_for_surveyor(
        db, employee_id, claim_id, evidence_type, evidence_date, evidence_source, file
    )


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

    if update_data.get("Survey_Report_Submitted") is True:
        _assert_ready_for_submission(inspection, update_data)
        # Submitting a report implies the inspection is done - "Completed"
        # is the project's existing terminal status for this lifecycle.
        update_data["Inspection_Status"] = "Completed"

    return crud_inspection.update(db, inspection, update_data)
