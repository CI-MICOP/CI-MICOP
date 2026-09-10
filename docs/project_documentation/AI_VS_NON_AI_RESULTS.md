# CI-MICOP Step 5.2 — Rule-Based Baseline vs. ML Models + Explainable AI

**Reproduce this report:** `python -m ai_ml.experiments.run_fraud_experiment` (from the repo root, with `ai_ml/requirements.txt` installed). Every number below is copied directly from that run's output and from `ai_ml/model_artifacts/evaluation_results.json` / `test_set_predictions_and_errors.csv` — nothing here is estimated or invented.

---

## 1. Objective

Compare a transparent, non-AI rule-based fraud screen against two ML models (Logistic Regression, Random Forest) on **exactly the same held-out test claims**, then explain both approaches' outputs in language a Claims Officer can act on — without either approach ever making the final decision.

```
                    SAME TEST SET
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
       NON-AI BASELINE           ML MODELS
       Rule-based                Logistic Regression
                                 Random Forest
              │                     │
              └──────────┬──────────┘
                         ↓
                  Evaluation
                         ↓
                  Explainability
                         ↓
                Claims Officer
```

## 2. Dataset

The verified 654-claim, one-row-per-claim dataset from Step 5.1 (`ai_ml.common.feature_builder.build_claim_level_dataset()`), plus two engineered numeric features added this step (`repair_ratio = est_Repair_Estimate / Claim_Amount`, `days_since_policy_start = Claim_Date − pol_Policy_Start_Date`), used by both the rule baseline and the ML models.

## 3. Target

**`frd_Fraud_Label`** — binary, verified present, verified binary (values `{0, 1}` only), 654/654 claims labeled. Class distribution over the full dataset: **555 (84.86%) not-fraud, 99 (15.14%) fraud**. As documented in `AI_ML_DATASET_AUDIT.md`, this is a **synthetic proxy label**, not verified ground truth — see Section 15 of that report for the evidence (it is statistically almost independent of its own sibling indicator columns).

## 4. Leakage Controls

Built entirely on the existing `ai_ml.common.feature_builder.safe_feature_columns("frd_Fraud_Label", df)` (187 columns) from Step 5.1 — unchanged this step. On top of that leakage filter, this step adds a *second* filter (`ai_ml.models.train_fraud_models.classify_feature_columns`) for identifiers/free-text/high-cardinality codes that are not "leakage" in the target-audit sense but still do not belong in a predictive model:

| Exclusion reason | Count | Examples |
|---|---:|---|
| Direct identifier / PII | 16 | `Claim_Number`, `cust_Customer_Name`, `cust_Phone`, `cust_Email`, `cust_Address`, `veh_Registration_Number`, `veh_Chassis_Number`, `veh_Engine_Number`, `pol_Policy_Number`, `est_Garage_ID`, `insp_Surveyor_ID` |
| Free text | 8 | `Claim_Description`, `acc_Accident_Description`, `dmg_Damage_Description`, `insp_Surveyor_Comments`, `acc_Accident_Location`, `acc_FIR_Number`, `insp_Inspection_Location`, `acc_Accident_Time` |
| High-cardinality categorical (near-identifier) | 6 | `Insurer_NOL_Code` (472 distinct), `veh_Make_Code` (469), `veh_Model` (66), `veh_RTA_Location_Code` (461), `pol_Office_Code` (470), `pol_Endorsement_Number` (57) |
| Raw datetime (replaced by the 2 engineered numeric features) | 11 | `Claim_Date`, `pol_Policy_Start_Date`, `acc_Accident_Date`, … |
| Zero-information (100% missing / constant) | 3 | `veh_Vehicle_Subtype` (100% missing, per the Step 5.1 audit), `Claim_Year`, `pol_Policy_Year` (single constant value) |

**Result: 69 numeric + 76 categorical = 145 features actually fed to the models.** A hard assertion in `run_fraud_experiment.py` checks the final feature set against `feature_builder.leaked_columns_for_target()` and raises immediately if any leaked column ever enters it — verified clean on this run.

## 5. Customer-Grouped Split

Split by `Customer_ID` using `sklearn.model_selection.GroupShuffleSplit(test_size=0.2, random_state=42)`, per the Step 5.1 finding that 151/487 customers file more than one claim.

| | Claims | Customers |
|---|---:|---:|
| Train | 520 | 389 |
| Test | 134 | 98 |
| **Overlap** | — | **0** |

Train positive rate: 15.00% · Test positive rate: 15.67% (both close to the full-dataset 15.14%, confirming the split did not distort the class balance). A hard assertion raises if this overlap is ever non-zero.

## 6. Rule-Based Baseline

