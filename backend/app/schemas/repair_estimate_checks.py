from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class EstimateCheckOut(BaseModel):
    check: str  # e.g. "ESTIMATE_DATE" - see services/repair_estimate_checks.py
    status: str  # "FLAGGED" | "NOT_FLAGGED" | "INFO" | "UNAVAILABLE"
    value: str | None
    reference: str | None
    explanation: str


class EstimateResultOut(BaseModel):
    estimate_id: str
    garage_id: str
    estimate_date: date
    repair_estimate: Decimal
    status: str  # "POINTS_TO_REVIEW" | "NO_POINTS_FOUND" | "UNAVAILABLE"
    checks: list[EstimateCheckOut]


class QuoteComparisonOut(BaseModel):
    estimates_compared: int
    garages: int
    lowest_estimate_id: str
    lowest_amount: Decimal
    highest_estimate_id: str
    highest_amount: Decimal
    difference: Decimal
    difference_percent: float | None
    explanation: str


class ClaimRepairEstimateChecksOut(BaseModel):
    """Response for POST /officer/claims/{claim_id}/repair-estimates/check
    (Step 5.8.21 - see services/repair_estimate_checks.py and
    docs/project_documentation/REPAIR_ESTIMATE_CHECKS.md).

    Deliberately has no combined score: each check is reported on its own,
    and three of them carry no verdict at all (status "INFO")."""

    Claim_ID: str
    estimates_checked: int
    results: list[EstimateResultOut]
    quote_comparison: QuoteComparisonOut | None
    limitations: list[str]
