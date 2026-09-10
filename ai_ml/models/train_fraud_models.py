"""Turns `feature_builder.safe_feature_columns(...)` into an actual
scikit-learn-ready feature matrix, and builds the two Step 5.2 models
(Logistic Regression, Random Forest) as Pipelines.

`safe_feature_columns` (Step 5.1/`ai_ml.common.feature_builder`) already
removes every *leaked* column for a given target. This module adds the
second, separate kind of exclusion the Step 5.2 instructions call for:
direct identifiers, free-text fields, and near-identifier high-cardinality
categorical codes - none of these are "leakage" in the target-audit
sense, but none of them belong in a predictive model either. Every
exclusion here is returned alongside the built feature list so it can be
printed/logged rather than silently applied.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Direct identifiers / PII - re-identify a specific claim/customer/vehicle
# rather than describing a generalizable pattern. Some of these are exact
# duplicates of the Claim_ID/Customer_ID/Vehicle_ID/Policy_ID columns
# already dropped by safe_feature_columns, just re-introduced under a
# table-prefixed name (e.g. veh_Customer_ID) - still identifiers.
IDENTIFIER_COLUMNS = [
    "Claim_Number", "Claim_Number_Child",
    "veh_Customer_ID", "veh_Policy_ID", "pol_Customer_ID", "pol_Vehicle_ID",
    "veh_Registration_Number", "veh_Chassis_Number", "veh_Engine_Number",
    "pol_Policy_Number",
    "cust_Customer_Name", "cust_Phone", "cust_Email", "cust_Address",
    "est_Garage_ID", "insp_Surveyor_ID",
]

# Free-text fields - not meaningfully one-hot-encodable, and using them
# would require an NLP/OCR text model, explicitly out of scope for this
# step (see Step 5.1 audit, Section 11 "AI Model Plan").
FREE_TEXT_COLUMNS = [
    "Claim_Description", "acc_Accident_Description", "dmg_Damage_Description",
    "insp_Surveyor_Comments", "acc_Accident_Location", "acc_FIR_Number",
    "insp_Inspection_Location", "acc_Accident_Time",
]

# Above this many distinct values, a text/object column behaves like a
# near-identifier (a real category - e.g. Vehicle_Type, Occupation - does
# not need hundreds of levels for 654 claims) rather than a genuine,
# generalizable category. Flagged automatically and logged, on top of
# the explicit lists above.
MAX_CATEGORICAL_CARDINALITY = 50

# Two simple, leakage-safe engineered features (also used by the rule
# baseline) computed from raw datetime/amount columns that cannot be fed
# to scikit-learn directly.
ENGINEERED_FEATURES = ["days_since_policy_start", "repair_ratio"]


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a copy of df with the engineered numeric columns added."""
    out = df.copy()
    claim_amount = out["Claim_Amount"].replace(0, np.nan)
    out["repair_ratio"] = out["est_Repair_Estimate"] / claim_amount
    out["days_since_policy_start"] = (out["Claim_Date"] - out["pol_Policy_Start_Date"]).dt.days
    return out


def classify_feature_columns(df: pd.DataFrame, safe_columns: list[str]) -> dict:
    """Splits `safe_columns` into what actually goes into the model
    (numeric / categorical) vs. what is excluded and why. `df` must
    already have the engineered features added.

    Returns a dict: {"numeric": [...], "categorical": [...],
    "excluded_identifier": [...], "excluded_free_text": [...],
    "excluded_high_cardinality": [...], "excluded_datetime": [...]}
    """
    candidate = [c for c in safe_columns if c not in IDENTIFIER_COLUMNS and c not in FREE_TEXT_COLUMNS]
    excluded_datetime = []
    excluded_zero_information = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    excluded_high_cardinality = []

    for col in candidate:
        dtype = df[col].dtype
        if pd.api.types.is_datetime64_any_dtype(dtype):
            excluded_datetime.append(col)
            continue
        # A column with 0 or 1 distinct non-null value carries no signal
        # at all (e.g. veh_Vehicle_Subtype is 100% missing - see the
        # Step 5.1 audit) - imputing/encoding it only produces warnings.
        if df[col].nunique(dropna=True) <= 1:
            excluded_zero_information.append(col)
        elif pd.api.types.is_bool_dtype(dtype) or pd.api.types.is_numeric_dtype(dtype):
            numeric_cols.append(col)
        else:
            nunique = df[col].nunique(dropna=True)
            if nunique > MAX_CATEGORICAL_CARDINALITY:
                excluded_high_cardinality.append(col)
            else:
                categorical_cols.append(col)

    for feat in ENGINEERED_FEATURES:
        if feat not in numeric_cols:
            numeric_cols.append(feat)

    return {
        "numeric": numeric_cols,
        "categorical": categorical_cols,
        "excluded_identifier": [c for c in safe_columns if c in IDENTIFIER_COLUMNS],
        "excluded_free_text": [c for c in safe_columns if c in FREE_TEXT_COLUMNS],
        "excluded_high_cardinality": excluded_high_cardinality,
        "excluded_datetime": excluded_datetime,
        "excluded_zero_information": excluded_zero_information,
    }


def build_preprocessor(numeric_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    """Impute + scale numeric columns; impute + one-hot categorical
    columns. `handle_unknown='ignore'` so a category seen only in test
    never crashes the pipeline (it just contributes all-zero dummies)."""
    numeric_pipeline = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("numeric", numeric_pipeline, numeric_cols),
        ("categorical", categorical_pipeline, categorical_cols),
    ])


def train_logistic_regression(
    X_train: pd.DataFrame, y_train: pd.Series, preprocessor: ColumnTransformer, class_weight: str | None = None
) -> Pipeline:
    """Fits ONLY on the training split passed in."""
    pipeline = Pipeline([
        ("preprocess", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000, class_weight=class_weight, random_state=42)),
    ])
    pipeline.fit(X_train, y_train)
    return pipeline


def train_random_forest(
    X_train: pd.DataFrame, y_train: pd.Series, preprocessor: ColumnTransformer, class_weight: str | None = None
) -> Pipeline:
    """Small, controlled configuration - 654 rows and explainability
    both argue against a large hyperparameter search."""
    pipeline = Pipeline([
        ("preprocess", preprocessor),
        (
            "classifier",
            RandomForestClassifier(
                n_estimators=200,
                max_depth=6,
                min_samples_leaf=5,
                class_weight=class_weight,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])
    pipeline.fit(X_train, y_train)
    return pipeline