Implemented in `ai_ml/baselines/rule_based_fraud.py`. Three boolean signals used as-is (already flags in the raw data): cross-document mismatch (`cdc_Document_Mismatch_Indicator` / `cdc_Accident_Details_Mismatch_Indicator` / `cdc_Vehicle_Damage_Mismatch_Indicator`, OR'd), `est_Excessive_Claim_Amount_Indicator`, `evidence_any_duplicate_flag`. Three numeric signals with thresholds **calibrated on the training split only** (90th/10th percentile, never touching test labels):

| Calibrated threshold | Value | Meaning |
|---|---:|---|
| `repair_ratio_threshold` | 2.948 | repair estimate ≥ 2.95× the claim amount |
| `early_claim_days_threshold` | 31.9 days | claim filed within ~32 days of policy start |
| `completeness_threshold` | 0.674 | mean document completeness in the worst 10% of training claims |

A claim is flagged if its weighted rule score reaches `overall_threshold=1.0` (one strong boolean flag, or two 0.5-weight numeric signals). Every flagged claim carries a plain-language reason code (`DOCUMENT_INCONSISTENCY`, `REPAIR_ESTIMATE_ANOMALY`, `DUPLICATE_EVIDENCE`, `UNUSUAL_CLAIM_PATTERN`).

## 7. Logistic Regression

`sklearn.Pipeline(ColumnTransformer[median-impute+scale numeric, most-frequent-impute+one-hot categorical] → LogisticRegression(class_weight="balanced", random_state=42))`. `class_weight="balanced"` was used because the training positive rate (15.0%) is well below 40%. Fit only on the 520 training claims.

## 8. Random Forest

Same preprocessing, `RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=5, class_weight="balanced", random_state=42)` — deliberately small given 654 total claims and the priority on explainability; no hyperparameter search was run.

## 9. Evaluation Metrics (identical 134 test claims, 21 actual positives)

| Approach | Accuracy* | Precision | Recall | F1 | ROC-AUC | PR-AUC | Confusion Matrix (TN/FP/FN/TP) |
|---|---:|---:|---:|---:|---:|---:|---|
| Rule Baseline (threshold=1.0) | 0.157 | 0.146 | **0.905** | 0.252 | 0.526 | 0.167 | 2 / 111 / 2 / 19 |
| Logistic Regression @0.5 | 0.709 | 0.200 | 0.286 | 0.235 | 0.635 | 0.222 | 89 / 24 / 15 / 6 |
| Logistic Regression @calibrated (0.35) | 0.687 | 0.200 | 0.333 | 0.250 | 0.635 | 0.222 | 85 / 28 / 14 / 7 |
| Random Forest @0.5 | 0.836 | 0.333 | 0.048 | 0.083 | 0.554 | **0.233** | 111 / 2 / 20 / 1 |
| Random Forest @calibrated (0.35) | 0.269 | 0.165 | **0.905** | 0.279 | 0.554 | 0.233 | 17 / 96 / 2 / 19 |

*Accuracy is reported for completeness only — per Step 5.1's class-balance analysis (5.6:1 imbalance) it is not the headline metric here; a trivial "always predict not-fraud" classifier would score 84.9% accuracy while catching zero fraud. The calibrated threshold (0.35) was chosen by maximizing F1 on an inner, customer-grouped train/validation split (391/129 claims) carved out of the training data only (F1=0.234 on that inner validation) — **the test set was never used for threshold selection.**

## 10. Comparison

By **PR-AUC** (the recommended metric given the imbalance, since it does not require picking a threshold): **Random Forest (0.233) ≈ Logistic Regression (0.222) > Rule Baseline (0.167)**. Both ML models outperform the rule baseline on ranking quality (PR-AUC, ROC-AUC), and honestly: **all three are close to chance-level given ROC-AUC values of 0.53–0.64** — none of them separate the two classes strongly.

At threshold=0.5, the two ML models sit at opposite ends of the precision/recall trade-off: **Random Forest is highly conservative** (flags only 3 of 134 test claims, catching 1 of 21 fraud cases, but only 2 false alarms), while **Logistic Regression is more balanced** (24 false positives, catches 6 of 21). The **rule baseline is the opposite extreme of Random Forest**: it flags 130 of 134 test claims (nearly everyone), which mechanically drives recall to 90.5% — but at only 14.6% precision, meaning roughly **6 of every 7 alerts it raises are false alarms**. This behavior is fully explained by Step 5.1: the underlying boolean indicators (document mismatch, excessive-amount flag, duplicate evidence) fire on roughly half the claims *independently of the fraud label*, so an OR-combination of them inevitably flags most claims. **This is itself a valid, reportable finding**, not a bug: it demonstrates quantitatively why a naive rule-based OR-screen is impractical on this dataset without either narrowing its trigger conditions or accepting a very high false-alarm rate — precisely the kind of result an ML model's PR-AUC-based ranking can improve on, even modestly.

## 11. False-Positive Analysis (threshold=0.5)

| Approach | # False Positives | Representative examples (no PII) |
|---|---:|---|
| Rule Baseline | 111 | Nearly the entire non-fraud test set — the OR-combination over-triggers, as explained above |
| Logistic Regression | 24 | `CLM-000103` (Total Loss, ₹11,442, consistency=Match, duplicate_evidence=True, p=0.903); `CLM-000106` (Theft, ₹156,783, consistency=Partial Match, p=0.998) |
| Random Forest | **2** | `CLM-000144` (Total Loss, ₹96,513, consistency=Match, excessive-amount=True, duplicate-evidence=True, completeness=0.90, p=0.522); `CLM-000649` (Third Party, ₹27,389, same two flags, p=0.506) |

Random Forest's two false positives both carry *every* "risky-looking" flag (excessive repair estimate **and** duplicate evidence **and** high completeness) yet are labeled not-fraud — a direct illustration of Step 5.1's finding that these indicators are largely independent of the actual label in this dataset.

## 12. False-Negative Analysis (threshold=0.5)

| Approach | # False Negatives | Representative examples (no PII) |
|---|---:|---|
| Rule Baseline | 2 | `CLM-000024` (Own Damage, consistency=Match, **no** flags fired at all, score=0.11); `CLM-000580` (Theft, ₹116,664, **zero** rules fired, score=0.00) |
| Logistic Regression | 15 | `CLM-000012` (Total Loss, excessive-amount=True, duplicate-evidence=True, p=0.001 — very confidently *wrong*); `CLM-000207` (Own Damage, same two flags, p=0.041) |
| Random Forest | 20 | Same `CLM-000012` (p=0.389); `CLM-000095` (Theft, ₹48,947, excessive-amount=True, duplicate-evidence=True, p=0.339) |

**The single most important individual case: `CLM-000024`.** It is genuinely labeled fraud (`Fraud_Label=1`) yet has `cdc_Overall_Consistency_Status=Match`, `est_Excessive_Claim_Amount_Indicator=False`, and `evidence_any_duplicate_flag=False` — **every visible screening signal looks completely clean**, and all three approaches (rule baseline, Logistic Regression, Random Forest) missed it. This is exactly what Step 5.1's target audit predicted: `Fraud_Label` correlates only weakly and noisily with the visible indicator columns, so no approach built on those columns alone can be expected to catch every case.

## 13. Practical Interpretation

- **Neither approach is production-ready**, and neither should be read as detecting real fraud — see Section 15.
- **Random Forest's advantage is in ranking (PR-AUC/ROC-AUC), not in its default 0.5-threshold behavior**, which is too conservative to be operationally useful (catches only 1 of 21 cases). The calibrated threshold (0.35) trades this for much higher recall (90.5%) at the cost of precision (16.5%) — nearly identical to the rule baseline's behavior at that point, which makes sense: both are trying to reach high recall from a weak signal.
- **The rule baseline is transparent and instantly explainable** ("flagged because of duplicate evidence + excessive repair estimate") but, as configured, is not selective enough to be useful for prioritizing officer attention — it would need either fewer OR-combined conditions or a higher `overall_threshold` (a documented, configurable change, not implemented this step per the "do not tune the baseline using test labels" instruction, since any further tuning must go back through Section 6's training-only calibration).
- **The honest headline finding is that Step 5.1's leakage/synthetic-label audit is confirmed empirically**: no approach — rule-based or ML — achieves strong separation (all ROC-AUC values are 0.53–0.64, barely better than the 0.50 of random guessing), which is consistent with `Fraud_Label` being a synthetically generated, largely independent proxy rather than a signal cleanly recoverable from the available pre-decision features.

## 14. Limitations

- 654 claims (520 train / 134 test, only ~21 positive test cases) is a small sample; metric estimates — especially PR-AUC on ~21 positives — have wide uncertainty. No confidence intervals were computed this step.
- The inner threshold-calibration split (Section 9) used a plain grouped split, not repeated cross-validation, so the calibrated threshold itself is a single noisy estimate.
- Random Forest used a fixed, small, manually chosen configuration (Section 8) — no hyperparameter search was performed, consistent with the "keep it practical" instruction, but this means reported performance is a lower bound on what that model family could achieve.
- The rule baseline's specific rule set and weights (Section 6) are one reasonable, documented configuration, not the only one — Section 13 already notes an untested but plausible refinement (raising `overall_threshold`).

## 15. Synthetic-Data Disclaimer

> This experiment is a validation study using the currently available CI-MICOP dataset. The dataset is synthetic/de-identified and therefore the measured performance must not be interpreted as production fraud-detection accuracy. Real-world validation requires appropriately governed insurer claims data.

This is consistent with, and directly confirmed by, the Step 5.1 audit's finding that `Fraud_Label` and its sibling risk columns behave as an independently-generated synthetic proxy rather than a verified real-world outcome (`AI_ML_DATASET_AUDIT.md`, Section 4).

**Research interpretation, stated explicitly:**
- **Non-AI (rule-based):** transparent screening logic an officer could read and verify line by line. Does not learn from data.
- **AI/ML:** statistical patterns learned from the 520 training claims. Cannot explain *why* in plain terms without the SHAP layer (Section 16 below).
- **Neither proves fraud.** Both produce a *screening risk signal* only.
- **The Claims Officer makes the final decision** — nothing in this pipeline writes back to the CI-MICOP database, and the Step 4.5 frontend already enforces "AI provides decision support; final decision remains with the Claims Officer" with no auto-decision endpoint.

```
Data → AI/ML Risk Analysis → Explainability → Human Review → Claims Officer Decision
```

## 16. Explainability

**SHAP** (`ai_ml/explainability/shap_explainer.py`): `LinearExplainer` for Logistic Regression, `TreeExplainer` for Random Forest, both run against the fitted `ColumnTransformer`'s actual output space (so one-hot-expanded feature names are real, not guessed). Example, `CLM-000640` (Logistic Regression, p=1.000, one of the 5 highest-scored test claims):

```
Fraud Screening Risk: HIGH
Top contributing factors:
1. DOCUMENT_INCONSISTENCY  – Information across submitted documents is inconsistent.
2. UNUSUAL_CLAIM_PATTERN   – The claim contains a pattern that differs from typical claims.
These are risk contributors, not proof of fraud. Final decision remains with the Claims Officer.
```
Full example set (5 claims × 2 models = 10 explanations) saved to `ai_ml/model_artifacts/shap_example_explanations.json`.

**Reason codes** (`ai_ml/explainability/reason_codes.py`): a single shared vocabulary (`DOCUMENT_INCONSISTENCY`, `REPAIR_ESTIMATE_ANOMALY`, `DUPLICATE_EVIDENCE`, `UNUSUAL_CLAIM_PATTERN`) used by *both* the rule baseline's triggered-rule output and the SHAP top-feature mapping, so a Claims Officer sees the same language regardless of which approach flagged a claim. Language is deliberately hedged ("risk contributors, not proof") — never "fraud confirmed."

## 17. Recommended Step 5.3

1. Repeat this same experiment for the secondary targets identified in Step 5.1 (`frd_Risk_Category`, `cdc_Overall_Consistency_Status`, `est_Excessive_Claim_Amount_Indicator`), reusing the same leakage-safe pipeline.
2. Investigate whether a narrower rule baseline (higher `overall_threshold`, or dropping the noisiest boolean flag) improves precision without a large recall cost — calibrated on training data only, exactly as Section 6 already does.
3. Add repeated/stratified cross-validation for both the model comparison and the threshold calibration, to put confidence intervals around the Section 9 metrics given the small positive-class count (~21 in test).
4. Only after 1–3: consider a small hyperparameter search for Random Forest (or a gradient-boosting alternative), still bounded by the explainability requirement.
5. Continue to label every result as synthetic-data validation, per Section 15, in any paper, poster, or demo built from this step.

---

## Files created this step

**Dependencies:** `ai_ml/requirements.txt`

**Baseline:** `ai_ml/baselines/__init__.py`, `ai_ml/baselines/rule_based_fraud.py`

**Models:** `ai_ml/models/__init__.py`, `ai_ml/models/train_fraud_models.py`, `ai_ml/models/evaluation.py`

**Explainability:** `ai_ml/explainability/__init__.py`, `ai_ml/explainability/reason_codes.py`, `ai_ml/explainability/shap_explainer.py`

**Experiment runner:** `ai_ml/experiments/__init__.py`, `ai_ml/experiments/run_fraud_experiment.py`

**Tests:** `ai_ml/tests/test_fraud_pipeline.py` (15 tests, all passing)

**Generated artifacts** (gitignored, regenerable by re-running the experiment): `ai_ml/model_artifacts/confusion_matrix_{rule_baseline,logistic_regression,random_forest}.png`, `evaluation_results.json`, `rule_baseline_calibration.json`, `shap_example_explanations.json`, `test_set_predictions_and_errors.csv`, `logistic_regression_fraud_label.pkl`, `random_forest_fraud_label.pkl`

**Documentation:** `docs/project_documentation/AI_VS_NON_AI_RESULTS.md` (this report)

## Files modified

`ai_ml/models/train_fraud_models.py`'s `classify_feature_columns` was extended (during this step's own validation) to also exclude zero-information columns (100%-missing or single-constant-value) after the initial run surfaced a `veh_Vehicle_Subtype`-related scikit-learn warning — no other Step 5.1 file's behavior changed. No frontend, backend, database schema, or raw dataset file was modified.
