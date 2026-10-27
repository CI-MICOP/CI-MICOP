"""The surveyor's claim workflow: schedule, step order, completeness, step
locks, corrections and write locks - the one place these rules live.

Claim Details -> Inspection -> Vehicle Damage -> Evidence -> Survey Report.

Every state-changing surveyor action (inspection update, damage record,
evidence capture, report submission) goes through these checks, and the
report endpoints and the claim detail's "workflow" summary use the same
functions, so the browser only ever displays what the server decides.

Time zone: inspection dates are calendar dates with no time of day or time
zone in the schema. The portal serves Indian claims (INR amounts, Indian
states and pincodes), so a scheduled date is interpreted as that date in
India Standard Time (UTC+05:30, no daylight saving), and the server's
clock is converted to IST explicitly - the result does not depend on the
server machine's own time zone. With a date only, an inspection opens at
00:00 IST on its date, not at an appointment time.

Step locks (forward progression, derived from saved data): a completed
step is locked once work has been saved on a later step - Inspection once
a damage record or a surveyor photo exists, Vehicle Damage once a
surveyor photo exists. A locked step can only be changed after the
surveyor explicitly opens a correction for it (POST .../corrections,
recorded server-side in services/workflow_state.py). Evidence is the last
step before submission and stays open until the report is submitted.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import evidence as crud_evidence
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.surveyor_inspection import SurveyorInspection
from app.schemas.surveyor import (
    DAMAGE_OBSERVED_VALUES,
    DAMAGE_SEVERITY_VALUES,
    REPAIR_RECOMMENDATION_VALUES,
    VEHICLE_CONDITION_VALUES,
)
from app.services import evidence_capture, workflow_state
from app.services.claim_access import get_claim_assigned_to_surveyor_or_403

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30), "IST")
SCHEDULE_TIMEZONE_LABEL = "India Standard Time (UTC+05:30)"

STEP_INSPECTION = "inspection"
STEP_DAMAGE = "damage"
STEP_EVIDENCE = "evidence"
STEP_LABELS = {STEP_INSPECTION: "Inspection", STEP_DAMAGE: "Vehicle Damage", STEP_EVIDENCE: "Evidence"}

INSPECTION_FIELD_LABELS = {
    "Vehicle_Condition": "Vehicle Condition",
    "Damage_Observed": "Damage Observed",
    "Damage_Severity": "Damage Severity",
    "Repair_Recommendation": "Repair Recommendation",
}


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist():
    return now_ist().date()


# ---------------------------------------------------------------- which inspection


def own_inspection(inspections: list[SurveyorInspection], employee_id: str | None) -> SurveyorInspection | None:
    """The surveyor's own inspection for a claim: the active (not yet
    submitted) one if there is one, otherwise their latest submitted one.
    Never another surveyor's. `inspections` is in crud list_by_claim order."""
    mine = [i for i in inspections if employee_id and i.Surveyor_ID == employee_id]
    active = [i for i in mine if not i.Survey_Report_Submitted]
    if active:
        return active[-1]
    return mine[-1] if mine else None


# ---------------------------------------------------------------- schedule


def scheduled_start(inspection: SurveyorInspection) -> datetime:
    return datetime.combine(inspection.Inspection_Date, time(0, 0), tzinfo=IST)


def schedule_reached(inspection: SurveyorInspection, now: datetime | None = None) -> bool:
    return (now or now_ist()) >= scheduled_start(inspection)


def _long_date(value) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def schedule_message(inspection: SurveyorInspection) -> str:
    return f"This inspection will become available on {_long_date(inspection.Inspection_Date)} (India Standard Time)."


def schedule_info(inspection: SurveyorInspection, now: datetime | None = None) -> dict:
    now = now or now_ist()
    return {
        "scheduled_date": inspection.Inspection_Date.isoformat(),
        "starts_at": scheduled_start(inspection).isoformat(),
        "has_time": False,  # the schema stores a date only
        "timezone": SCHEDULE_TIMEZONE_LABEL,
        "reached": schedule_reached(inspection, now),
        "server_time": now.isoformat(),
        "message": schedule_message(inspection),
    }


# ---------------------------------------------------------------- completeness


def incomplete_inspection_fields(values: dict) -> list[str]:
    """Inspection fields still at "Pending" or holding a value that is not
    an allowed final value."""
    missing = []
    if values.get("Vehicle_Condition") not in VEHICLE_CONDITION_VALUES:
        missing.append("Vehicle_Condition")
    if values.get("Damage_Observed") not in DAMAGE_OBSERVED_VALUES:
        missing.append("Damage_Observed")
    if values.get("Damage_Observed") == "Yes" and values.get("Damage_Severity") not in DAMAGE_SEVERITY_VALUES:
        missing.append("Damage_Severity")
    if values.get("Repair_Recommendation") not in REPAIR_RECOMMENDATION_VALUES:
        missing.append("Repair_Recommendation")
    return missing


