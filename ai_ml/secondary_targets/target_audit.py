"""Step 5.3 target audit + target-specific leakage classification for the
three secondary targets identified in Step 5.1:

    frd_Risk_Category                    (4-class: Low/Medium/High/Critical)
    cdc_Overall_Consistency_Status       (3-class: Match/Partial Match/Mismatch)
    est_Excessive_Claim_Amount_Indicator (binary)

`ai_ml.common.feature_builder.TARGET_LEAKAGE_GROUPS` already gives each of
these targets a conservative, table-level leakage rule (exclude the whole
source table that the target itself lives in). This module does NOT
change that shared, already-tested Step 5.2 architecture. Instead it
verifies whether that blanket rule is actually correct for each target
(via crosstabs/correlations against the real data - see the "why"
comment on each entry below) and, where the verification shows the
blanket rule is *too conservative* (throwing away legitimate pre-decision
fields that are not actually target-derived), builds a narrower,
target-specific SAFE list on top of it. Every exclusion decision is
one of exactly three categories, per claim/target:

    SAFE              - legitimate pre-decision input, verified independent
                         of the target's own generation process
    POTENTIAL_LEAKAGE - same source table / same generation process as the
                         target, but NOT proven to determine it - excluded
                         out of caution, not because it was shown to leak
    DEFINITE_LEAKAGE  - the target itself, or a column proven/near-proven
                         to encode it (including cross-table duplicate
                         "sibling" columns that ordinary prefix-based
                         exclusion does not catch)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_ml.common.feature_builder import (
    ALWAYS_LEAKED_COLUMNS,
    ALWAYS_LEAKED_PREFIXES,
    LEAKAGE_ADJACENT_COLUMNS,
    POST_REPAIR_COLUMNS,
    leaked_columns_for_target,
    safe_feature_columns,
)

SECONDARY_TARGETS = [
    "frd_Risk_Category",
    "cdc_Overall_Consistency_Status",
    "est_Excessive_Claim_Amount_Indicator",
]

# Columns that need to be added back to feature_builder's blanket "exclude
# the whole source table" rule, because verification (see run_secondary_
# targets_experiment.py's `verify_target_relationships`) showed they are
# legitimate pre-decision inputs, not target-derived. Empty for a target
# means "the blanket rule is correct as-is - keep it."
SAFE_RESTORATIONS: dict[str, list[str]] = {
    # Verified: est_Repair_Estimate/Repair_Cost/.../Estimated_Repair_Days
    # correlate near-zero with est_Excessive_Claim_Amount_Indicator
    # (|r| < 0.02 - see report Section on target-specific leakage). They
    # are ordinary, legitimate pre-decision garage-estimate fields, not
    # a rollup of the indicator, so the table-level blanket exclusion
    # was too conservative specifically for THIS target.
    "est_Excessive_Claim_Amount_Indicator": [
        "est_Repair_Estimate", "est_Repair_Cost", "est_Parts_Cost",
        "est_Labour_Cost", "est_Painting_Cost",
        "est_Replacement_Parts_Count", "est_Repaired_Parts_Count",
        "est_Estimated_Repair_Days",
    ],
    "frd_Risk_Category": [],
    "cdc_Overall_Consistency_Status": [],
}

# Columns that must be added to DEFINITE_LEAKAGE on top of feature_builder's
# rule, because they are cross-table "sibling" duplicates of the target
# concept that a plain table-prefix rule does not catch.
EXTRA_DEFINITE_LEAKAGE: dict[str, list[str]] = {
    # A near-duplicate of the target living in a DIFFERENT table (fraud_
    # risk_analysis also carries an Excessive_Claim_Amount_Indicator).
    # Only 53.8% agreement with the real target (near coin-flip - see
    # verification script), so it is not literally the same value, but it
    # is the same *concept* re-asserted elsewhere and must not be used to
    # predict its own sibling.
    "est_Excessive_Claim_Amount_Indicator": ["frd_Excessive_Claim_Amount_Indicator"],
    # frd_Fraud_Label is NOT in the same table as Risk_Category's table
    # rule already excludes it (whole frd_ prefix), so no extra entry is
    # needed here for feature exclusion - but see NOTE below: it is
    # documented as DEFINITE_LEAKAGE in the report because of the strong,
    # asymmetric relationship verified in Section 11 (Low/Medium
    # Risk_Category claims are NEVER labeled fraud). Listed for
    # completeness / report generation only.
    "frd_Risk_Category": ["frd_Fraud_Label"],
    "cdc_Overall_Consistency_Status": [],
}


def audit_target(target: str, df: pd.DataFrame) -> dict:
    """Section 1A: existence / dtype / class balance / missingness."""
    exists = target in df.columns
    if not exists:
        return {"target": target, "exists": False}

    series = df[target]
    missing = int(series.isna().sum())
    counts = series.value_counts(dropna=True)
    pct = (counts / len(df) * 100).round(2)
    return {
        "target": target,
        "exists": True,
        "dtype": str(series.dtype),
        "n_rows": len(df),
        "missing_values": missing,
        "n_classes": int(counts.shape[0]),
        "class_counts": counts.to_dict(),
        "class_percentages": pct.to_dict(),
        "min_class_size": int(counts.min()) if len(counts) else 0,
        "claim_id_unique": bool(df["Claim_ID"].is_unique),
    }


def leakage_report(target: str, df: pd.DataFrame) -> dict:
    """Section 1B/2: SAFE / POTENTIAL_LEAKAGE / DEFINITE_LEAKAGE for one
    target, built on top of feature_builder's existing rules.

    - DEFINITE_LEAKAGE = the target itself, plus any cross-table sibling
      duplicate proven/suspected to encode the same concept
      (EXTRA_DEFINITE_LEAKAGE).
    - POTENTIAL_LEAKAGE = everything feature_builder already excludes for
      this target's own source table (same generation process, not proven
      to determine the target - excluded out of caution), MINUS the
      structural exclusions that apply to every target regardless of
      leakage (always-leaked columns/prefixes, post-repair, identifiers,
      Claim_Status) which are reported separately as "structural", and
      MINUS anything explicitly restored back to SAFE.
    - SAFE = feature_builder's safe list, plus restorations, minus
      whatever ends up in POTENTIAL_LEAKAGE or DEFINITE_LEAKAGE.
    """
    base_leaked = set(leaked_columns_for_target(target, df))
    base_safe = set(safe_feature_columns(target, df))

    restorations = [c for c in SAFE_RESTORATIONS.get(target, []) if c in df.columns]
    extra_definite = [c for c in EXTRA_DEFINITE_LEAKAGE.get(target, []) if c in df.columns]

    definite = {target} | set(extra_definite)

    structural_exclusions = (
        set(ALWAYS_LEAKED_COLUMNS)
        | set(POST_REPAIR_COLUMNS)
        | set(LEAKAGE_ADJACENT_COLUMNS)
        | {"Claim_ID", "Policy_ID", "Customer_ID", "Vehicle_ID"}
    )
    potential = {
        c for c in (base_leaked - set(restorations) - definite)
        if not any(c.startswith(p) for p in ALWAYS_LEAKED_PREFIXES)
        and c not in structural_exclusions
    }

    safe = (base_safe | set(restorations)) - potential - definite

    return {
        "target": target,
        "safe_features": sorted(safe),
        "potential_leakage": sorted(potential),
        "definite_leakage": sorted(definite),
        "n_safe": len(safe),
        "n_potential_leakage": len(potential),
        "n_definite_leakage": len(definite),
        "restorations_applied": restorations,
    }


def secondary_safe_feature_columns(target: str, df: pd.DataFrame) -> list[str]:
    """The feature list actually used for modeling `target` - SAFE only,
    never POTENTIAL_LEAKAGE or DEFINITE_LEAKAGE."""
    return leakage_report(target, df)["safe_features"]


NO_BASELINE_STATEMENT = (
    "No defensible non-AI baseline was implemented for this target because "
    "the available fields do not provide an independent rule definition "
    "without target leakage."
)
