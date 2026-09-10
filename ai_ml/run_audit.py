"""Step 5.1 dataset audit runner.

Loads every raw table, runs the data-quality checks from
ai_ml/common/data_quality.py, builds the claim-level modeling dataset via
ai_ml/common/feature_builder.py, and verifies it end to end (row count,
uniqueness, no silent drops). This script is read-only with respect to
the raw dataset - it never writes back to ai_ml/datasets/.

Run from the repo root:
    python -m ai_ml.run_audit
"""

from __future__ import annotations

from ai_ml.common import data_quality as dq
from ai_ml.common import feature_builder as fb
from ai_ml.common.data_loader import TABLE_FILES, load_all_tables


def audit_all_tables() -> dict[str, pd.DataFrame]:
    import pandas as pd  # local import keeps module import light for callers that only need the dict

    tables = load_all_tables()
    id_columns = {
        "authentication_users": "User_ID",
        "customers": "Customer_ID",
        "vehicles": "Vehicle_ID",
        "policies": "Policy_ID",
        "claims": "Claim_ID",
        "accidents": "Accident_ID",
        "documents": "Document_ID",
        "vehicle_damage": "Damage_ID",
        "repair_estimates": "Estimate_ID",
        "evidence": "Evidence_ID",
        "surveyor_inspections": "Inspection_ID",
        "cross_document_consistency": "Consistency_ID",
        "fraud_risk_analysis": "Risk_ID",
        "claim_decision_audit": "Audit_ID",
        "tp_claims": "TP_Claim_ID",
    }

    print("=" * 100)
    print("DATASET INVENTORY")
    print("=" * 100)
    for name in TABLE_FILES:
        df = tables[name]
        summary = dq.table_summary(df, id_columns.get(name))
        print(f"{name:30s} file={TABLE_FILES[name]:40s} rows={summary['rows']:5d} cols={summary['columns']:3d} "
              f"dup_rows={summary['duplicate_rows']:3d} dup_ids={summary['duplicate_ids']} "
              f"missing_cells={summary['total_missing_cells']}")

    return tables


def verify_claim_level_dataset(tables) -> None:
    print()
    print("=" * 100)
    print("CLAIM-LEVEL DATASET BUILD + VERIFICATION")
    print("=" * 100)
    claims = tables["claims"]
    dataset = fb.build_claim_level_dataset()
    print(f"raw claims rows:       {len(claims)}")
    print(f"claim-level rows out:  {len(dataset)}")
    print(f"claim-level columns:   {dataset.shape[1]}")
    assert len(dataset) == len(claims), "Row count changed during build - see feature_builder assertions."
    assert dataset["Claim_ID"].is_unique, "Claim_ID must be unique in the claim-level dataset."
    print("VERIFIED: one row per claim, no rows silently dropped or duplicated.")

    for target in ["frd_Fraud_Label", "frd_Risk_Category", "cdc_Overall_Consistency_Status",
                    "est_Excessive_Claim_Amount_Indicator", "Final_Decision"]:
        safe_cols = fb.safe_feature_columns(target, dataset)
        leaked_cols = fb.leaked_columns_for_target(target, dataset)
        print(f"\nTarget: {target}")
        print(f"  safe feature columns:   {len(safe_cols)}")
        print(f"  leaked/excluded columns: {len(leaked_cols)}")


def main() -> None:
    tables = audit_all_tables()
    verify_claim_level_dataset(tables)


if __name__ == "__main__":
    main()