def _inspection_values(inspection: SurveyorInspection, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    return {field: overrides.get(field, getattr(inspection, field)) for field in INSPECTION_FIELD_LABELS}


def surveyor_captures(db: Session, inspection: SurveyorInspection) -> list[tuple]:
    """(evidence row, capture record) for this inspection's own surveyor
    captures - never customer photos or rows without a capture record."""
    rows = []
    for e in crud_evidence.list_by_claim(db, inspection.Claim_ID):
        metadata = evidence_capture.read_metadata(e)
        if evidence_capture.is_surveyor_capture_for(metadata, inspection):
            rows.append((e, metadata))
    return rows


def qualifying_photo_count(db: Session, inspection: SurveyorInspection) -> int:
    return sum(1 for _, m in surveyor_captures(db, inspection) if evidence_capture.qualifies_for_inspection(m, inspection))


def missing_records(db: Session, inspection: SurveyorInspection, damage_observed: str | None) -> list[str]:
    """The saved records the workflow still needs, worked out from the
    database and the server-written capture records - never from anything
    the browser claims (a "Surveyor" source value alone never counts)."""
    problems = []
    if damage_observed == "Yes" and not crud_vehicle_damage.list_by_claim(db, inspection.Claim_ID):
        problems.append("Damage was observed, but no vehicle damage record has been saved.")
    if qualifying_photo_count(db, inspection) == 0:
        problems.append(
            "No photo captured with the in-app camera by the assigned surveyor, with a usable location reading, "
            "has been saved."
        )
    return problems


def workflow_problems(db: Session, inspection: SurveyorInspection) -> list[str]:
    values = _inspection_values(inspection)
    problems = [
        f"{INSPECTION_FIELD_LABELS[field]} is not complete." for field in incomplete_inspection_fields(values)
    ]
    return problems + missing_records(db, inspection, values["Damage_Observed"])


def consistency_warnings(db: Session, inspection: SurveyorInspection) -> list[str]:
    """Saved data that disagrees after a correction - shown in the report,
    never silently changed."""
    warnings = []
    if inspection.Damage_Observed == "No" and crud_vehicle_damage.list_by_claim(db, inspection.Claim_ID):
        warnings.append("Damage Observed is \"No\", but vehicle damage records are saved for this claim.")
    return warnings


# ---------------------------------------------------------------- step locks and corrections


def step_states(db: Session, inspection: SurveyorInspection) -> dict:
    values = _inspection_values(inspection)
    inspection_complete = not incomplete_inspection_fields(values)
    damage_required = values["Damage_Observed"] == "Yes"
    damage_count = len(crud_vehicle_damage.list_by_claim(db, inspection.Claim_ID))
    damage_complete = inspection_complete and (not damage_required or damage_count > 0)
    captures = surveyor_captures(db, inspection)
    qualifying = sum(1 for _, m in captures if evidence_capture.qualifies_for_inspection(m, inspection))
    try:
        corrections, state_error = workflow_state.open_corrections(inspection), False
    except workflow_state.WorkflowStateError:
        # Fail closed: no correction counts as open (locked steps stay
        # locked) and submission is refused until the file is repaired.
        logger.exception("Unreadable correction state for inspection %s", inspection.Inspection_ID)
        corrections, state_error = {}, True
    return {
        "inspection_complete": inspection_complete,
        "damage_required": damage_required,
        "damage_count": damage_count,
        "damage_complete": damage_complete,
        "capture_count": len(captures),
        "qualifying_photo_count": qualifying,
        "evidence_complete": damage_complete and qualifying > 0,
        # Locked = complete, with work already saved on a later step.
        "locked": {
            STEP_INSPECTION: inspection_complete and (damage_count > 0 or len(captures) > 0),
            STEP_DAMAGE: damage_complete and len(captures) > 0,
        },
        "corrections": {step: step in corrections for step in workflow_state.CORRECTABLE_STEPS},
        "correction_state_error": state_error,
    }


CORRECTION_STATE_ERROR = (
    "The correction record for this inspection could not be read, so corrections and submission are paused. "
    "Nothing was changed - contact support."
)


def _state_unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=CORRECTION_STATE_ERROR)


def assert_step_editable(db: Session, inspection: SurveyorInspection, step: str) -> None:
    """A locked step changes only inside a correction the surveyor opened."""
    states = step_states(db, inspection)
    if states["locked"].get(step) and states["correction_state_error"]:
        raise _state_unavailable()
    if states["locked"].get(step) and not states["corrections"].get(step):
        raise _conflict(
            f"The {STEP_LABELS[step]} step is complete and later steps have saved work. "
            f"Open a correction for {STEP_LABELS[step]} before changing it."
        )


