import re
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles, require_surveyor_employee_id
from app.crud import accident as crud_accident
from app.crud import claim as crud_claim
from app.crud import evidence as crud_evidence
from app.crud import repair_estimate as crud_repair_estimate
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.surveyor_inspection import SurveyorInspection
from app.schemas.claim import ClaimSummaryOut
from app.schemas.claim_detail import AccidentOut, EvidenceOut, RepairEstimateOut, VehicleDamageOut
from app.schemas.surveyor import (
    RepairEstimateCreate,
    SurveyorInspectionCreate,
    SurveyorInspectionOut,
    SurveyorInspectionUpdate,
    VehicleDamageCreate,
)
from app.services import (
    evidence_capture,
    evidence_storage,
    evidence_upload,
    inspection_creation,
    repair_estimate_creation,
    survey_report,
    survey_report_pdf,
    surveyor_documents,
    surveyor_workflow,
    vehicle_damage_creation,
    workflow_state,
)
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/surveyor", tags=["surveyor"])

_surveyor_or_admin = require_roles("Surveyor", "Admin")

# Statuses meaning "not started yet"; the first saved finding moves the
# inspection to "In Progress". "Completed" is only ever set by submission.
_NOT_STARTED_STATUSES = {"Assigned", "Scheduled"}
_FINDING_FIELDS = {
    "Vehicle_Condition",
    "Damage_Observed",
    "Damage_Severity",
    "Parts_Required",
    "Repair_Recommendation",
    "Surveyor_Comments",
}


def _assert_ready_for_submission(db: Session, inspection: SurveyorInspection, update_data: dict) -> None:
    """A survey report may only be submitted once the inspection records
    real findings (never the initial "Pending" placeholders) and the
    records the workflow requires are saved: a vehicle damage record when
    damage was observed, and a photo captured with the in-app camera by the
    assigned surveyor with a usable location. Records are checked in the
    database and the server-written capture records, never taken from the
    request (see services/surveyor_workflow.py, shared with the report
    endpoints)."""
    effective = {field: update_data.get(field, getattr(inspection, field)) for field in surveyor_workflow.INSPECTION_FIELD_LABELS}
    missing = surveyor_workflow.incomplete_inspection_fields(effective)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit an incomplete inspection. Missing/incomplete field(s): {', '.join(missing)}",
        )

    missing_records = surveyor_workflow.missing_records(db, inspection, effective["Damage_Observed"])
    if missing_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit the survey report yet. " + " ".join(missing_records),
        )


class CorrectionRequest(BaseModel):
    step: str


def _surveyor_evidence_view(db: Session, current_user: AuthenticationUser, claim_id: str, own) -> list[dict]:
    """Evidence the surveyor side may see: only photos taken through the
    surveyor camera workflow - for a surveyor, their own captures for their
    inspection. Customer photos (customer documents, or dataset evidence
    rows marked "Customer") and any row without a server-written surveyor
    capture record are never returned, whatever Evidence_Source says."""
    rows = []
    for e in crud_evidence.list_by_claim(db, claim_id):
        metadata = evidence_capture.read_metadata(e)
        if current_user.Role == "Surveyor":
            visible = bool(own) and evidence_capture.is_surveyor_capture_for(metadata, own)
        else:
            visible = evidence_capture.role_of(metadata) == evidence_capture.ROLE_SURVEYOR
        if visible:
            rows.append(
                {
                    **EvidenceOut.model_validate(e).model_dump(),
                    "capture": evidence_capture.public_view(metadata),
                    "qualifying_capture": bool(own) and evidence_capture.qualifies_for_inspection(metadata, own),
                }
            )
    return rows


def _pdf_response(report: dict) -> Response:
    pdf = survey_report_pdf.render_survey_report_pdf(report)
    safe_number = re.sub(r"[^A-Za-z0-9_-]", "_", report["claim"]["Claim_Number"])
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="survey-report-{safe_number}.pdf"',
            "Cache-Control": "no-store",
        },
    )


