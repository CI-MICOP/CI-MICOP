"""SHAP-based, claim-level explanations for the two ML models.

Kept deliberately simple: both models are scikit-learn Pipelines
(preprocess -> classifier). Rather than explaining the whole pipeline
(SHAP does not understand ColumnTransformer/OneHotEncoder directly), this
transforms the input once with the fitted preprocessor and explains the
classifier step directly against the transformed feature space, using
`preprocessor.get_feature_names_out()` for real (if one-hot-expanded)
feature names.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap

from ai_ml.explainability.reason_codes import reason_code_for_feature


def _transformed_frame(pipeline, X: pd.DataFrame) -> pd.DataFrame:
    preprocessor = pipeline.named_steps["preprocess"]
    transformed = preprocessor.transform(X)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    feature_names = preprocessor.get_feature_names_out()
    return pd.DataFrame(transformed, columns=feature_names, index=X.index)


def build_explainer(pipeline, X_background: pd.DataFrame, model_kind: str):
    """model_kind: 'logistic_regression' or 'random_forest'."""
    classifier = pipeline.named_steps["classifier"]
    background = _transformed_frame(pipeline, X_background)

    if model_kind == "random_forest":
        return shap.TreeExplainer(classifier), background
    if model_kind == "logistic_regression":
        # LinearExplainer needs the background distribution to estimate
        # feature means/covariance for its expected-value baseline.
        return shap.LinearExplainer(classifier, background), background
    raise ValueError(f"Unknown model_kind: {model_kind}")


def explain_claims(pipeline, model_kind: str, X_background: pd.DataFrame, X_explain: pd.DataFrame, top_n: int = 3):
    """Returns (shap_values_for_class_1, transformed_explain_frame,
    top_factors_per_row) where top_factors_per_row[i] is a list of up to
    `top_n` (raw_feature_name, shap_value) tuples sorted by |shap_value|,
    restricted to POSITIVE contributions (features pushing risk up) since
    that is what a claims officer needs to see first."""
    explainer, _ = build_explainer(pipeline, X_background, model_kind)
    transformed_explain = _transformed_frame(pipeline, X_explain)

    raw_values = explainer.shap_values(transformed_explain)
    # RandomForestClassifier binary output: list [class0, class1] or a
    # (n, features, n_classes) array depending on the shap/sklearn
    # version - normalize to a single (n, features) array for class 1.
    if isinstance(raw_values, list):
        values = raw_values[1]
    elif isinstance(raw_values, np.ndarray) and raw_values.ndim == 3:
        values = raw_values[:, :, 1]
    else:
        values = raw_values

    feature_names = list(transformed_explain.columns)
    top_factors_per_row = []
    for row_idx in range(values.shape[0]):
        row_values = values[row_idx]
        order = np.argsort(-row_values)  # descending: most risk-increasing first
        top = [(feature_names[i], float(row_values[i])) for i in order[:top_n] if row_values[i] > 0]
        top_factors_per_row.append(top)

    return values, transformed_explain, top_factors_per_row


def risk_level_from_probability(probability: float) -> str:
    """Simple, documented banding - not calibrated against any external
    standard, just a readable 4-level split for the officer-facing UI."""
    if probability >= 0.75:
        return "HIGH"
    if probability >= 0.5:
        return "MEDIUM"
    if probability >= 0.25:
        return "LOW"
    return "MINIMAL"


def to_reason_codes(top_factors: list[tuple[str, float]]) -> list[str]:
    """Maps a SHAP top-feature list (raw, possibly one-hot-expanded
    names like 'categorical__Claim_Type_Theft') to the shared reason-code
    vocabulary, de-duplicated, most important first."""
    codes: list[str] = []
    for feature_name, _value in top_factors:
        # Strip the ColumnTransformer's "numeric__"/"categorical__" prefix
        # before matching against the raw column-name patterns.
        bare_name = feature_name.split("__", 1)[-1]
        code = reason_code_for_feature(bare_name)
        if code not in codes:
            codes.append(code)
    return codes
