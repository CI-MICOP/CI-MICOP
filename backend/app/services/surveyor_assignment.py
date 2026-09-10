"""Business logic for a Claims Officer/Admin assigning a Surveyor to a
claim (Step 5.8.8).

This project has no separate assignment table or column (see the
approved 15-table schema). Steps 5.8.5/5.8.6/5.8.7 already established
that "a surveyor_inspections row exists for (claim, surveyor)" IS the
project's definition of "assigned" - reused unchanged here via
crud_claim.surveyor_is_assigned. This service is what actually creates
that first row for a brand-new claim (closing the gap documented in
SURVEYOR_INSPECTION_WORKFLOW.md: a customer-created claim previously had
no way to ever get its first SurveyorInspection row, since
services/inspection_creation.py requires the surveyor to already be
"assigned" before they can self-start one).

The newly created row uses the exact same honest "not yet assessed"
sentinel values as services/inspection_creation.py - an assignment must
never look like a completed inspection.

Duplicate/reassignment handling: the real dataset's Inspection_Status
vocabulary (Assigned, Scheduled, In Progress, Completed) has no
"Cancelled"/"Reassigned" value, so an existing active assignment cannot
be safely retired without inventing a new business value (explicitly
disallowed). Therefore ANY existing active assignment (any surveyor,
Survey_Report_Submitted=False) on the claim blocks a new one, uniformly,
with 409 Conflict - this covers both "duplicate assignment to the same
surveyor" and "reassignment to a different surveyor" the same way. See
docs/project_documentation/SURVEYOR_ASSIGNMENT_WORKFLOW.md.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import authentication_user as crud_user
from app.crud import claim as crud_claim
from app.crud import surveyor_inspection as crud_inspection
from app.db_models.surveyor_inspection import SurveyorInspection
from app.schemas.surveyor import PENDING


def assign_surveyor_to_claim(db: Session, claim_id: str, surveyor_employee_id: str) -> SurveyorInspection:
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    surveyor = crud_user.get_by_employee_id(db, surveyor_employee_id)
    if surveyor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surveyor not found")

    if surveyor.Role != "Surveyor":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected account is not a Surveyor account",
        )
    if surveyor.Account_Status != "Active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected surveyor account is not active",
        )
    if not surveyor.Employee_ID:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected surveyor account has no Employee_ID on file",
        )

    existing_for_claim = crud_inspection.list_by_claim(db, claim_id)
    active_assignment = next((i for i in existing_for_claim if not i.Survey_Report_Submitted), None)
    if active_assignment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This claim already has an active surveyor assignment "
                f"(Surveyor_ID={active_assignment.Surveyor_ID}, Inspection_ID={active_assignment.Inspection_ID}). "
                "Reassignment is not supported - the existing inspection must be completed first."
            ),
        )

    assignment = SurveyorInspection(
        Inspection_ID=crud_inspection.generate_inspection_id(db),
        Claim_ID=claim.Claim_ID,
        # Derived from the looked-up, validated surveyor record - never
        # trusted as a raw client-supplied identifier beyond the lookup
        # itself, which is validated above.
        Surveyor_ID=surveyor.Employee_ID,
        Inspection_Date=date.today(),
        # The accident location already recorded on the claim - real,
        # already-known data, not a fabricated inspection finding.
        Inspection_Location=claim.Place_of_Accident,
        # Nothing has been assessed yet - identical honest "not yet
        # assessed" sentinel used by services/inspection_creation.py.
        Vehicle_Condition=PENDING,
        Damage_Observed=PENDING,
        Damage_Severity=PENDING,
        Parts_Required=0,
        Repair_Recommendation=PENDING,
        Surveyor_Comments="",
        # "Assigned" is a real value from the approved dataset - means
        # "surveyor assigned; inspection not yet completed."
        Inspection_Status="Assigned",
        Survey_Report_Submitted=False,
        Surveyor_Confidence_Score=Decimal("0.0000"),
    )

    crud_inspection.create(db, assignment)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The assignment could not be saved. No assignment was created.",
        ) from exc
    db.refresh(assignment)
    return assignment
