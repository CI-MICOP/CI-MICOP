"""Reusable data-quality audit functions used by the Step 5.1 dataset
audit (see docs/project_documentation/AI_ML_DATASET_AUDIT.md) and by any
later modeling step that needs to re-check the raw tables. Everything
here is read-only / analysis-only - it never mutates the DataFrames it
is given or writes back to the raw files.
"""

from __future__ import annotations

import pandas as pd


def missing_value_report(df: pd.DataFrame) -> pd.DataFrame:
    """Missing-value count and percentage per column."""
    missing = df.isna().sum()
    pct = (missing / len(df) * 100).round(2) if len(df) else missing * 0.0
    return pd.DataFrame({"missing_count": missing, "missing_pct": pct}).sort_values(
        "missing_pct", ascending=False
    )


def unique_value_report(df: pd.DataFrame) -> pd.Series:
    """Distinct-value count per column (NaN not counted as a value)."""
    return df.nunique(dropna=True).sort_values(ascending=False)


def duplicate_row_count(df: pd.DataFrame) -> int:
    """Fully-duplicated rows (every column identical)."""
    return int(df.duplicated(keep=False).sum())


def duplicate_id_count(df: pd.DataFrame, id_column: str) -> int:
    """Rows whose primary-key column value repeats (should be 0 for a
    genuine primary key)."""
    if id_column not in df.columns:
        return 0
    return int(df[id_column].duplicated(keep=False).sum())


def numeric_range_report(df: pd.DataFrame) -> pd.DataFrame:
    """Min/max/mean/negative-count for every numeric column - a cheap way
    to spot impossible values (negative amounts, negative day-counts)."""
    numeric_cols = df.select_dtypes(include="number").columns
    rows = []
    for col in numeric_cols:
        series = df[col]
        rows.append(
            {
                "column": col,
                "min": series.min(),
                "max": series.max(),
                "mean": round(series.mean(), 2) if len(series) else None,
                "negative_count": int((series < 0).sum()),
                "zero_count": int((series == 0).sum()),
            }
        )
    return pd.DataFrame(rows).set_index("column")


def date_range_report(df: pd.DataFrame) -> pd.DataFrame:
    """Min/max for every datetime column, plus a count of dates in the
    future relative to today (a common synthetic-data red flag)."""
    date_cols = df.select_dtypes(include="datetime").columns
    now = pd.Timestamp.now()
    rows = []
    for col in date_cols:
        series = df[col].dropna()
        rows.append(
            {
                "column": col,
                "min": series.min() if len(series) else None,
                "max": series.max() if len(series) else None,
                "future_count": int((series > now).sum()) if len(series) else 0,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["column", "min", "max", "future_count"]).set_index("column")
    return pd.DataFrame(rows).set_index("column")


def categorical_value_counts(df: pd.DataFrame, max_categories: int = 20) -> dict[str, pd.Series]:
    """Value counts for every text/categorical column with a manageable
    number of distinct values - used to spot suspicious/inconsistent
    category labels (typos, mixed casing, stray whitespace)."""
    result = {}
    for col in df.select_dtypes(include="object").columns:
        nunique = df[col].nunique(dropna=True)
        if 0 < nunique <= max_categories:
            result[col] = df[col].value_counts(dropna=False)
    return result


def foreign_key_orphan_count(child_df: pd.DataFrame, fk_column: str, parent_df: pd.DataFrame, parent_key: str) -> int:
    """Rows in child_df whose fk_column value does not exist in
    parent_df[parent_key] - should be 0 if referential integrity holds."""
    if fk_column not in child_df.columns or parent_key not in parent_df.columns:
        return 0
    valid_keys = set(parent_df[parent_key].dropna())
    child_keys = child_df[fk_column].dropna()
    return int((~child_keys.isin(valid_keys)).sum())


def table_summary(df: pd.DataFrame, id_column: str | None = None) -> dict:
    """One-line summary used to build the dataset-inventory table."""
    return {
        "rows": len(df),
        "columns": df.shape[1],
        "duplicate_rows": duplicate_row_count(df),
        "duplicate_ids": duplicate_id_count(df, id_column) if id_column else None,
        "total_missing_cells": int(df.isna().sum().sum()),
    }