def open_correction(db: Session, inspection: SurveyorInspection, step: str, actor: str) -> None:
    assert_inspection_writable(inspection)
    if step not in workflow_state.CORRECTABLE_STEPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only these steps can be corrected: {', '.join(workflow_state.CORRECTABLE_STEPS)}.",
        )
    states = step_states(db, inspection)
    complete = states["inspection_complete"] if step == STEP_INSPECTION else states["damage_complete"]
    if not complete:
        raise _conflict(f"The {STEP_LABELS[step]} step is not complete, so it can be edited without a correction.")
    try:
        workflow_state.open_correction(inspection, step, actor, now_ist().isoformat())
    except (workflow_state.WorkflowStateError, OSError) as exc:
        raise _state_unavailable() from exc


def close_corrections(inspection: SurveyorInspection, steps, actor: str, reason: str, *, strict: bool = True) -> None:
    """Ends corrections. `strict` (an explicit request) reports a state
    failure; after a save that has already been committed it is logged
    instead - the corrections then stay as recorded, and submission stays
    blocked while the state is unreadable."""
    try:
        workflow_state.close_corrections(inspection, steps, actor, now_ist().isoformat(), reason)
    except (workflow_state.WorkflowStateError, OSError) as exc:
        if strict:
            raise _state_unavailable() from exc
        logger.exception("Could not close corrections for inspection %s", inspection.Inspection_ID)


def submission_review(db: Session, inspection: SurveyorInspection) -> dict | None:
    """For a submitted report: whether the saved records still meet today's
    submission rules. Older submissions (for example sample data, or
    reports submitted before surveyor captures were required) are kept
    exactly as submitted - this only reports the difference, it never
    reverts, re-verifies or resubmits anything."""
    if not inspection.Survey_Report_Submitted:
        return None
    problems = workflow_problems(db, inspection)
    return {
        "meets_current_requirements": not problems,
        "problems": problems,
        "message": (
            "Submitted. The saved records meet the current submission requirements."
            if not problems
            else "This report was submitted, but its saved records do not meet the current submission "
            "requirements. It is kept exactly as submitted and has not been re-verified."
        ),
    }


def workflow_summary(db: Session, inspection: SurveyorInspection, now: datetime | None = None) -> dict:
    """The authoritative step states the frontend displays."""
    states = step_states(db, inspection)
    submitted = bool(inspection.Survey_Report_Submitted)
    return {
        "inspection_id": inspection.Inspection_ID,
        "schedule": schedule_info(inspection, now),
        "inspection_complete": states["inspection_complete"],
        "incomplete_fields": incomplete_inspection_fields(_inspection_values(inspection)),
        "damage_required": states["damage_required"],
        "damage_count": states["damage_count"],
        "damage_complete": states["damage_complete"],
        "capture_count": states["capture_count"],
        "qualifying_photo_count": states["qualifying_photo_count"],
        "evidence_complete": states["evidence_complete"],
        "locked_steps": states["locked"],
        "open_corrections": states["corrections"],
        "correction_state_error": states["correction_state_error"],
        "submitted": submitted,
        "submission_review": submission_review(db, inspection),
        "report_available": submitted or states["evidence_complete"],
        "warnings": consistency_warnings(db, inspection),
    }


# ---------------------------------------------------------------- write locks


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def assert_inspection_writable(inspection: SurveyorInspection, now: datetime | None = None) -> None:
    """A submitted report is final, and nothing may be recorded before the
    scheduled date - for every role, since these are the only write paths."""
    if inspection.Survey_Report_Submitted:
        raise _conflict("This survey report has already been submitted, so the inspection can no longer be changed.")
    if not schedule_reached(inspection, now):
        raise _conflict(schedule_message(inspection))


def require_writable_step(
    db: Session, claim_id: str, employee_id: str, step: str, now: datetime | None = None
) -> SurveyorInspection:
    """For damage and evidence writes: the claim must be assigned to this
    surveyor, their inspection active (not submitted) and its scheduled
    date reached, every earlier step complete in saved data, and the step
    itself not locked (unless a correction is open)."""
    get_claim_assigned_to_surveyor_or_403(db, claim_id, employee_id)
    inspection = own_inspection(crud_inspection.list_by_claim(db, claim_id), employee_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No inspection exists for this claim yet.")
    assert_inspection_writable(inspection, now)

    if step in (STEP_DAMAGE, STEP_EVIDENCE):
        incomplete = incomplete_inspection_fields(_inspection_values(inspection))
        if incomplete:
            labels = ", ".join(INSPECTION_FIELD_LABELS[f] for f in incomplete)
            raise _conflict(f"Complete and save the Inspection step first. Incomplete: {labels}.")
    if step == STEP_EVIDENCE and inspection.Damage_Observed == "Yes":
        if not crud_vehicle_damage.list_by_claim(db, claim_id):
            raise _conflict("Damage was observed - save at least one vehicle damage record before adding evidence.")
    if step == STEP_DAMAGE:
        assert_step_editable(db, inspection, STEP_DAMAGE)
    return inspection
