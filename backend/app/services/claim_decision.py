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
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

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

    # Claim.Final_Decision/Decision_Reason/Approved_Amount/Decision_Date
    # already exist on the approved schema - persisted directly, per this
    # task's instruction not to invent a new claim lifecycle. Claim_Status
    # is deliberately left untouched: the approved dataset shows no
    # discoverable correlation between Claim_Status and Final_Decision
    # (near-uniform crosstab across all 5 status x 3 decision
    # combinations), so there is no existing state-machine rule to reuse.
    crud_claim.update(
        db,
        claim,
        {
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
        # A new audit row was created - not overloading this with a claim-
        # lifecycle "Closed" semantic that this step does not otherwise
        # manage (Claim_Status is untouched, see above).
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
