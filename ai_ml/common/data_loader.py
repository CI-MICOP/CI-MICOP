"""Loads the raw CI-MICOP dataset tables (Excel files) into pandas
DataFrames. Read-only - nothing here ever writes back to the raw files.

The dataset lives under ai_ml/datasets/CI_MICOP_15_Tables_Complete/. Table
names below match the CI-MICOP database's own table names (see
database/schema.sql) so downstream code can refer to a table the same way
whether it eventually comes from Postgres or from these raw files.
"""

from pathlib import Path

import pandas as pd

# ai_ml/common/data_loader.py -> parents[1] == ai_ml/
AI_ML_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = AI_ML_DIR / "datasets" / "CI_MICOP_15_Tables_Complete"

# Maps each CI-MICOP table name to its source file. authentication_users
# deliberately points at CI_MICOP_Authentication_Users.xlsx (660 rows), not
# 01_authentication_users.xlsx (600 rows) - the Step 2 database report
# documented this same authoritative-file choice, and this pipeline mirrors
# it so the AI dataset matches what is actually loaded into the database.
TABLE_FILES = {
    "authentication_users": "CI_MICOP_Authentication_Users.xlsx",
    "customers": "02_customers.xlsx",
    "vehicles": "03_vehicles.xlsx",
    "policies": "04_policies.xlsx",
    "claims": "05_claims.xlsx",
    "accidents": "06_accidents.xlsx",
    "documents": "07_documents.xlsx",
    "vehicle_damage": "08_vehicle_damage.xlsx",
    "repair_estimates": "09_repair_estimates.xlsx",
    "evidence": "10_evidence.xlsx",
    "surveyor_inspections": "11_surveyor_inspections.xlsx",
    "cross_document_consistency": "12_cross_document_consistency.xlsx",
    "fraud_risk_analysis": "13_fraud_risk_analysis.xlsx",
    "claim_decision_audit": "14_claim_decision_audit.xlsx",
    "tp_claims": "15_tp_claims.xlsx",
}

# Columns that are dates/timestamps stored as text in the raw files -
# parsed on load so downstream code gets real datetime dtypes instead of
# strings, without ever mutating the source .xlsx files themselves.
DATE_COLUMNS = {
    "authentication_users": ["Last_Login", "Created_Date"],
    "customers": ["Date_of_Birth"],
    "vehicles": ["Policy_Start_Date", "Policy_End_Date"],
    "policies": ["Policy_Start_Date", "Policy_End_Date"],
    "claims": ["Claim_Date", "Claim_Intimation_Date", "Date_of_Disbursement", "Decision_Date"],
    "accidents": ["Accident_Date"],
    "documents": ["Document_Submitted_Date"],
    "repair_estimates": ["Estimate_Date"],
    "evidence": ["Evidence_Date"],
    "surveyor_inspections": ["Inspection_Date"],
    "claim_decision_audit": ["Decision_Date", "Audit_Timestamp"],
}


def load_table(table_name: str) -> pd.DataFrame:
    """Loads one table by its CI-MICOP name (see TABLE_FILES)."""
    if table_name not in TABLE_FILES:
        raise ValueError(f"Unknown table '{table_name}'. Known tables: {sorted(TABLE_FILES)}")

    path = DATASET_DIR / TABLE_FILES[table_name]
    if not path.exists():
        raise FileNotFoundError(f"Expected dataset file not found: {path}")

    df = pd.read_excel(path)
    for col in DATE_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def load_all_tables() -> dict[str, pd.DataFrame]:
    """Loads every known table into a {table_name: DataFrame} dict."""
    return {name: load_table(name) for name in TABLE_FILES}
