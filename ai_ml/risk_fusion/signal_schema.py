"""Common claim-level signal representation for the Step 5.4 risk-fusion
layer.

A "signal" is one independently-computed, pre-decision, leakage-safe
observation about a claim (e.g. "did submitted documents agree with each
other?"). The fusion engine (`fusion_engine.py`) combines several signals
into one overall risk score - but a `Signal` is deliberately NOT a
calibrated probability. Most signals here are transparent rule-derived
indicators (booleans, ratios, counts); only `fraud_screening_rule_score`
is downstream of any model/rule fit, and even that is a simple weighted
rule score (`ai_ml.baselines.rule_based_fraud`), not a neural network.

Every signal must be traceable to a real, already-existing, leakage-safe
column in the Step 5.1 claim-level dataset (see
`ai_ml.common.feature_builder.safe_feature_columns("frd_Fraud_Label", df)`)
or to Step 5.2's rule-based screener. A signal that cannot be computed for
a given claim is represented explicitly via `SignalAvailability` - never
silently defaulted to zero risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalCategory(str, Enum):
    DOCUMENT_CONSISTENCY = "DOCUMENT_CONSISTENCY"
    REPAIR_ESTIMATE_ANOMALY = "REPAIR_ESTIMATE_ANOMALY"
    EVIDENCE_DUPLICATION = "EVIDENCE_DUPLICATION"
    FRAUD_SCREENING = "FRAUD_SCREENING"
    CLAIM_PATTERN_ANOMALY = "CLAIM_PATTERN_ANOMALY"
    DOCUMENT_COMPLETENESS = "DOCUMENT_COMPLETENESS"
    INFORMATION_QUALITY = "INFORMATION_QUALITY"


class SignalDirection(str, Enum):
    """Whether a HIGHER raw value or a LOWER raw value indicates more
    risk. `Signal.signal_value` is always pre-adjusted for this (0=no
    risk contribution, 1=maximum risk contribution) - `raw_value` keeps
    the original, un-adjusted number for traceability/debugging."""

    HIGHER_IS_RISKIER = "higher_is_riskier"
    LOWER_IS_RISKIER = "lower_is_riskier"


class SignalAvailability(str, Enum):
    """Never silently fabricate a value - every signal states which of
    these four situations applies."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"          # the underlying data column is missing/None for this claim
    NOT_EVALUATED = "not_evaluated"      # this signal family was intentionally not computed (e.g. disabled)
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # data exists but is too sparse to trust (e.g. 0 documents)


@dataclass(frozen=True)
class Signal:
    """One claim-level risk signal.

    signal_value: risk contribution in [0, 1], direction-adjusted, or
        None if `availability != AVAILABLE`.
    raw_value: the original, un-adjusted measurement (e.g. a ratio, a
        count, a 0/1 flag), or None if unavailable. Kept for traceability.
    confidence: how much this individual signal should be trusted, in
        [0, 1], or None if unavailable. This is NOT the same as
        `signal_value` - a signal can be confidently "no risk" (value=0,
        confidence=1.0) or unreliably "high risk" (value=0.9,
        confidence=0.3, e.g. the fraud-screening signal - see Step 5.2/
        5.3's near-chance-level finding, reflected here as a fixed
        reliability discount).
    """

    claim_id: str
    signal_name: str
    category: SignalCategory
    signal_value: float | None
    raw_value: float | None
    signal_direction: SignalDirection
    confidence: float | None
    availability: SignalAvailability
    evidence_available: bool
    explanation: str
    source_module: str

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "signal_name": self.signal_name,
            "category": self.category.value,
            "signal_value": self.signal_value,
            "raw_value": self.raw_value,
            "signal_direction": self.signal_direction.value,
            "confidence": self.confidence,
            "availability": self.availability.value,
            "evidence_available": self.evidence_available,
            "explanation": self.explanation,
            "source_module": self.source_module,
        }