def _inspection_rows(db: Session, employee_id: str, submitted: bool) -> list[dict]:
    rows = []
    for inspection in crud_inspection.list_by_surveyor(db, employee_id):
        if bool(inspection.Survey_Report_Submitted) != submitted:
            continue
        claim = crud_claim.get(db, inspection.Claim_ID)
        rows.append(
            {
                "inspection": SurveyorInspectionOut.model_validate(inspection),
                "claim": ClaimSummaryOut.model_validate(claim) if claim else None,
                "schedule": surveyor_workflow.schedule_info(inspection),
            }
        )
    return rows


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


@router.get("/active-inspections")
def list_active_inspections(
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """The surveyor's active work: their inspections whose report has not
    been submitted, with the claim and the schedule. A submitted report
    leaves this list for good (see /survey-reports)."""
    return _inspection_rows(db, employee_id, submitted=False)


@router.get("/survey-reports")
def list_survey_reports(
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """The surveyor's submitted survey reports (history)."""
    return _inspection_rows(db, employee_id, submitted=True)


@router.get("/survey-reports/{inspection_id}/report")
def read_submitted_survey_report(
    inspection_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """A submitted report from the history - the surveyor's own only."""
    return survey_report.build_submitted_report(db, inspection_id, employee_id)


@router.get("/survey-reports/{inspection_id}/report.pdf")
def download_submitted_survey_report(
    inspection_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    return _pdf_response(survey_report.build_submitted_report(db, inspection_id, employee_id))


@router.get("/claims/{claim_id}")
def read_assigned_claim_detail(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_surveyor_or_admin),
    db: Session = Depends(get_db),
):
    """Accident, damage, and evidence information for a claim the
    surveyor is assigned to inspect, plus - for that surveyor - the
    authoritative workflow state (schedule, step completion, submission)
    the frontend displays."""
    get_claim_or_403(db, claim_id, current_user)
    inspections = crud_inspection.list_by_claim(db, claim_id)
    own = surveyor_workflow.own_inspection(inspections, current_user.Employee_ID)
    evidence = _surveyor_evidence_view(db, current_user, claim_id, own)

    return {
        "accidents": [AccidentOut.model_validate(a) for a in crud_accident.list_by_claim(db, claim_id)],
        "vehicle_damage": [
            VehicleDamageOut.model_validate(d) for d in crud_vehicle_damage.list_by_claim(db, claim_id)
        ],
        "evidence": evidence,
        "repair_estimates": [
            RepairEstimateOut.model_validate(r) for r in crud_repair_estimate.list_by_claim(db, claim_id)
        ],
        "inspections": [SurveyorInspectionOut.model_validate(i) for i in inspections],
        "workflow": surveyor_workflow.workflow_summary(db, own) if own else None,
    }


@router.get("/claims/{claim_id}/documents")
def list_claim_documents(
    claim_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """The Claim Documents panel (Claim Details step): the claim's customer
    documents with their real availability and verification status. Only
    the assigned surveyor, and only from the scheduled inspection date -
    see services/surveyor_documents.py."""
    return surveyor_documents.list_claim_documents(db, claim_id, employee_id)


_PREVIEW_EXTENSIONS = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}


@router.get("/claims/{claim_id}/documents/{document_id}/content")
def read_claim_document_content(
    claim_id: str,
    document_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """One claim document for the in-dashboard viewer, re-authorised on every
    request (repeat viewing is allowed). Served inline from the server-side
    record, never by path or public URL, and never cached."""
    content, media_type, _ = surveyor_documents.read_document_content(db, claim_id, document_id, employee_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            # A neutral name: the stored filename may identify the customer.
            "Content-Disposition": f'inline; filename="claim-document{_PREVIEW_EXTENSIONS[media_type]}"',
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            # Rendered as a passive document: no scripts, forms or plugins of its own.
            "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox",
        },
    )


@router.get("/claims/{claim_id}/report")
def read_survey_report(
    claim_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """The survey report for the assigned surveyor's own inspection - a
    Draft once the workflow is complete, or the submitted report. Only the
    assigned surveyor may read it. Read-only: never submits anything."""
    return survey_report.build_survey_report(db, claim_id, employee_id)


@router.get("/claims/{claim_id}/report.pdf")
def download_survey_report(
    claim_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """The same report as GET /claims/{claim_id}/report, as a PDF."""
    return _pdf_response(survey_report.build_survey_report(db, claim_id, employee_id))


@router.post("/vehicle-damage", response_model=VehicleDamageOut, status_code=status.HTTP_201_CREATED)
def create_vehicle_damage(
    payload: VehicleDamageCreate,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """Surveyor records a vehicle-damage observation. Vehicle_ID always
    comes from the claim itself (never the browser); assignment, schedule,
    submission and step order are enforced in
    services/vehicle_damage_creation.py via services/surveyor_workflow.py."""
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


@router.post("/evidence", status_code=status.HTTP_410_GONE)
def upload_evidence(employee_id: str = Depends(require_surveyor_employee_id)):
    """Retired: surveyors no longer upload evidence files. Accident and
    vehicle photos are taken with the in-app camera (POST
    /surveyor/evidence/capture), so a file from the device's storage or
    gallery can never be submitted as surveyor evidence. Kept as an
    explicit 410 so old clients get a clear answer."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Evidence files can no longer be uploaded. Capture photos with the in-app camera instead.",
    )


@router.post("/evidence/capture", status_code=status.HTTP_201_CREATED)
async def capture_evidence(
    claim_id: str = Form(...),
    evidence_type: str = Form(...),
    photo: UploadFile = File(...),
    captured_at: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    accuracy_m: float | None = Form(None),
    location_error: str | None = Form(None),
    evidence_date: str | None = Form(None),
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """A photo taken with the in-app camera, with the browser-reported
    capture time and location. The surveyor, claim, inspection, source and
    receipt time are established by the server (see
    services/evidence_upload.py capture_evidence_for_surveyor)."""
    evidence, metadata = await evidence_upload.capture_evidence_for_surveyor(
        db,
        employee_id,
        claim_id,
        evidence_type,
        photo,
        captured_at,
        latitude,
        longitude,
        accuracy_m,
        location_error,
        evidence_date,
    )
    inspection = crud_inspection.get(db, metadata["server"]["inspection_id"])
    return {
        **EvidenceOut.model_validate(evidence).model_dump(),
        "capture": evidence_capture.public_view(metadata),
        "qualifying_capture": evidence_capture.qualifies_for_inspection(metadata, inspection),
    }


@router.get("/evidence/{evidence_id}/image")
def read_evidence_image(
    evidence_id: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """A surveyor's own captured photo (for thumbnails). Anything else -
    customer photos, other surveyors' captures, rows without a capture
    record - answers 404, so nothing about it is disclosed."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    evidence = crud_evidence.get(db, evidence_id)
    if evidence is None or not crud_claim.surveyor_is_assigned(db, evidence.Claim_ID, employee_id):
        raise not_found
    # A verified surveyor capture record (same claim and row, photo hash
    # unchanged - services/evidence_capture.py) taken by this surveyor.
    metadata = evidence_capture.read_metadata(evidence)
    server = (metadata or {}).get("server") or {}
    if metadata is None or server.get("surveyor_employee_id") != employee_id:
        raise not_found
    path = evidence_storage.storage_path_for(evidence.Claim_ID, evidence.Evidence_ID, evidence.File_Name)
    media_type = "image/png" if server.get("image_format") == "PNG" else "image/jpeg"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})


def _own_inspection_or_404(db: Session, inspection_id: str, employee_id: str) -> SurveyorInspection:
    """The surveyor's own inspection on a claim still assigned to them.
    Anything else answers 404 alike, so another surveyor's inspection is
    not disclosed."""
    inspection = crud_inspection.get(db, inspection_id)
    if (
        inspection is None
        or inspection.Surveyor_ID != employee_id
        or not crud_claim.surveyor_is_assigned(db, inspection.Claim_ID, employee_id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    return inspection


@router.post("/inspections/{inspection_id}/corrections")
def open_correction(
    inspection_id: str,
    payload: CorrectionRequest,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    """The surveyor deliberately reopens a completed step to correct it.
    Recorded server-side (with an audit trail); only then may a locked step
    be changed. Not possible after submission or before the scheduled date."""
    inspection = _own_inspection_or_404(db, inspection_id, employee_id)
    surveyor_workflow.open_correction(db, inspection, payload.step, employee_id)
    return surveyor_workflow.workflow_summary(db, inspection)


@router.delete("/inspections/{inspection_id}/corrections/{step}")
def close_correction(
    inspection_id: str,
    step: str,
    employee_id: str = Depends(require_surveyor_employee_id),
    db: Session = Depends(get_db),
):
    inspection = _own_inspection_or_404(db, inspection_id, employee_id)
    surveyor_workflow.assert_inspection_writable(inspection)
    if step not in workflow_state.CORRECTABLE_STEPS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown step.")
    surveyor_workflow.close_corrections(inspection, (step,), employee_id, "closed_by_surveyor")
    return surveyor_workflow.workflow_summary(db, inspection)


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

    # A submitted report is final (it can no longer be reverted or edited)
    # and nothing may be recorded before the scheduled date - for every
    # role, since this is the only inspection update path.
    surveyor_workflow.assert_inspection_writable(inspection)

    # An explicit null is "no change" - never written to a required column.
    # Survey_Report_Submitted=false on an unsubmitted inspection is a no-op.
    update_data = {field: value for field, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if update_data.get("Survey_Report_Submitted") is False:
        update_data.pop("Survey_Report_Submitted")

    if update_data.get("Survey_Report_Submitted") is True:
        # Only the assigned surveyor submits their own report.
        if current_user.Role != "Surveyor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the assigned surveyor can submit this survey report.",
            )
        states = surveyor_workflow.step_states(db, inspection)
        if states["correction_state_error"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=surveyor_workflow.CORRECTION_STATE_ERROR
            )
        open_steps = [step for step, is_open in states["corrections"].items() if is_open]
        if open_steps:
            labels = ", ".join(surveyor_workflow.STEP_LABELS[step] for step in open_steps)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Finish the open correction ({labels}) before submitting the survey report.",
            )
        _assert_ready_for_submission(db, inspection, update_data)
        # Submitting a report implies the inspection is done - "Completed"
        # is the project's existing terminal status for this lifecycle.
        update_data["Inspection_Status"] = "Completed"
    elif update_data.get("Inspection_Status") == "Completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='An inspection becomes "Completed" only when its survey report is submitted.',
        )
    changes_findings = bool(_FINDING_FIELDS & update_data.keys())
    if changes_findings:
        # A completed step with work saved on later steps changes only inside
        # a correction the surveyor opened (services/surveyor_workflow.py).
        surveyor_workflow.assert_step_editable(db, inspection, surveyor_workflow.STEP_INSPECTION)
    if (
        update_data.get("Survey_Report_Submitted") is not True
        and "Inspection_Status" not in update_data
        and inspection.Inspection_Status in _NOT_STARTED_STATUSES
        and changes_findings
    ):
        # Recording findings starts the inspection.
        update_data["Inspection_Status"] = "In Progress"

    updated = crud_inspection.update(db, inspection, update_data)
    if changes_findings:
        # A saved correction of the inspection ends that correction; later
        # steps are re-checked from the saved data.
        surveyor_workflow.close_corrections(
            updated,
            (surveyor_workflow.STEP_INSPECTION,),
            current_user.Employee_ID or current_user.User_ID,
            "saved",
            strict=False,
        )
    return updated
