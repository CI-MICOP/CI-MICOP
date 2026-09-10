"""Repeated, Customer_ID-grouped cross-validation for the Step 5.3
secondary targets (Section 4/5/9). Every fold enforces zero Customer_ID
overlap between its train and validation portions - the same invariant
Step 5.2 enforces for the single train/test split, just repeated across
folds and seeds so the results carry a stability estimate instead of a
single lucky/unlucky split.

`StratifiedGroupKFold` (sklearn >= 1.1) is used when the smallest class is
large enough to support the requested fold count; otherwise the fold
count is reduced and the limitation is reported rather than silently
producing empty/degenerate folds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import StratifiedGroupKFold

RANDOM_SEEDS = [42, 43, 44]
MAX_FOLDS = 5
MIN_FOLDS = 3


def choose_fold_count(min_class_size: int, max_folds: int = MAX_FOLDS, min_folds: int = MIN_FOLDS) -> int:
    """Never propose more folds than the smallest class can support
    (each fold's validation slice needs at least ~1 example of every
    class for stratification to mean anything). Returns 0 if even
    `min_folds` folds are not supportable - callers must check for this
    and skip that target's CV rather than forcing degenerate folds."""
    if min_class_size < min_folds:
        return 0
    return min(max_folds, min_class_size)


def make_folds(df: pd.DataFrame, target_col: str, n_splits: int, random_state: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Returns [(train_idx, val_idx), ...] as positional index arrays into
    `df`, grouped by Customer_ID, stratified by `target_col`. Verifies
    zero Customer_ID overlap for every fold (hard assertion, not just a
    printed warning)."""
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    y = df[target_col].astype(str).values
    groups = df["Customer_ID"].values
    folds = []
    for train_idx, val_idx in splitter.split(df, y, groups=groups):
        train_customers = set(df.iloc[train_idx]["Customer_ID"])
        val_customers = set(df.iloc[val_idx]["Customer_ID"])
        overlap = train_customers & val_customers
        if overlap:
            raise AssertionError(f"Customer_ID overlap in a CV fold: {len(overlap)} customers appear in both train and validation.")
        folds.append((train_idx, val_idx))
    return folds


def fold_class_distribution(df: pd.DataFrame, target_col: str, folds: list[tuple[np.ndarray, np.ndarray]]) -> pd.DataFrame:
    """Section 5: class distribution per fold, for reporting."""
    rows = []
    for i, (train_idx, val_idx) in enumerate(folds):
        val_counts = df.iloc[val_idx][target_col].value_counts().to_dict()
        rows.append({
            "fold": i,
            "n_train": len(train_idx),
            "n_val": len(val_idx),
            "n_train_customers": df.iloc[train_idx]["Customer_ID"].nunique(),
            "n_val_customers": df.iloc[val_idx]["Customer_ID"].nunique(),
            "val_class_distribution": val_counts,
            "val_has_all_classes": len(val_counts) == df[target_col].nunique(),
        })
    return pd.DataFrame(rows)


def summarize_stability(values: list[float]) -> dict:
    """Section 9: mean/std/min/max + 95% CI across fold/repeat results.
    Uses a t-distribution CI (appropriate for a small number of fold/
    repeat measurements, not assumed-normal population variance). If
    fewer than 2 usable values exist, no CI is reported - presenting one
    from a single number would be misleading, not merely imprecise."""
    clean = [v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
    n = len(clean)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None, "ci95": None, "ci_method": None}
    mean = float(np.mean(clean))
    if n == 1:
        return {"n": 1, "mean": mean, "std": None, "min": mean, "max": mean, "ci95": None,
                "ci_method": "not computed - only 1 usable value"}
    std = float(np.std(clean, ddof=1))
    sem = std / np.sqrt(n)
    t_crit = float(stats.t.ppf(0.975, df=n - 1))
    margin = t_crit * sem
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "min": float(np.min(clean)),
        "max": float(np.max(clean)),
        "ci95": [mean - margin, mean + margin],
        "ci_method": f"t-distribution (df={n - 1}), mean +/- t_crit * (std/sqrt(n))",
    }
