"""Business logic for a Surveyor starting a new inspection.

Mirrors the existing services/claim_creation.py and
services/document_upload.py pattern: the router stays a thin HTTP
wrapper, and the actual rules - the assignment check, duplicate-active
prevention, ID generation, and the honest "not yet assessed" initial
values - live here.

Assignment model: the approved schema has no separate assignment table
or column. This project's existing code (app/crud/claim.py's
surveyor_is_assigned, reused unchanged by services/claim_access.py's
get_claim_or_403) already treats "a SurveyorInspection row exists for
(claim, surveyor)" as the definition of "this surveyor is assigned to
this claim." This service reuses that exact same definition rather than
inventing a new one. See
docs/project_documentation/SURVEYOR_INSPECTION_WORKFLOW.md for the full
rationale and the resulting limitation for brand-new claims (which have
no inspection from anyone yet, and therefore no assignment under this
model - see that document rather than working around it here).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import claim as crud_claim
from app.crud import surveyor_inspection as crud_inspection
from app.db_models.surveyor_inspection import SurveyorInspection
from app.schemas.surveyor import PENDING, SurveyorInspectionCreate


def create_inspection_for_surveyor(
    db: Session, employee_id: str, payload: SurveyorInspectionCreate
) -> SurveyorInspection:
    claim = crud_claim.get(db, payload.Claim_ID)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    if not crud_claim.surveyor_is_assigned(db, payload.Claim_ID, employee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this claim",
        )

    existing_for_claim = crud_inspection.list_by_claim(db, payload.Claim_ID)
    has_active_inspection = any(
        i.Surveyor_ID == employee_id and not i.Survey_Report_Submitted for i in existing_for_claim
    )
    if has_active_inspection:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active (not yet submitted) inspection for this claim. "
            "Update that inspection instead of starting a new one.",
        )

    inspection = SurveyorInspection(
        Inspection_ID=crud_inspection.generate_inspection_id(db),
        Claim_ID=payload.Claim_ID,
        Surveyor_ID=employee_id,
        Inspection_Date=date.today(),
        # The accident location already recorded on the claim - real,
        # already-known data, not a fabricated inspection finding.
        Inspection_Location=claim.Place_of_Accident,
        # Nothing has been assessed yet - these are the honest "not yet
        # assessed" sentinel, never a real conclusion (see schemas/surveyor.py).
        Vehicle_Condition=PENDING,
        Damage_Observed=PENDING,
        Damage_Severity=PENDING,
        Parts_Required=0,
        Repair_Recommendation=PENDING,
        Surveyor_Comments="",
        # "Assigned" is a real value from the approved dataset - the
        # natural initial status for a just-created inspection.
        Inspection_Status="Assigned",
        Survey_Report_Submitted=False,
        Surveyor_Confidence_Score=Decimal("0.0000"),
    )

    crud_inspection.create(db, inspection)
    db.commit()
    db.refresh(inspection)
    return inspection
