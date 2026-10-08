"""Steps 5.8.21 and 5.8.22: controlled validation corpus for the repair
estimate checks (services/repair_estimate_checks.py).

Every case below was written by hand for this validation. None of it is real
insurer data and none comes from the synthetic research dataset. Results on
this corpus describe how the six checks behave on these controlled inputs
only.

Each case records two labels:
  ideal     - what a careful Claims Officer would want: FLAGGED (worth a
              second look), NOT_FLAGGED, or UNAVAILABLE (nothing to compare)
  observed  - what the check actually returned when this corpus was first
              run (2026-10-07). test_repair_estimate_checks.py asserts the
              check still returns exactly this, so any future change shows
              up as a test failure and REPAIR_ESTIMATE_CHECKS.md must be
              updated alongside it.

The C, M and T cases were added in Step 5.8.22, when repair cost vs
estimate, estimate vs damage cost and repair days became verdict-giving.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

FLAGGED = "FLAGGED"
NOT_FLAGGED = "NOT_FLAGGED"
UNAVAILABLE = "UNAVAILABLE"

ESTIMATE_DATE = "ESTIMATE_DATE"
CLAIM_AMOUNT_RATIO = "CLAIM_AMOUNT_RATIO"
REPLACEMENT_PARTS = "REPLACEMENT_PARTS"
COST_VS_ESTIMATE = "COST_VS_ESTIMATE"
DAMAGE_COST_RATIO = "DAMAGE_COST_RATIO"
REPAIR_DAYS = "REPAIR_DAYS"


@dataclass(frozen=True)
class CorpusCase:
    case_id: str
    check: str
    inputs: dict
    ideal: str
    observed: str
    note: str


ACCIDENT = date(2026, 8, 20)

CORPUS: list[CorpusCase] = [
    # ---------------------------------------------------------------- estimate date vs accident date
    CorpusCase(
        "D01", ESTIMATE_DATE, {"estimate_date": date(2026, 8, 22), "accident_date": ACCIDENT},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Estimate two days after the accident.",
    ),
    CorpusCase(
        "D02", ESTIMATE_DATE, {"estimate_date": ACCIDENT, "accident_date": ACCIDENT},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Same-day estimate is possible.",
    ),
    CorpusCase(
        "D03", ESTIMATE_DATE, {"estimate_date": date(2026, 8, 19), "accident_date": ACCIDENT},
        ideal=FLAGGED, observed=FLAGGED, note="Estimate one day before the accident.",
    ),
    CorpusCase(
        "D04", ESTIMATE_DATE, {"estimate_date": date(2026, 8, 22), "accident_date": None},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="No accident record to compare with.",
    ),
    CorpusCase(
        "D05", ESTIMATE_DATE, {"estimate_date": date(2027, 9, 30), "accident_date": ACCIDENT},
        ideal=FLAGGED, observed=NOT_FLAGGED,
        note="Estimate 406 days after the accident: an officer would look, but the check has no upper limit "
        "(no reference for a normal delay).",
    ),
    # ---------------------------------------------------------------- estimate vs claim amount
    CorpusCase(
        "R01", CLAIM_AMOUNT_RATIO, {"repair_estimate": Decimal("40000.00"), "claim_amount": Decimal("50000.00")},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Ratio 0.80, near the reference median.",
    ),
    CorpusCase(
        "R02", CLAIM_AMOUNT_RATIO, {"repair_estimate": Decimal("150000.00"), "claim_amount": Decimal("50000.00")},
        ideal=FLAGGED, observed=FLAGGED, note="Ratio 3.00, above the reference 90th percentile (2.97).",
    ),
    CorpusCase(
        "R03", CLAIM_AMOUNT_RATIO, {"repair_estimate": Decimal("148000.00"), "claim_amount": Decimal("50000.00")},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Ratio 2.96, just inside the reference range.",
    ),
    CorpusCase(
        "R04", CLAIM_AMOUNT_RATIO, {"repair_estimate": Decimal("40000.00"), "claim_amount": Decimal("0.00")},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="No claim amount to compare with.",
    ),
    CorpusCase(
        "R05", CLAIM_AMOUNT_RATIO, {"repair_estimate": Decimal("0.00"), "claim_amount": Decimal("50000.00")},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="A zero estimate is not a low ratio; there is nothing to compare.",
    ),
    # ---------------------------------------------------------------- replaced parts vs surveyor damage records
    CorpusCase(
        "P01", REPLACEMENT_PARTS, {"replacement_parts_count": 2, "damage_actions": ["Replace"]},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Both the estimate and the surveyor say replace.",
    ),
    CorpusCase(
        "P02", REPLACEMENT_PARTS, {"replacement_parts_count": 2, "damage_actions": ["Repair", "Repair"]},
        ideal=FLAGGED, observed=FLAGGED, note="Estimate replaces parts; surveyor recorded repair only.",
    ),
    CorpusCase(
        "P03", REPLACEMENT_PARTS, {"replacement_parts_count": 0, "damage_actions": ["Repair"]},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Nothing replaced on the estimate.",
    ),
    CorpusCase(
        "P04", REPLACEMENT_PARTS, {"replacement_parts_count": 2, "damage_actions": []},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="No damage recorded yet.",
    ),
    CorpusCase(
        "P05", REPLACEMENT_PARTS, {"replacement_parts_count": 6, "damage_actions": ["Replace"]},
        ideal=FLAGGED, observed=NOT_FLAGGED,
        note="Six replaced parts against one damage record: an officer would look, but counts are deliberately "
        "not compared (one damage record can cover several parts).",
    ),
    CorpusCase(
        "P06", REPLACEMENT_PARTS, {"replacement_parts_count": 0, "damage_actions": ["Replace"]},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED,
        note="Surveyor says replace, estimate replaces nothing: unusual, but not a cost concern.",
    ),
    # ---------------------------------------------------------------- repair cost vs estimate
    CorpusCase(
        "C01", COST_VS_ESTIMATE, {"repair_cost": Decimal("52000.00"), "repair_estimate": Decimal("50000.00")},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Cost 4% above the estimate.",
    ),
    CorpusCase(
        "C02", COST_VS_ESTIMATE, {"repair_cost": Decimal("60000.00"), "repair_estimate": Decimal("50000.00")},
        ideal=FLAGGED, observed=FLAGGED, note="Cost 20% above the estimate, beyond the reference 90th percentile (15.4%).",
    ),
    CorpusCase(
        "C03", COST_VS_ESTIMATE, {"repair_cost": Decimal("45000.00"), "repair_estimate": Decimal("50000.00")},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Cost below the estimate is not a cost concern.",
    ),
    CorpusCase(
        "C04", COST_VS_ESTIMATE, {"repair_cost": Decimal("57500.00"), "repair_estimate": Decimal("50000.00")},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Cost 15.0% above, just inside the reference range.",
    ),
    CorpusCase(
        "C05", COST_VS_ESTIMATE, {"repair_cost": Decimal("52000.00"), "repair_estimate": Decimal("0.00")},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="A zero estimate gives nothing to compare with.",
    ),
    # ---------------------------------------------------------------- estimate vs surveyor's damage cost
    CorpusCase(
        "M01", DAMAGE_COST_RATIO,
        {"repair_estimate": Decimal("60000.00"), "damage_costs": [Decimal("10000.00"), Decimal("20000.00")]},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Ratio 2.00 against two damage records.",
    ),
    CorpusCase(
        "M02", DAMAGE_COST_RATIO, {"repair_estimate": Decimal("60000.00"), "damage_costs": [Decimal("10000.00")]},
        ideal=FLAGGED, observed=FLAGGED, note="Ratio 6.00, above the reference 90th percentile (5.34).",
    ),
    CorpusCase(
        "M03", DAMAGE_COST_RATIO, {"repair_estimate": Decimal("53000.00"), "damage_costs": [Decimal("10000.00")]},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Ratio 5.30, just inside the reference range.",
    ),
    CorpusCase(
        "M04", DAMAGE_COST_RATIO, {"repair_estimate": Decimal("60000.00"), "damage_costs": []},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="No damage recorded yet.",
    ),
    CorpusCase(
        "M05", DAMAGE_COST_RATIO, {"repair_estimate": Decimal("150000.00"), "damage_costs": [Decimal("50000.00")]},
        ideal=FLAGGED, observed=NOT_FLAGGED,
        note="Estimate three times the surveyor's damage cost: an officer would look, but the reference range is "
        "wide (5.34) because the two amounts are unrelated in the reference dataset.",
    ),
    # ---------------------------------------------------------------- repair days
    CorpusCase(
        "T01", REPAIR_DAYS, {"estimated_days": 7, "actual_days": 12},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="5 days over.",
    ),
    CorpusCase(
        "T02", REPAIR_DAYS, {"estimated_days": 7, "actual_days": 20},
        ideal=FLAGGED, observed=FLAGGED, note="13 days over, beyond the reference 90th percentile (12).",
    ),
    CorpusCase(
        "T03", REPAIR_DAYS, {"estimated_days": 7, "actual_days": 19},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="12 days over, just inside the reference range.",
    ),
    CorpusCase(
        "T04", REPAIR_DAYS, {"estimated_days": 10, "actual_days": 6},
        ideal=NOT_FLAGGED, observed=NOT_FLAGGED, note="Finished early.",
    ),
    CorpusCase(
        "T05", REPAIR_DAYS, {"estimated_days": 7, "actual_days": 0},
        ideal=UNAVAILABLE, observed=UNAVAILABLE, note="Actual days not recorded yet.",
    ),
    CorpusCase(
        "T06", REPAIR_DAYS, {"estimated_days": 2, "actual_days": 12},
        ideal=FLAGGED, observed=NOT_FLAGGED,
        note="Six times the estimated days: an officer would look, but the check measures days over (10), "
        "not how many times longer.",
    ),
]
