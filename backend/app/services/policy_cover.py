"""Was the claim's policy in force on the accident date?

Deterministic date comparison - not AI, not a decision. It reads the
policy's own recorded period (policies.Policy_Start_Date / Policy_End_Date)
and the accident record's date (accidents.Accident_Date); it never assumes
a policy length. Both ends of the period are inclusive.

What it cannot see: the schema records ONE period per policy. A policy whose
own-damage and third-party sections run for different periods (for example
a bundled long-term third-party cover) is checked against that single
period, and the result says so.

Read-time only: never writes to the database. Not exposed through an
endpoint by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.crud import policy as crud_policy
from app.db_models.accident import Accident
from app.db_models.claim import Claim

STATUS_COVERED = "COVERED"
STATUS_EXPIRED = "EXPIRED"  # accident after the recorded end date
STATUS_NOT_STARTED = "NOT_STARTED"  # accident before the recorded start date
STATUS_CANNOT_RUN = "CANNOT_RUN"  # a required date or record is missing

SINGLE_PERIOD_LIMITATION = (
    "The policy record holds one period; separate own-damage and third-party periods are not recorded, "
    "so both are taken to be this period."
)


@dataclass
class PolicyCoverResult:
    status: str
    accident_date: date | None
    policy_start: date | None
    policy_end: date | None
    explanation: str
    limitations: list[str]


def check_cover(accident_date: date | None, policy_start: date | None, policy_end: date | None) -> PolicyCoverResult:
    base = dict(accident_date=accident_date, policy_start=policy_start, policy_end=policy_end,
                limitations=[SINGLE_PERIOD_LIMITATION])
    if accident_date is None or policy_start is None or policy_end is None:
        missing = [name for name, value in (("accident date", accident_date), ("policy start date", policy_start),
                                            ("policy end date", policy_end)) if value is None]
        return PolicyCoverResult(status=STATUS_CANNOT_RUN, explanation=(
            "Policy cover could not be checked because the " + " and ".join(missing) + " is not recorded."), **base)
    if policy_end < policy_start:
        return PolicyCoverResult(status=STATUS_CANNOT_RUN, explanation=(
            f"Policy cover could not be checked: the recorded end date {policy_end.isoformat()} is before the "
            f"start date {policy_start.isoformat()}."), **base)
    if accident_date > policy_end:
        return PolicyCoverResult(status=STATUS_EXPIRED, explanation=(
            f"The accident date {accident_date.isoformat()} is after the policy ended on "
            f"{policy_end.isoformat()}. Needs officer review."), **base)
    if accident_date < policy_start:
        return PolicyCoverResult(status=STATUS_NOT_STARTED, explanation=(
            f"The accident date {accident_date.isoformat()} is before the policy started on "
            f"{policy_start.isoformat()}. Needs officer review."), **base)
    return PolicyCoverResult(status=STATUS_COVERED, explanation=(
        f"The accident date {accident_date.isoformat()} is within the policy period "
        f"{policy_start.isoformat()} to {policy_end.isoformat()}."), **base)


def check_claim_policy_cover(db: Session, claim: Claim) -> PolicyCoverResult:
    """Entry point for a claim. Read-only."""
    accident = db.query(Accident).filter(Accident.Claim_ID == claim.Claim_ID).order_by(Accident.Accident_ID).first()
    policy = crud_policy.get(db, claim.Policy_ID)
    return check_cover(
        accident.Accident_Date if accident else None,
        policy.Policy_Start_Date if policy else None,
        policy.Policy_End_Date if policy else None,
    )
