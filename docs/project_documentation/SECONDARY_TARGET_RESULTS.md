# Secondary Target Results (Step 5.3)

**Validation-study disclaimer:** This experiment is a validation study using the currently available CI-MICOP dataset. The dataset is synthetic/de-identified and therefore the measured performance must not be interpreted as production fraud-detection, risk-scoring, or consistency-checking accuracy. Real-world validation requires appropriately governed insurer claims data.

This report extends [AI_VS_NON_AI_RESULTS.md](AI_VS_NON_AI_RESULTS.md) (Step 5.2, `frd_Fraud_Label`) to the three secondary targets identified in [AI_ML_DATASET_AUDIT.md](AI_ML_DATASET_AUDIT.md): `frd_Risk_Category`, `cdc_Overall_Consistency_Status`, and `est_Excessive_Claim_Amount_Indicator`. It also introduces Rule Baseline v2 for fraud and a repeated-grouped-CV robustness check comparing it against the Step 5.2 results. All numbers below are actual measured output from `python -m ai_ml.experiments.run_secondary_targets_experiment`, not estimates.

---

## 1. Target audit

| Target | Type | Classes | Class distribution | Missing | Min class size |
|---|---|---:|---|---:|---:|
| `frd_Risk_Category` | multiclass (4) | Low / Medium / High / Critical | Medium 213 (32.6%), Low 198 (30.3%), High 160 (24.5%), Critical 83 (12.7%) | 0 | 83 |
| `cdc_Overall_Consistency_Status` | multiclass (3) | Match / Partial Match / Mismatch | Match 394 (60.2%), Partial Match 204 (31.2%), Mismatch 56 (8.6%) | 0 | 56 |
| `est_Excessive_Claim_Amount_Indicator` | binary | True / False | False 347 (53.1%), True 307 (46.9%) | 0 | 307 |

All three targets: `Claim_ID` unique (654 rows), verified programmatically before any modeling.

---

## 2. Target-specific leakage classification

`feature_builder.py`'s existing rule (exclude the whole source table a target lives in) was **not** copied blindly - it was verified against the real data (crosstabs/correlations) for every target, and refined only where the verification showed it was wrong. Full column-level lists are in `ai_ml/model_artifacts/secondary_targets/secondary_targets_summary.json`.

| Target | SAFE | POTENTIAL_LEAKAGE | DEFINITE_LEAKAGE |
|---|---:|---:|---|
| `frd_Risk_Category` | 189 | 12 (rest of `frd_` table) | `frd_Risk_Category`, **`frd_Fraud_Label`** |
| `cdc_Overall_Consistency_Status` | 189 | 13 (rest of `cdc_` table) | `cdc_Overall_Consistency_Status` |
| `est_Excessive_Claim_Amount_Indicator` | 198 | 3 (`est_Estimate_Anomaly_Score`, `est_Estimate_Date`, `est_Garage_ID`) | `est_Excessive_Claim_Amount_Indicator`, **`frd_Excessive_Claim_Amount_Indicator`** |

**Why `frd_Fraud_Label` is DEFINITE leakage for `Risk_Category`, not just excluded by the blanket `frd_` rule:** the crosstab shows an unusually strong, asymmetric relationship - `Fraud_Label` is **1 for 0% of Low/Medium claims (0/411) and 1 for 40.7% of High/Critical claims (99/243)**. Feeding `Fraud_Label` into a Risk_Category model would let it trivially separate two of the four classes. This is documented explicitly because a plain "exclude the target's own table" rule wouldn't catch this if `Fraud_Label` ever lived in a different table.

**Why `frd_Excessive_Claim_Amount_Indicator` is DEFINITE leakage for `Excessive_Claim_Amount_Indicator`:** it is a cross-table duplicate of the same concept, sitting in `fraud_risk_analysis` rather than `repair_estimates`. It agrees with the real target only 53.8% of the time (near coin-flip), so it isn't a hidden copy of the value - but it re-asserts the same concept and must not be used to predict its own sibling.

**Why the blanket exclusion was refined (restored to SAFE) for `Excessive_Claim_Amount_Indicator`:** `feature_builder.py`'s default rule excludes the *entire* `repair_estimates` table for this target, which would also throw away `Repair_Estimate`, `Repair_Cost`, `Parts_Cost`, `Labour_Cost`, `Painting_Cost`, `Replacement_Parts_Count`, `Repaired_Parts_Count`, and `Estimated_Repair_Days` - ordinary, legitimate pre-decision garage-estimate fields. Correlation between the repair-estimate/claim-amount ratio and the target was checked directly: **r = -0.014** (essentially zero) - these fields are not target-derived, so they were restored. (This also foreshadows the modeling result below: since even the *intended* legitimate signal barely correlates with the label, near-chance model performance was expected going in, not discovered after the fact.)

