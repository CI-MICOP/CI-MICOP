"""Standardized reason codes for the risk-fusion layer (Part E).

Reuses the 4 existing Step 5.2 reason codes
(`ai_ml.explainability.reason_codes.REASON_CODES`) unchanged and adds
only the 4 new codes this step's design explicitly calls for. Every
entry is a decision-support statement ("AI risk signal: ...") - never a
verdict ("AI detected fraud", "confirmed").
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_ml.explainability.reason_codes import REASON_CODES as BASE_REASON_CODES
from ai_ml.risk_fusion.signal_schema import Signal, SignalAvailability


@dataclass(frozen=True)
class ReasonCodeDefinition:
    code: str
    title: str
    explanation: str
    severity: str  # "LOW" | "MEDIUM" | "HIGH"
    source_module: str

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "explanation": self.explanation,
            "severity": self.severity,
            "source_module": self.source_module,
        }


_NEW_REASON_CODES: dict[str, ReasonCodeDefinition] = {
    "MISSING_EVIDENCE": ReasonCodeDefinition(
        code="MISSING_EVIDENCE",
        title="Missing supporting evidence",
        explanation="One or more expected pieces of evidence (documents, photos, or evidence items) were not available for this claim, so the related risk signal could not be evaluated.",
        severity="MEDIUM",
        source_module="ai_ml.risk_fusion.signal_builder",
    ),
    "MULTI_SIGNAL_DISAGREEMENT": ReasonCodeDefinition(
        code="MULTI_SIGNAL_DISAGREEMENT",
        title="Risk signals disagree",
        explanation="The available risk signals for this claim do not agree with each other - some indicate elevated risk while others do not, reducing confidence in the overall risk score.",
        severity="MEDIUM",
        source_module="ai_ml.risk_fusion.uncertainty",
    ),
    "LOW_MODEL_CONFIDENCE": ReasonCodeDefinition(
        code="LOW_MODEL_CONFIDENCE",
        title="Underlying screening signal has limited reliability",
        explanation="This claim's risk score includes a model/rule-based screening signal that prior validation (Step 5.2/5.3) found performs only marginally above chance - treat the associated risk contribution with caution.",
        severity="MEDIUM",
        source_module="ai_ml.risk_fusion.uncertainty",
    ),
    "INSUFFICIENT_DATA": ReasonCodeDefinition(
        code="INSUFFICIENT_DATA",
        title="Insufficient data to assess this claim reliably",
        explanation="Too few risk signals were available for this claim to produce a trustworthy overall risk assessment. This claim should not be treated as low-risk by default.",
        severity="HIGH",
        source_module="ai_ml.risk_fusion.uncertainty",
    ),
}

# The 4 Step 5.2 codes, wrapped in the same ReasonCodeDefinition shape so
# callers can use one interface regardless of which step introduced a
# code. Severity is a new field Step 5.2 did not need - assigned here by
# reading the same descriptions Step 5.2 already used.
_BASE_AS_DEFINITIONS: dict[str, ReasonCodeDefinition] = {
    "DOCUMENT_INCONSISTENCY": ReasonCodeDefinition(
        code="DOCUMENT_INCONSISTENCY", title="Document inconsistency detected",
        explanation=BASE_REASON_CODES["DOCUMENT_INCONSISTENCY"], severity="MEDIUM",
        source_module="ai_ml.explainability.reason_codes",
    ),
    "REPAIR_ESTIMATE_ANOMALY": ReasonCodeDefinition(
        code="REPAIR_ESTIMATE_ANOMALY", title="Repair estimate anomaly detected",
        explanation=BASE_REASON_CODES["REPAIR_ESTIMATE_ANOMALY"], severity="MEDIUM",
        source_module="ai_ml.explainability.reason_codes",
    ),
    "DUPLICATE_EVIDENCE": ReasonCodeDefinition(
        code="DUPLICATE_EVIDENCE", title="Duplicate evidence detected",
        explanation=BASE_REASON_CODES["DUPLICATE_EVIDENCE"], severity="HIGH",
        source_module="ai_ml.explainability.reason_codes",
    ),
    "UNUSUAL_CLAIM_PATTERN": ReasonCodeDefinition(
        code="UNUSUAL_CLAIM_PATTERN", title="Unusual claim pattern detected",
        explanation=BASE_REASON_CODES["UNUSUAL_CLAIM_PATTERN"], severity="LOW",
        source_module="ai_ml.explainability.reason_codes",
    ),
}

RISK_FUSION_REASON_CODES: dict[str, ReasonCodeDefinition] = {**_BASE_AS_DEFINITIONS, **_NEW_REASON_CODES}

_SIGNAL_NAME_TO_CODE = {
    "document_consistency_mismatch": "DOCUMENT_INCONSISTENCY",
    "repair_estimate_anomaly": "REPAIR_ESTIMATE_ANOMALY",
    "evidence_duplication": "DUPLICATE_EVIDENCE",
    "fraud_screening_rule_score": "UNUSUAL_CLAIM_PATTERN",
    "claim_pattern_anomaly": "UNUSUAL_CLAIM_PATTERN",
    "document_completeness": "MISSING_EVIDENCE",
    "information_quality": "INSUFFICIENT_DATA",
}

_RISK_TRIGGER_THRESHOLD = 0.5


def describe(code: str) -> dict:
    definition = RISK_FUSION_REASON_CODES.get(code)
    if definition is None:
        return ReasonCodeDefinition(
            code=code, title="Unclassified signal", explanation="This claim shows a pattern the screening process flagged for review.",
            severity="LOW", source_module="ai_ml.risk_fusion.reason_codes",
        ).to_dict()
    return definition.to_dict()


def reason_codes_for_signals(signals: list[Signal], risk_threshold: float = _RISK_TRIGGER_THRESHOLD) -> list[str]:
    """Reason codes for signals that actually fired (value >= threshold),
    most-explanatory-first, followed by any evidence-related codes for
    signals that could not be evaluated at all."""
    codes: list[str] = []
    for signal in signals:
        if signal.availability == SignalAvailability.AVAILABLE and signal.signal_value is not None and signal.signal_value >= risk_threshold:
            code = _SIGNAL_NAME_TO_CODE.get(signal.signal_name, "UNUSUAL_CLAIM_PATTERN")
            if code not in codes:
                codes.append(code)
    for signal in signals:
        if signal.availability != SignalAvailability.AVAILABLE and "MISSING_EVIDENCE" not in codes:
            codes.append("MISSING_EVIDENCE")
            break
    return codes


def reason_codes_for_claim(signals: list[Signal], confidence_band: str, uncertainty_reasons: list[str], risk_threshold: float = _RISK_TRIGGER_THRESHOLD) -> list[str]:
    """Combines the signal-triggered codes above with the uncertainty-
    layer-triggered codes (`MULTI_SIGNAL_DISAGREEMENT`, `LOW_MODEL_CONFIDENCE`,
    `INSUFFICIENT_DATA`), so those three codes are actually reachable
    rather than defined-but-unused. `confidence_band` and
    `uncertainty_reasons` come from `ai_ml.risk_fusion.uncertainty.compute_uncertainty`."""
    codes = reason_codes_for_signals(signals, risk_threshold)

    if any("disagree" in r for r in uncertainty_reasons) and "MULTI_SIGNAL_DISAGREEMENT" not in codes:
        codes.append("MULTI_SIGNAL_DISAGREEMENT")

    model_derived_flagged = any("model/rule-screening-derived" in r for r in uncertainty_reasons)
    if model_derived_flagged and confidence_band in {"LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE"} and "LOW_MODEL_CONFIDENCE" not in codes:
        codes.append("LOW_MODEL_CONFIDENCE")

    if confidence_band == "INSUFFICIENT_EVIDENCE" and "INSUFFICIENT_DATA" not in codes:
        codes.append("INSUFFICIENT_DATA")

    return codes


def build_officer_explanation(reason_codes: list[str]) -> list[dict]:
    """Officer-facing wording - decision-support phrasing only, e.g.
    "AI risk signal: repair estimate anomaly detected", never a verdict
    like "AI detected fraud"."""
    explanations = []
    for code in reason_codes:
        definition = describe(code)
        explanations.append({
            "code": code,
            "title": definition["title"],
            "officer_explanation": f"AI risk signal: {definition['title'].lower()}.",
            "detail": definition["explanation"],
            "severity": definition["severity"],
        })
    return explanations
