"""Human-readable reason codes shared by the rule-based baseline
(`ai_ml.baselines.rule_based_fraud`) and the ML explanation layer
(`ai_ml.explainability.shap_explainer`), so a Claims Officer sees the
same vocabulary regardless of which approach flagged a claim.

Language rule (Step 5.2, Section 15): never assert "fraud confirmed".
Every phrase below describes a *screening risk contributor*, not proof.
"""

from __future__ import annotations

REASON_CODES: dict[str, str] = {
    "DOCUMENT_INCONSISTENCY": "Information across submitted documents is inconsistent.",
    "REPAIR_ESTIMATE_ANOMALY": "The repair estimate contains an unusual cost pattern.",
    "DUPLICATE_EVIDENCE": "Similar evidence appears more than once.",
    "UNUSUAL_CLAIM_PATTERN": "The claim contains a pattern that differs from typical claims.",
}

# Maps a raw (pre-one-hot) claim-level feature name to the reason code it
# represents, for turning a SHAP top-feature list into the same
# vocabulary the rule baseline uses. Matched by prefix so one entry
# covers every column from that source table/signal.
_FEATURE_PREFIX_TO_REASON = [
    ("cdc_", "DOCUMENT_INCONSISTENCY"),
    ("document_", "DOCUMENT_INCONSISTENCY"),
    ("has_document_", "DOCUMENT_INCONSISTENCY"),
    ("est_", "REPAIR_ESTIMATE_ANOMALY"),
    ("repair_ratio", "REPAIR_ESTIMATE_ANOMALY"),
    ("dmg_", "REPAIR_ESTIMATE_ANOMALY"),
    ("evidence_", "DUPLICATE_EVIDENCE"),
    ("has_evidence_", "DUPLICATE_EVIDENCE"),
]


def reason_code_for_feature(feature_name: str) -> str:
    """Best-effort mapping of a raw feature name to one of the 4 reason
    codes above. Falls back to UNUSUAL_CLAIM_PATTERN for anything that
    doesn't match a known signal family (e.g. customer/vehicle/policy
    profile fields, timing features)."""
    for prefix, code in _FEATURE_PREFIX_TO_REASON:
        if feature_name.startswith(prefix):
            return code
    return "UNUSUAL_CLAIM_PATTERN"


def describe_reason_code(code: str) -> str:
    return REASON_CODES.get(code, "This claim shows a pattern the screening process flagged for review.")


def build_claim_explanation(claim_id: str, risk_level: str, top_factors: list[str]) -> dict:
    """Assembles the claim-level explanation structure a Claims Officer
    would see. `top_factors` is an ordered list of reason codes (most
    important first). This never states a verdict - only risk-level and
    contributing factors, matching Step 4.5's "AI provides decision
    support; the officer decides" wording already shipped in the UI."""
    return {
        "claim_id": claim_id,
        "fraud_screening_risk": risk_level,
        "contributing_factors": [
            {"code": code, "description": describe_reason_code(code)} for code in top_factors
        ],
        "disclaimer": "These are risk contributors, not proof of fraud. Final decision remains with the Claims Officer.",
    }