**Section 2 (target-specific leakage checks) findings, verified directly against the data:**
- `Risk_Category` vs its own `Overall_Risk_Score` / `Fraud_Risk_Score` / `Anomaly_Score`: near-identical means across all four categories (e.g. Overall_Risk_Score mean ranges only 46.1-55.3 across Low..Critical) - **not a clean derivation**, contrary to the "obvious" assumption that Risk_Category is a binned version of these scores.
- `Overall_Consistency_Status` vs the count of individual field-level `_Match` columns that are not `"Match"`: **no relationship** - claims with 0 field mismatches still land in Mismatch (1/23) and Partial Match (5/23) categories, and claims with 6-7 field mismatches still land in Match. The individual match columns do not roll up into the status.
- `Excessive_Claim_Amount_Indicator` vs `Estimate_Anomaly_Score` in the same table: **r = -0.008** (no relationship).

These are not defects in the audit - they are the central finding of this step (see [AI_ML_VALIDATION_FINDINGS.md](AI_ML_VALIDATION_FINDINGS.md)): several of CI-MICOP's labels behave as independently-generated synthetic values rather than deterministic rollups of their own visible component signals.

---

## 3-4. Modeling datasets & grouped validation

One row per `Claim_ID` for every target (654 rows, asserted). `Customer_ID` and `Claim_ID` are kept for grouping/traceability and never enter the feature matrix. Every fold below is `StratifiedGroupKFold`, grouped by `Customer_ID`, with a hard `AssertionError` if any customer appears in both the train and validation portion of a fold (see `ai_ml/secondary_targets/validation.py::make_folds`) - verified with zero overlap across all folds/targets tested.

---

## 5. Cross-validation design

