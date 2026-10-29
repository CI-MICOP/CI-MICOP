"""Business logic for a Claims Officer recording a claim's final
decision (Step 5.8.9).

Human-in-the-loop: this service never computes or infers a decision. It
only persists the decision the officer already selected. If a genuine
prior AI recommendation exists (a claim_decision_audit row whose
AI_Recommendation is a real value from the approved dataset's vocabulary,
not a placeholder), it is carried forward into the new audit row as
supporting information only - it never influences Final_Decision, and is
never regenerated or recomputed here. See
docs/project_documentation/CLAIMS_OFFICER_DECISION_WORKFLOW.md.

A claim's final decision, once recorded, is permanent: a claim whose
Final_Decision is already Approved/Rejected/Partially Approved rejects any
further submission with 409 Conflict, enforced here (not only in the
frontend) using a row-level lock (crud/claim.py::get_for_update) so two
concurrent requests for the same claim cannot both finalize it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import claim as crud_claim
from app.crud import claim_decision_audit as crud_audit
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.schemas.officer import DecisionCreate
from app.schemas.surveyor import PENDING
from app.services.claim_status import COMPLETED_STATUS

# Real values observed in the approved dataset
# (14_claim_decision_audit.xlsx) - anything outside this set (e.g. the
# seed data's "Review" placeholder) is not genuine AI output and must not
# be presented as a real recommendation.
REAL_AI_RECOMMENDATION_VALUES = {"Approve", "Reject", "Investigate"}

# A real dataset value (357 of 654 real rows) - the honest default when
# this decision itself does not trigger any escalation. This step does
# not implement an escalation workflow (out of scope - see the Escalations
# officer page, which remains untouched).
NOT_ESCALATED = "Not Escalated"


def record_decision_for_officer(
    db: Session, employee_id: str, claim_id: str, payload: DecisionCreate
) -> ClaimDecisionAudit:
    # Row-locked: a second, concurrent decision on this same claim blocks
    # here until this request's transaction ends, then re-reads the
    # now-committed Final_Decision below - so two requests can never both
    # pass the "not yet finalized" check for the same claim.
    claim = crud_claim.get_for_update(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    # Once a real decision is recorded, it is permanent - this is the
    # project's lock, not just a disabled button in the frontend. "Pending"
    # is the only non-final value (schemas/surveyor.py); Approved/Rejected/
    # Partially Approved (schemas/officer.py's FINAL_DECISION_VALUES) are
    # all final outcomes once persisted, with no re-decision or override
    # path, by design - there is no existing administrative correction
    # workflow in this project to preserve.
    if claim.Final_Decision != PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This claim's decision has already been finalized and cannot be changed.",
        )

    # Carry forward a genuinely-existing AI signal as supporting
    # information only - never fabricate one, never recompute one.
    previous = crud_audit.get_latest_by_claim(db, claim_id)
    if previous is not None and previous.AI_Recommendation in REAL_AI_RECOMMENDATION_VALUES:
        ai_recommendation = previous.AI_Recommendation
        ai_confidence_score = previous.AI_Confidence_Score
        human_review_required = previous.Human_Review_Required
    else:
        # No genuine AI analysis exists for this claim - honest
        # placeholders, not a fabricated recommendation. "Pending" is the
        # project's existing sentinel convention (schemas/surveyor.py);
        # Human_Review_Required=True is trivially honest here, since a
        # human is in fact reviewing it right now.
        ai_recommendation = PENDING
        ai_confidence_score = Decimal("0.0000")
        human_review_required = True

    today = date.today()

    # Claim_Status now mirrors the officer's decision, so the persisted
    # status and Final_Decision can never disagree (previously Claim_Status
    # was left untouched by every decision - see
    # CLAIMS_OFFICER_DECISION_WORKFLOW.md Section 10 - which let a claim
    # stay "Under Review" forever even once decided). Claim_Status only
    # ever has two real values in this project (services/claim_status.py):
    # "Under Review" while a decision is pending, and "Completed" once the
    # officer has finished processing the claim - whatever that decision
    # turned out to be. The differentiated outcome (Approved/Rejected/
    # Partially Approved) is Final_Decision's job, not Claim_Status's: a
    # rejected or partially approved claim is just as finally decided as an
    # approved one, and this endpoint only ever runs for one of those three
    # final values (see the FINAL_DECISION_VALUES check in schemas/
    # officer.py) - so every call here completes the claim and moves it out
    # of the active review queue alike.
    new_status = COMPLETED_STATUS

    crud_claim.update(
        db,
        claim,
        {
            "Claim_Status": new_status,
            "Final_Decision": payload.Final_Decision,
            "Decision_Reason": payload.Decision_Reason,
            "Approved_Amount": payload.Approved_Amount,
            "Decision_Date": today,
        },
    )

    audit = ClaimDecisionAudit(
        Audit_ID=crud_audit.generate_audit_id(db),
        Claim_ID=claim.Claim_ID,
        # Derived from the authenticated JWT - never trusted from the body.
        Claims_Officer_ID=employee_id,
        AI_Recommendation=ai_recommendation,
        AI_Confidence_Score=ai_confidence_score,
        Human_Review_Required=human_review_required,
        Final_Decision=payload.Final_Decision,
        Decision_Reason=payload.Decision_Reason,
        Approved_Amount=payload.Approved_Amount,
        Decision_Date=today,
        Escalation_Status=NOT_ESCALATED,
        Escalated_To=None,
        Officer_Comments=payload.Officer_Comments,
        # A new audit row was created - this reflects the audit row itself,
        # not the claim's lifecycle (Claim_Status is set directly on the
        # claim above, not inferred from Audit_Action).
        Audit_Action="Created",
        # Naive UTC, matching api/v1/routers/auth.py's Last_Login convention
        # for this project's other DateTime (not DateTime(timezone=True))
        # column.
        Audit_Timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    crud_audit.create(db, audit)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The decision could not be saved. No changes were made.",
        ) from exc

    db.refresh(claim)
    db.refresh(audit)
    return audit
