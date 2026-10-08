"""Steps 5.8.21 and 5.8.22: repair estimate checks (roadmap item 10).

This is NOT fraud detection, NOT a risk score, and NOT an automatic claim
decision. It answers one narrow question for a Claims Officer: is there
anything in this claim's repair estimate(s) worth a second look when it is
set against the claim's own other records?

Method (no AI model - see docs/project_documentation/REPAIR_ESTIMATE_CHECKS.md):
plain comparisons between a repair_estimates row and the claim, accident
and vehicle_damage rows of the same claim.

All six checks can raise a point for review. None uses a guessed limit:
  - ESTIMATE_DATE:      an estimate dated before the accident (a date order
                        that cannot be right);
  - REPLACEMENT_PARTS:  the estimate lists replaced parts while every damage
                        record the surveyor made says "Repair";
  - CLAIM_AMOUNT_RATIO: estimate / claim amount;
  - COST_VS_ESTIMATE:   repair cost / estimate;
  - DAMAGE_COST_RATIO:  estimate / the damage cost the surveyor recorded;
  - REPAIR_DAYS:        actual repair days minus estimated repair days.
The last four raise a point when the value is above the 90th percentile of
the approved 654-claim reference dataset. CLAIM_AMOUNT_RATIO uses the
reference ai_pipeline.py already had; the other three references were added
in Step 5.8.22 (ai_ml/experiments/compute_repair_estimate_reference.py).

When a claim has two or more estimates, their amounts are also set side by
side (lowest, highest, gap) without a verdict: every reference claim has
exactly one estimate, so there is no reference for a normal gap.

Deliberately NOT checked: Repair_Cost against Parts + Labour + Painting.
SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md (Section 8) found these never reconcile
in the approved dataset, so any tolerance would be an invented rule.

Read-time only: this module never writes to the database (it does not set
RepairEstimate.Excessive_Claim_Amount_Indicator or Estimate_Anomaly_Score),
never touches Final_Decision, Approved_Amount or claim_decision_audit, and
is not wired into ai_pipeline.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.crud import accident as crud_accident
from app.crud import repair_estimate as crud_repair_estimate
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.claim import Claim
from app.db_models.repair_estimate import RepairEstimate
from app.services.ai_pipeline import REPAIR_RATIO_P50, REPAIR_RATIO_P90

STATUS_FLAGGED = "FLAGGED"
STATUS_NOT_FLAGGED = "NOT_FLAGGED"
STATUS_INFO = "INFO"
STATUS_UNAVAILABLE = "UNAVAILABLE"

ESTIMATE_POINTS_TO_REVIEW = "POINTS_TO_REVIEW"
ESTIMATE_NO_POINTS_FOUND = "NO_POINTS_FOUND"
ESTIMATE_UNAVAILABLE = "UNAVAILABLE"

CHECK_ESTIMATE_DATE = "ESTIMATE_DATE"
CHECK_CLAIM_AMOUNT_RATIO = "CLAIM_AMOUNT_RATIO"
CHECK_REPLACEMENT_PARTS = "REPLACEMENT_PARTS"
CHECK_COST_VS_ESTIMATE = "COST_VS_ESTIMATE"
CHECK_DAMAGE_COST_RATIO = "DAMAGE_COST_RATIO"
CHECK_REPAIR_DAYS = "REPAIR_DAYS"

REPLACE = "Replace"

# Reference percentiles computed ONCE from the approved 654-claim reference
# dataset (ai_ml/datasets/CI_MICOP_15_Tables_Complete/{08_vehicle_damage,
# 09_repair_estimates}.xlsx) by
# ai_ml/experiments/compute_repair_estimate_reference.py - the median and
# the 90th percentile, as for REPAIR_RATIO_P50 / REPAIR_RATIO_P90. Never
# recomputed from live data.
COST_RATIO_P50 = 1.0038072427048264  # Repair_Cost / Repair_Estimate
COST_RATIO_P90 = 1.1541645403053924
DAMAGE_COST_RATIO_P50 = 1.4154223607224274  # Repair_Estimate / total Estimated_Damage_Cost
DAMAGE_COST_RATIO_P90 = 5.343173251552042
EXTRA_REPAIR_DAYS_P50 = 3  # Actual_Repair_Days - Estimated_Repair_Days
EXTRA_REPAIR_DAYS_P90 = 12

_NO_REFERENCE = "No reference range is available for this, so it is shown for information only."

_STANDARD_LIMITATIONS = [
    "These are plain comparisons between this claim's own records, not an AI model. A point for review is "
    "a reason to look closer, not a finding that anything is wrong.",
    "Four checks use a reference range: estimate against claim amount, repair cost against estimate, estimate "
    "against the surveyor's damage cost, and repair days. The ranges come from the synthetic 654-claim research "
    "dataset, not from real insurer claims. About 1 in 10 of those reference claims is above each range.",
    "In that dataset the surveyor's damage cost is not related to the estimate, and the estimated repair days "
    "are not related to the actual days. Those two ranges show what is common there, not what is expected.",
    "Part counts are not compared number for number, because one damage record can cover several parts.",
    "The cost breakdown (parts + labour + painting) is not checked against the repair cost - the reference "
    "dataset shows these do not reconcile.",
]


@dataclass
class EstimateCheck:
    check: str
    status: str
    value: str | None
    reference: str | None
    explanation: str


@dataclass
class EstimateResult:
    estimate_id: str
    garage_id: str
    estimate_date: date
    repair_estimate: Decimal
    status: str
    checks: list[EstimateCheck]


@dataclass
class QuoteComparison:
    estimates_compared: int
    garages: int
    lowest_estimate_id: str
    lowest_amount: Decimal
    highest_estimate_id: str
    highest_amount: Decimal
    difference: Decimal
    difference_percent: float | None
    explanation: str


@dataclass
class ClaimRepairEstimateChecks:
    claim_id: str
    estimates_checked: int
    results: list[EstimateResult]
    quote_comparison: QuoteComparison | None
    limitations: list[str]


def _inr(amount: Decimal) -> str:
    return f"INR {amount:,.2f}"


def check_estimate_date(estimate_date: date, accident_date: date | None) -> EstimateCheck:
    if accident_date is None:
        return EstimateCheck(
            CHECK_ESTIMATE_DATE, STATUS_UNAVAILABLE, None, None,
            "This claim has no accident record, so the estimate date cannot be compared with the accident date.",
        )
    days = (estimate_date - accident_date).days
    value, reference = estimate_date.isoformat(), f"accident date {accident_date.isoformat()}"
    if days < 0:
        return EstimateCheck(
            CHECK_ESTIMATE_DATE, STATUS_FLAGGED, value, reference,
            f"The estimate is dated {-days} day(s) before the recorded accident date. A repair estimate for "
            "this accident cannot be earlier than the accident - check both dates.",
        )
    when = "on the recorded accident date" if days == 0 else f"{days} day(s) after the recorded accident date"
    return EstimateCheck(CHECK_ESTIMATE_DATE, STATUS_NOT_FLAGGED, value, reference, f"The estimate is dated {when}.")


def check_claim_amount_ratio(repair_estimate: Decimal, claim_amount: Decimal | None) -> EstimateCheck:
    if not claim_amount:
        return EstimateCheck(
            CHECK_CLAIM_AMOUNT_RATIO, STATUS_UNAVAILABLE, None, None,
            "The claim amount is not available, so the estimate cannot be compared with it.",
        )
    if not repair_estimate:
        return EstimateCheck(
            CHECK_CLAIM_AMOUNT_RATIO, STATUS_UNAVAILABLE, None, None,
            "The repair estimate amount is zero, so there is nothing to compare with the claim amount.",
        )
    ratio = float(repair_estimate) / float(claim_amount)
    value = f"{ratio:.2f}"
    reference = f"90% of reference claims at or below {REPAIR_RATIO_P90:.2f} (median {REPAIR_RATIO_P50:.2f})"
    summary = f"The repair estimate ({_inr(repair_estimate)}) is {ratio:.2f} times the claim amount ({_inr(claim_amount)})."
    if ratio > REPAIR_RATIO_P90:
        return EstimateCheck(
            CHECK_CLAIM_AMOUNT_RATIO, STATUS_FLAGGED, value, reference,
            f"{summary} That is higher than 90% of the reference claims (at or below {REPAIR_RATIO_P90:.2f}). "
            "There can be valid reasons, such as a partial claim.",
        )
    return EstimateCheck(
        CHECK_CLAIM_AMOUNT_RATIO, STATUS_NOT_FLAGGED, value, reference,
        f"{summary} That is within the range of 90% of the reference claims (at or below {REPAIR_RATIO_P90:.2f}).",
    )


def check_replacement_parts(replacement_parts_count: int, damage_actions: list[str]) -> EstimateCheck:
    """damage_actions: the Repair_or_Replace value of each vehicle_damage row on the claim."""
    if not damage_actions:
        return EstimateCheck(
            CHECK_REPLACEMENT_PARTS, STATUS_UNAVAILABLE, None, None,
            "No vehicle damage has been recorded for this claim, so the estimate's parts cannot be compared with it.",
        )
    replace_records = sum(1 for action in damage_actions if action == REPLACE)
    value = f"{replacement_parts_count} replaced part(s) on the estimate"
    reference = f"{replace_records} of {len(damage_actions)} damage record(s) marked 'Replace'"
    if replacement_parts_count > 0 and replace_records == 0:
        return EstimateCheck(
            CHECK_REPLACEMENT_PARTS, STATUS_FLAGGED, value, reference,
            f"The estimate lists {replacement_parts_count} replaced part(s), but every damage record the surveyor "
            f"made for this claim ({len(damage_actions)}) says 'Repair'. Check whether replacement is needed.",
        )
    if replacement_parts_count == 0:
        return EstimateCheck(
            CHECK_REPLACEMENT_PARTS, STATUS_NOT_FLAGGED, value, reference, "The estimate lists no replaced parts."
        )
    return EstimateCheck(
        CHECK_REPLACEMENT_PARTS, STATUS_NOT_FLAGGED, value, reference,
        "The estimate lists replaced parts and the surveyor also recorded damage that needs replacement. "
        "The part counts themselves are not compared.",
    )


def check_cost_vs_estimate(repair_cost: Decimal, repair_estimate: Decimal) -> EstimateCheck:
    if not repair_estimate:
        return EstimateCheck(
            CHECK_COST_VS_ESTIMATE, STATUS_UNAVAILABLE, None, None,
            "The repair estimate amount is zero, so the repair cost cannot be compared with it.",
        )
    difference = repair_cost - repair_estimate
    percent = abs(float(difference)) / float(repair_estimate) * 100
    if difference == 0:
        position = "equal to"
    else:
        position = f"{_inr(abs(difference))} ({percent:.1f}%) {'above' if difference > 0 else 'below'}"
    limit_percent = (COST_RATIO_P90 - 1) * 100
    value = _inr(repair_cost)
    reference = (
        f"repair estimate {_inr(repair_estimate)}; 90% of reference claims at most {limit_percent:.1f}% above "
        "their estimate"
    )
    summary = f"The repair cost ({_inr(repair_cost)}) is {position} the repair estimate ({_inr(repair_estimate)})."
    if float(repair_cost) / float(repair_estimate) > COST_RATIO_P90:
        return EstimateCheck(
            CHECK_COST_VS_ESTIMATE, STATUS_FLAGGED, value, reference,
            f"{summary} That is further above the estimate than 90% of the reference claims (at most "
            f"{limit_percent:.1f}% above). There can be valid reasons, such as damage found during the repair.",
        )
    return EstimateCheck(
        CHECK_COST_VS_ESTIMATE, STATUS_NOT_FLAGGED, value, reference,
        f"{summary} That is within the range of 90% of the reference claims (at most {limit_percent:.1f}% above).",
    )


def check_damage_cost_ratio(repair_estimate: Decimal, damage_costs: list[Decimal]) -> EstimateCheck:
    """damage_costs: the Estimated_Damage_Cost of each vehicle_damage row on the claim."""
    total = sum(damage_costs, Decimal("0"))
    if not damage_costs or not total:
        return EstimateCheck(
            CHECK_DAMAGE_COST_RATIO, STATUS_UNAVAILABLE, None, None,
            "No damage cost has been recorded by the surveyor for this claim, so the estimate cannot be compared with it.",
        )
    if not repair_estimate:
        return EstimateCheck(
            CHECK_DAMAGE_COST_RATIO, STATUS_UNAVAILABLE, None, None,
            "The repair estimate amount is zero, so there is nothing to compare with the surveyor's damage cost.",
        )
    ratio = float(repair_estimate) / float(total)
    value = f"{ratio:.2f}"
    reference = (
        f"surveyor's damage cost {_inr(total)} across {len(damage_costs)} record(s); 90% of reference claims at or "
        f"below {DAMAGE_COST_RATIO_P90:.2f} (median {DAMAGE_COST_RATIO_P50:.2f})"
    )
    summary = (
        f"The repair estimate ({_inr(repair_estimate)}) is {ratio:.2f} times the damage cost the surveyor recorded "
        f"({_inr(total)})."
    )
    if ratio > DAMAGE_COST_RATIO_P90:
        return EstimateCheck(
            CHECK_DAMAGE_COST_RATIO, STATUS_FLAGGED, value, reference,
            f"{summary} That is higher than 90% of the reference claims (at or below {DAMAGE_COST_RATIO_P90:.2f}). "
            "There can be valid reasons, such as damage the surveyor has not recorded yet.",
        )
    return EstimateCheck(
        CHECK_DAMAGE_COST_RATIO, STATUS_NOT_FLAGGED, value, reference,
        f"{summary} That is within the range of 90% of the reference claims (at or below {DAMAGE_COST_RATIO_P90:.2f}).",
    )


def check_repair_days(estimated_days: int, actual_days: int) -> EstimateCheck:
    # Actual_Repair_Days = 0 means "not yet available" (repair_estimate_creation.py).
    if not actual_days:
        return EstimateCheck(
            CHECK_REPAIR_DAYS, STATUS_UNAVAILABLE, None, None, "The actual repair days have not been recorded yet."
        )
    if not estimated_days:
        return EstimateCheck(
            CHECK_REPAIR_DAYS, STATUS_UNAVAILABLE, None, None,
            "The estimated repair days are recorded as zero, so the actual days cannot be compared with them.",
        )
    difference = actual_days - estimated_days
    if difference == 0:
        position = "the same as estimated"
    else:
        position = f"{abs(difference)} day(s) {'more' if difference > 0 else 'fewer'} than estimated"
    value = f"{actual_days} day(s)"
    reference = (
        f"{estimated_days} day(s) estimated; 90% of reference claims at most {EXTRA_REPAIR_DAYS_P90} day(s) over "
        f"(median {EXTRA_REPAIR_DAYS_P50})"
    )
    summary = f"The repair took {actual_days} day(s) against {estimated_days} estimated - {position}."
    if difference > EXTRA_REPAIR_DAYS_P90:
        return EstimateCheck(
            CHECK_REPAIR_DAYS, STATUS_FLAGGED, value, reference,
            f"{summary} That is a longer overrun than 90% of the reference claims (at most {EXTRA_REPAIR_DAYS_P90} "
            "day(s) over). There can be valid reasons, such as waiting for parts.",
        )
    return EstimateCheck(
        CHECK_REPAIR_DAYS, STATUS_NOT_FLAGGED, value, reference,
        f"{summary} That is within the range of 90% of the reference claims (at most {EXTRA_REPAIR_DAYS_P90} day(s) over).",
    )


def estimate_status(checks: list[EstimateCheck]) -> str:
    statuses = {c.status for c in checks}
    if STATUS_FLAGGED in statuses:
        return ESTIMATE_POINTS_TO_REVIEW
    if STATUS_NOT_FLAGGED in statuses:
        return ESTIMATE_NO_POINTS_FOUND
    return ESTIMATE_UNAVAILABLE


def compare_quotes(quotes: list[tuple[str, str, Decimal]]) -> QuoteComparison | None:
    """quotes: (Estimate_ID, Garage_ID, Repair_Estimate) per estimate on the
    claim. None when there are fewer than two to compare."""
    if len(quotes) < 2:
        return None
    lowest = min(quotes, key=lambda q: q[2])
    highest = max(quotes, key=lambda q: q[2])
    difference = highest[2] - lowest[2]
    percent = round(float(difference) / float(lowest[2]) * 100, 1) if lowest[2] else None
    garages = len({q[1] for q in quotes})
    gap = "The amounts are equal." if difference == 0 else (
        f"The highest is {_inr(difference)}" + (f" ({percent:.1f}%)" if percent is not None else "") + " above the lowest."
    )
    return QuoteComparison(
        estimates_compared=len(quotes),
        garages=garages,
        lowest_estimate_id=lowest[0],
        lowest_amount=lowest[2],
        highest_estimate_id=highest[0],
        highest_amount=highest[2],
        difference=difference,
        difference_percent=percent,
        explanation=(
            f"{len(quotes)} estimates are on file from {garages} garage(s): lowest {_inr(lowest[2])} ({lowest[0]}), "
            f"highest {_inr(highest[2])} ({highest[0]}). {gap} {_NO_REFERENCE}"
        ),
    )


def assess_estimate(
    estimate: RepairEstimate,
    claim_amount: Decimal | None,
    accident_date: date | None,
    damage_actions: list[str],
    damage_costs: list[Decimal],
) -> EstimateResult:
    checks = [
        check_estimate_date(estimate.Estimate_Date, accident_date),
        check_claim_amount_ratio(estimate.Repair_Estimate, claim_amount),
        check_replacement_parts(estimate.Replacement_Parts_Count, damage_actions),
        check_cost_vs_estimate(estimate.Repair_Cost, estimate.Repair_Estimate),
        check_damage_cost_ratio(estimate.Repair_Estimate, damage_costs),
        check_repair_days(estimate.Estimated_Repair_Days, estimate.Actual_Repair_Days),
    ]
    return EstimateResult(
        estimate_id=estimate.Estimate_ID,
        garage_id=estimate.Garage_ID,
        estimate_date=estimate.Estimate_Date,
        repair_estimate=estimate.Repair_Estimate,
        status=estimate_status(checks),
        checks=checks,
    )


def check_claim_repair_estimates(db: Session, claim: Claim) -> ClaimRepairEstimateChecks:
    """Entry point routers should call. Only reads this claim's own
    repair_estimates, vehicle_damage and accidents rows. Read-only."""
    estimates = crud_repair_estimate.list_by_claim(db, claim.Claim_ID)
    damage = crud_vehicle_damage.list_by_claim(db, claim.Claim_ID)
    accidents = crud_accident.list_by_claim(db, claim.Claim_ID)
    accident_date = min((a.Accident_Date for a in accidents), default=None)
    damage_actions = [d.Repair_or_Replace for d in damage]
    damage_costs = [d.Estimated_Damage_Cost for d in damage]
    return ClaimRepairEstimateChecks(
        claim_id=claim.Claim_ID,
        estimates_checked=len(estimates),
        results=[assess_estimate(e, claim.Claim_Amount, accident_date, damage_actions, damage_costs) for e in estimates],
        quote_comparison=compare_quotes([(e.Estimate_ID, e.Garage_ID, e.Repair_Estimate) for e in estimates]),
        limitations=list(_STANDARD_LIMITATIONS),
    )