5-fold `StratifiedGroupKFold`, repeated across 3 seeds (42/43/44) = 15 fold-runs per target/model. All three secondary targets have a smallest class large enough to support 5 folds (83, 56, 307 respectively - `ai_ml/secondary_targets/validation.py::choose_fold_count` requires >= `MIN_FOLDS=3`; below that a target's CV is skipped rather than forced). No target hit that limit in this run, so none was skipped.

---

## 6-9. Models, baselines, metrics, and stability (mean +/- 95% CI across 15 fold-runs)

### `frd_Risk_Category` (multiclass, chance-level accuracy = 25%)

| Model | Accuracy | Macro-F1 | Weighted-F1 | ROC-AUC (OVR macro) |
|---|---:|---:|---:|---:|
| Logistic Regression | 0.266 (std 0.020) | 0.244 (std 0.022) | 0.266 (std 0.019) | 0.498 (std 0.026) |
| Random Forest | 0.273 (std 0.039) | 0.244 (std 0.034) | 0.270 (std 0.037) | 0.509 (std 0.024) |

**No rule baseline implemented** - see Section 7.

### `cdc_Overall_Consistency_Status` (multiclass, majority-class accuracy = 60.2%)

| Model | Accuracy | Macro-F1 | Weighted-F1 | ROC-AUC (OVR macro) |
|---|---:|---:|---:|---:|
| Logistic Regression | 0.451 (std 0.015) | 0.329 (std 0.017) | 0.457 (std 0.015) | 0.535 (std 0.023) |
| Random Forest | 0.499 (std 0.018) | 0.323 (std 0.018) | 0.478 (std 0.017) | 0.511 (std 0.020) |

**No rule baseline implemented** - see Section 7. Random Forest's higher raw accuracy is driven by predicting the majority class ("Match") more often - Macro-F1 (which weights all 3 classes equally) shows it is *not* actually better at the minority classes than Logistic Regression.

### `est_Excessive_Claim_Amount_Indicator` (binary, ~53%/47% balanced)

| Approach | Accuracy | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|
| Rule baseline (repair-ratio threshold) | 0.522 | 0.165 | n/a* | 0.472 |
| Logistic Regression | 0.481 (std 0.024) | 0.451 (std 0.028) | 0.477 (std 0.029) | 0.470 (std 0.028) |
| Random Forest | 0.503 (std 0.016) | 0.228 (std 0.029) | 0.458 (std 0.022) | 0.458 (std 0.014) |

\* ROC-AUC not tracked separately for the rule baseline's CV run (PR-AUC was the tracked headline metric); PR-AUC of 0.472 is essentially identical to the 46.9% base rate of the positive class - i.e. **chance level**.

All three approaches for all three targets cluster around chance (ROC-AUC ~0.50, or PR-AUC close to the positive base rate). No approach for any secondary target shows a usable signal - full interpretation in Section 10.

**Confidence interval method:** t-distribution, `mean +/- t_crit(df=14) * (std/sqrt(15))`, computed per model/target/metric across the 15 fold-runs (`ai_ml.secondary_targets.validation.summarize_stability`). Not reported when fewer than 2 usable values exist (would be misleading, not just imprecise) - this did not occur for any of the three secondary targets since all folds produced a usable metric.

---

## 10. Model comparison & signal classification

| Target | Classification | Why |
|---|---|---|
| `frd_Risk_Category` | **NOT RELIABLE** | ROC-AUC (OVR macro) 0.50-0.51, i.e. indistinguishable from a coin flip for a 4-class problem; both models perform *worse* than the always-predict-majority-class baseline (32.6% for "Medium") on plain accuracy in most folds. Leakage-safe features carry no usable signal for this target. |
| `cdc_Overall_Consistency_Status` | **NOT RELIABLE** | ROC-AUC (OVR macro) 0.51-0.54 (marginally above chance but not stable enough to trust - CIs cross 0.50 for Random Forest). Accuracy above the 60.2% majority-class rate only for Random Forest (49.9% < 60.2%, i.e. *below* the majority baseline) - neither model beats "always predict Match." |
| `est_Excessive_Claim_Amount_Indicator` | **WEAK SIGNAL (rule baseline) / NOT RELIABLE (ML)** | Rule baseline PR-AUC (0.472) sits almost exactly at the 46.9% base rate - i.e. the repair-ratio signal, while legitimate and leakage-free, carries essentially no discriminative power for this label. Both ML models perform at or below chance (PR-AUC 0.458-0.470 vs 0.469 base rate; ROC-AUC 0.46-0.48). |

These categories are **not** defined by an arbitrary accuracy cutoff. They follow directly from comparing each result to its own chance baseline (majority-class rate for accuracy, positive-class rate for PR-AUC, 0.50 for ROC-AUC), checking whether the 95% CI excludes that baseline, and confirming the result is leakage-safe. None of the three secondary targets clears that bar; none are labeled STRONG or MODERATE because doing so would not be supported by the actual numbers.

---

## 11. Target relationship analysis (descriptive only)

| Pair | Finding |
|---|---|
| `Risk_Category` vs `Fraud_Label` | **Strong, asymmetric coupling.** Fraud rate is 0% for Low/Medium claims (0/411) vs 40.7% for High/Critical claims (99/243). This is almost certainly a generation-time rule ("only High/Critical-risk claims can be flagged fraud"), not something either target's own component scores explain (see Section 2). |
| `Risk_Category` vs `Excessive_Claim_Amount_Indicator` | Roughly proportional across all 4 categories (excessive-amount rate 37-50%) - no meaningful coupling. |
| `Risk_Category` vs `Consistency_Status` | Roughly proportional across all 4 categories - no meaningful coupling. |
| `Consistency_Status` vs `Excessive_Claim_Amount_Indicator` | Roughly proportional (44-49% True rate in each status) - no meaningful coupling. |
| `Consistency_Status` vs `Fraud_Label` | Roughly proportional (14-21% fraud rate in each status) - no meaningful coupling. |
| `Excessive_Claim_Amount_Indicator` vs `Fraud_Label` | Roughly proportional (14.7% vs 17.2%) - no meaningful coupling. |

Only the `Risk_Category` <-> `Fraud_Label` relationship is structurally significant; it is treated as leakage (Section 2), never as a predictive feature.

---

## 12. Rule Baseline v2 (fraud) - evaluated on the same Step 5.2 test set

Step 5.2's baseline effectively used an OR-like rule: any one of three weight-1.0 boolean flags (`cross_document_mismatch`, `excessive_repair_estimate_flag`, `duplicate_evidence`) was enough to flag a claim (`overall_threshold=1.0`), which is why it over-triggered (130/134 test claims flagged, Recall 0.905, Precision 0.146).

**Calibration procedure (training data only):** an inner grouped train/validation split of the Step 5.2 TRAIN set (390 inner-train / 130 inner-validation claims, `GroupShuffleSplit(test_size=0.25, random_state=42)`), scanning `overall_threshold` in `{0.5, 1.0, ..., 3.5}` and picking the value that maximizes F1 on inner-validation. Chosen: **`overall_threshold = 2.0`** (now requires two independent signals, not one). The final screener was then re-fit on the full training set with that threshold and evaluated once on the untouched Step 5.2 test set.

| | Precision | Recall | F1 | PR-AUC | Flagged / 134 |
|---|---:|---:|---:|---:|---:|
| Rule Baseline v1 (threshold=1.0, Step 5.2) | 0.146 | 0.905 | 0.252 | 0.167 | 130 |
| Rule Baseline v2 (threshold=2.0, calibrated) | 0.161 | 0.857 | **0.271** | 0.167 | 112 |

Raising the threshold modestly improved Precision (0.146 -> 0.161) and F1 (0.252 -> 0.271) while giving up some Recall (0.905 -> 0.857) - a real, if small, improvement, not a dramatic fix (both are still far from a usable Precision). **PR-AUC is identical (0.167) for v1 and v2 by construction**: PR-AUC is computed from the continuous `Rule_Baseline_Score` (same weighted-sum formula in both versions), while `overall_threshold` only changes where the binary cutoff is drawn on that same score - it does not change the underlying ranking of claims by risk.

---

## 13. Fraud repeated-grouped-CV robustness

Step 5.2's single train/test split found Random Forest PR-AUC (0.233) > Logistic Regression (0.222) > Rule Baseline (0.167). Repeating the same comparison across 5-fold x 3-seed grouped CV (15 fold-runs) on the *full* 654-claim dataset:

| Approach | PR-AUC (mean, std) | F1 (mean, std) | Recall (mean) |
|---|---:|---:|---:|
| Logistic Regression | 0.189 (std 0.036) | 0.167 (std 0.050) | 0.209 |
| Random Forest | 0.177 (std 0.039) | 0.074 (std 0.085) | 0.050 |
| Rule Baseline v1 | 0.156 (std 0.023) | 0.256 (std 0.014) | 0.960 |
| Rule Baseline v2 | 0.156 (std 0.023) | 0.256 (std 0.024) | 0.798 |

*(Rule Baseline v2 here uses the single fixed `overall_threshold=2.0` found in Section 12, applied unchanged across all CV folds - it is not re-calibrated per fold, to keep the comparison to a single, reproducible rule definition rather than 15 different ones.)*

**The Random Forest > Logistic Regression PR-AUC ordering from Step 5.2 does NOT hold under repeated CV - it reverses.** Logistic Regression (0.189) is now higher than Random Forest (0.177), a gap of only 0.012, well within the combined noise band (combined std 0.033 > |gap| 0.012). **Conclusion: the ordering is not stable - Step 5.2's single-split result should be read as one sample from a noisy distribution, not as proof Random Forest is the better fraud model.** All four approaches (including both rule baselines) cluster in the same 0.16-0.19 PR-AUC range once repeated validation is applied.

---

## 14. Explainability

SHAP (`TreeExplainer`) was generated for the Random Forest model on `est_Excessive_Claim_Amount_Indicator` (chosen as the secondary target with the most legitimate, leakage-free signal available, even though its measured CV performance is near-chance - see the explicit caveat printed with these results). Five example claim explanations were produced (`CLM-000484`, `CLM-000646`, `CLM-000565`, `CLM-000501`, `CLM-000641`, all scored MEDIUM risk), each labeled:

> "Model contribution / screening signal" - **not** "Confirmed cause"

**This is included to demonstrate the explainability pipeline generalizes beyond fraud, not as evidence this model is production-ready** - its own CV numbers (Section 9) show it performs at chance. No explanations were generated for `Risk_Category` or `Consistency_Status`, since neither model showed any usable signal to explain.

---

## 15. Figures

Saved under `docs/project_documentation/figures/`:
1. `target_class_distributions.png` - class counts for all three secondary targets.
2. `secondary_target_model_comparison.png` - mean CV headline metric (PR-AUC or macro-F1) per target/model.
3. `fraud_pr_auc_cv_comparison.png` - fraud PR-AUC mean +/- std across repeated CV for all four approaches (Section 13).

---

## Files created this step

- `ai_ml/secondary_targets/__init__.py`, `target_audit.py`, `validation.py`, `cv_runner.py`, `rule_baselines.py`
- `ai_ml/experiments/run_secondary_targets_experiment.py`
- `ai_ml/tests/test_secondary_targets.py`
- `docs/project_documentation/SECONDARY_TARGET_RESULTS.md` (this file), `AI_ML_VALIDATION_FINDINGS.md`
- `docs/project_documentation/figures/*.png` (3 figures)
- `ai_ml/model_artifacts/secondary_targets/secondary_targets_summary.json` (gitignored artifact)

No file from Step 5.1/5.2 (`feature_builder.py`, `train_fraud_models.py`, `rule_based_fraud.py`, `run_fraud_experiment.py`, etc.) was modified - all reused as-is via import.
