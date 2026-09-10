# CI-MICOP Step 5.1 — AI/ML Foundation & Dataset Audit

**Scope:** read-only audit of `ai_ml/datasets/CI_MICOP_15_Tables_Complete/` plus a reusable, verified preprocessing pipeline under `ai_ml/common/`. No frontend, backend, PostgreSQL schema, or raw dataset file was modified. No model was trained. All numbers below were produced by running `python -m ai_ml.run_audit` and the supporting checks against the actual Excel files — nothing here is estimated or invented.

---

## 1. Dataset Inventory

16 files were found; 15 map 1:1 to the CI-MICOP database tables, and one (`01_authentication_users.xlsx`) is a superseded duplicate.

| # | File | Table | Rows | Cols | Grain | Level |
|---|------|-------|-----:|-----:|-------|-------|
| — | `CI_MICOP_Authentication_Users.xlsx` | `authentication_users` | 660 | 14 | 1 row / login account | account |
| — | `01_authentication_users.xlsx` | *(superseded — not used)* | 600 | 15 | — | — |
| 02 | `02_customers.xlsx` | `customers` | 600 | 19 | 1 row / customer | customer |
| 03 | `03_vehicles.xlsx` | `vehicles` | 905 | 34 | 1 row / vehicle | vehicle |
| 04 | `04_policies.xlsx` | `policies` | 905 | 31 | 1 row / policy | policy |
| 05 | `05_claims.xlsx` | `claims` | 654 | 45 | 1 row / claim | **claim (anchor)** |
| 06 | `06_accidents.xlsx` | `accidents` | 654 | 18 | 1 row / claim | claim |
| 07 | `07_documents.xlsx` | `documents` | 3936 | 11 | many rows / claim | document |
| 08 | `08_vehicle_damage.xlsx` | `vehicle_damage` | 654 | 12 | 1 row / claim | claim |
| 09 | `09_repair_estimates.xlsx` | `repair_estimates` | 654 | 16 | 1 row / claim | claim |
| 10 | `10_evidence.xlsx` | `evidence` | 1301 | 13 | many rows / claim | evidence |
| 11 | `11_surveyor_inspections.xlsx` | `surveyor_inspections` | 531 | 14 | 0–1 row / claim | claim |
| 12 | `12_cross_document_consistency.xlsx` | `cross_document_consistency` | 654 | 16 | 1 row / claim | claim |
| 13 | `13_fraud_risk_analysis.xlsx` | `fraud_risk_analysis` | 654 | 16 | 1 row / claim | claim |
| 14 | `14_claim_decision_audit.xlsx` | `claim_decision_audit` | 654 | 15 | 1 row / claim | claim |
| 15 | `15_tp_claims.xlsx` | `tp_claims` | 186 | 16 | 0–1 row / claim | claim |

**Why `CI_MICOP_Authentication_Users.xlsx` and not `01_authentication_users.xlsx`:** this repeats the same authoritative-file decision already documented in the Step 2 database report (660 rows vs. 600, `Employee_ID` correctly typed as text, matches the live database). `ai_ml/common/data_loader.py` encodes this choice explicitly so the AI dataset never silently diverges from what Postgres actually contains.

### Verified claim-cardinality (the key finding for Section 4)

| Table | Rows / 654 claims | Per-claim | Join treatment |
|---|---|---|---|
| `accidents` | 654 / 654 | exactly 1 | direct left join |
| `vehicle_damage` | 654 / 654 | exactly 1 | direct left join |
| `repair_estimates` | 654 / 654 | exactly 1 | direct left join |
| `cross_document_consistency` | 654 / 654 | exactly 1 | direct left join |
| `fraud_risk_analysis` | 654 / 654 | exactly 1 | direct left join |
| `claim_decision_audit` | 654 / 654 | exactly 1 | direct left join |
| `surveyor_inspections` | 531 / 654 | 0 or 1 (123 claims have **none**) | direct left join, NaN = no inspection |
| `tp_claims` | 186 / 654 | 0 or 1 (only 3rd-party claims) | direct left join, NaN = no TP claim |
| `documents` | 3936 / 654 | 1–8 (avg 6.02) | **must aggregate** |
| `evidence` | 1301 / 654 | 1–3 (avg 1.99) | **must aggregate** |

Referential integrity was checked in both directions: **zero** orphan `Claim_ID`/`Vehicle_ID`/`Policy_ID`/`Customer_ID` values were found in any child table, and every `surveyor_inspections.Surveyor_ID` maps to a real `Surveyor`-role account.

### Relationship map

```
customers(600) ──< claims(654) >── vehicles(905, 1 claim each) 
                       │                policies(905, 1 claim each)
                       ├── accidents (1:1)
                       ├── vehicle_damage (1:1)
                       ├── repair_estimates (1:1)
                       ├── cross_document_consistency (1:1)
                       ├── fraud_risk_analysis (1:1)
                       ├── claim_decision_audit (1:1)
                       ├── surveyor_inspections (0:1, 123 missing)
                       ├── tp_claims (0:1, only 186 present)
                       ├── documents (1:many, avg 6.02)
                       └── evidence (1:many, avg 1.99)
```

Only **654 of 905** vehicles/policies (72.3%) ever appear in a claim — expected, since most insured vehicles never file one. Only **487 of 600** customers (81.2%) appear in a claim.

---

## 2. Data-Quality Audit

Full per-table missing/duplicate/range output is reproducible via `python -m ai_ml.run_audit`; the columns with non-zero missingness are:

| Table.Column | Missing | % | Explanation |
|---|---:|---:|---|
| `authentication_users.Employee_ID` | 600/660 | 90.9% | Only Surveyor/Officer accounts have one (structural, not a defect) |
| `authentication_users.Customer_ID` | 60/660 | 9.1% | Staff accounts have no Customer_ID (structural) |
| `vehicles.Vehicle_Subtype` | 905/905 | **100%** | Column is entirely empty — zero information |
| `policies.Endorsement_Number` | 826/905 | 91.3% | Only endorsed policies have one (structural) |
| `claims.Claim_Number_Child` | 515/654 | 78.8% | Only split/child claims have one (structural) |
| `accidents.FIR_Number` | 203/654 | 31.0% | See inconsistency finding below |
| `claim_decision_audit.Escalated_To` | 465/654 | 71.1% | See inconsistency finding below |

No fully-duplicated rows and no duplicated primary keys were found in any of the 15 tables. No negative values were found in any numeric column (amounts, day-counts, scores) across the entire dataset.

**Duplicate business identifiers checked and clean:** `Registration_Number`, `Chassis_Number`, `Engine_Number` (vehicles), `Email`, `Phone`, `Customer_Name`+`Date_of_Birth` (customers) — zero duplicates on any of them, so there is no evidence of the same real-world entity hiding under two different IDs.

### Suspicious / inconsistent values found (genuine data-quality findings, not modified)

1. **`vehicles.Policy_Start_Date` / `Policy_End_Date` are constant** across all 905 rows (`2026-09-02` / `2027-09-02`) — a single stamped placeholder value, inconsistent with the real, properly varied dates in `policies.Policy_Start_Date/End_Date` (range `2024-09-03`→`2027-08-31`). **Do not use the vehicles-table copies of these columns** — they carry no information and contradict the policies table.
2. **`authentication_users.Last_Login` and `Created_Date` are a single constant value** for all 660 rows — both were evidently stamped at export time, not genuine historical activity. Zero predictive information; excluded from modeling.
3. **`accidents.FIR_Number` presence is statistically independent of `Police_Report_Available`** (29.6% null when no police report vs. 32.3% null when a police report *was* filed — almost identical). In a real system an FIR number should only exist when a police report was filed; here it does not track that field at all, indicating these two columns were generated independently rather than logically linked.
4. **`claim_decision_audit.Escalated_To` is statistically independent of `Escalation_Status`**: 28.9% of "Not Escalated" rows still have an `Escalated_To` value, and 71.0% of "Escalated" rows have **no** `Escalated_To` value. This is internally inconsistent and is the strongest single piece of evidence (see Section 5) that the audit-table fields are synthetic placeholders rather than a logically generated workflow trail.
5. **Claim dates extend to 2027-06-22** while `Policy_Start_Date`/`Policy_End_Date` in `policies` only run to `2026-08-31`/`2027-08-31` — internally consistent enough (policies do cover the later claim dates), but worth flagging that the dataset's reference "today" is clearly later than a typical present-day system clock; do not assume `Claim_Date` is always in the past when computing recency features.
6. **Redundant columns across tables:** `Document_Mismatch_Indicator`, `Vehicle_Damage_Mismatch_Indicator`, and `Accident_Details_Mismatch_Indicator` are each duplicated verbatim in both `cross_document_consistency` and `fraud_risk_analysis`. `Excessive_Claim_Amount_Indicator` is duplicated in both `repair_estimates` and `fraud_risk_analysis`. `Damage_Severity` appears independently in `vehicle_damage`, `evidence`, and `surveyor_inspections` (three different assessments of the same concept, not necessarily in agreement — worth comparing rather than assuming they agree). The claim-level dataset keeps all copies (prefixed by source table, e.g. `cdc_Document_Mismatch_Indicator` vs. `frd_Document_Mismatch_Indicator`) specifically so this duplication stays visible instead of one silently overwriting the other.

---

## 3. Claim-Level Modeling Dataset Design

Implemented in `ai_ml/common/preprocessing.py` + `ai_ml/common/feature_builder.py`, run via `ai_ml/run_audit.py`.

**Rule applied:** `claims` (654 rows) is the anchor. Every table verified as exactly 1:1 or 0:1 per claim (see table above) is left-joined directly. The two genuinely one-to-many tables — `documents` and `evidence` — are **aggregated to one row per claim first**, never joined raw:

- **`aggregate_documents`**: `document_count`, `distinct_document_types`, mean/min OCR confidence, mean completeness, any-mismatch flag, plus one fixed-width one-hot column per the 8 known document types (`has_document_FIR`, `has_document_RC`, …) — so "which documents were submitted" is captured without letting row count vary.
- **`aggregate_evidence`**: `evidence_count`, `distinct_evidence_types`, mean image quality, any-damage-detected flag, any-duplicate flag, mean confidence, plus one one-hot column per the 3 evidence types.

Every joined table's non-key columns are prefixed by source (`veh_`, `pol_`, `cust_`, `acc_`, `dmg_`, `est_`, `cdc_`, `frd_`, `aud_`, `insp_`, `tp_`) so the duplicated columns noted in Section 2.6 stay distinguishable instead of silently colliding.

**Verified result** (`python -m ai_ml.run_audit`):
```
raw claims rows:       654
claim-level rows out:  654
claim-level columns:   254
VERIFIED: one row per claim, no rows silently dropped or duplicated.
```
`feature_builder.build_claim_level_dataset()` raises an `AssertionError` if the row count ever changes or `Claim_ID` stops being unique — this is a hard guard, not just a printed check, so a future edit that reintroduces a fan-out join fails loudly instead of silently corrupting the dataset.

---

## 4. Target / Label Audit

No field in this dataset should be assumed to be verified ground truth. Every candidate was checked against the columns that would supposedly explain it, specifically to test whether it behaves like a real generated label or an independently-assigned placeholder.

| Candidate | What it represents | Genuine / derived / synthetic? | Usable as a target? |
|---|---|---|---|
| `fraud_risk_analysis.Fraud_Label` (0/1) | A binary fraud flag | **Synthetic, weakly-noisy relationship to its own siblings** — see test below | Yes, as a clearly-labeled proxy target only |
| `fraud_risk_analysis.Risk_Category` (Low/Medium/High/Critical) | A risk tier | Synthetic, same source table as `Fraud_Label` | Yes, as a secondary/multi-class proxy target |
| `cross_document_consistency.Overall_Consistency_Status` (Match/Partial/Mismatch) | Aggregate consistency verdict | **Not derivable from its own 9 field-level `*_Match` columns** — see test below | Usable, but its relationship to the detailed fields is not what the name implies |
| `repair_estimates.Excessive_Claim_Amount_Indicator` | Repair-estimate anomaly flag | Fairly balanced (46.9%/53.1%); `Estimate_Anomaly_Score` is near-perfectly uniform on [0,1] (25/50/75th percentiles land exactly on 0.25/0.50/0.75) — classic random-uniform generation signature | Usable as a target for a repair-estimate-leakage sub-model, but `Estimate_Anomaly_Score` should not be trusted as a real anomaly measure |
| `claims.Final_Decision` (Approved/Partially Approved/Rejected) | The claim officer's final call | Present for **all 654 claims** — even ones whose `Claim_Status` is still "Pending"/"Under Investigation" | Usable as the primary business-relevant target for decision-support modeling, with strict pre-decision feature discipline (Section 5) |
| `claim_decision_audit.AI_Recommendation` | A recorded "AI" suggestion | **Statistically independent of `Final_Decision`** — see test below | **Not usable as ground truth or as a feature** — it does not reflect a real model's behavior in this export |

**Evidence that `Fraud_Label` is not a simple derived rule:** grouping the 9 boolean fraud indicators by their sum and cross-tabulating against `Fraud_Label` shows no threshold behavior — claims with 0 flagged indicators and claims with 8 flagged indicators both contain a mix of label 0 and label 1. `Overall_Risk_Score` is higher on average for label 1 (mean 64.2) than label 0 (mean 48.2), but the ranges overlap almost completely (label-0 claims reach a max of 100; label-1 claims start as low as 50). **Conclusion: `Fraud_Label` correlates with `Overall_Risk_Score` but is not a hard function of it or of the boolean indicators — it behaves like an independently sampled synthetic label with a soft statistical relationship to its sibling columns, not verified real-world fraud outcomes.**

**Evidence that `Overall_Consistency_Status` is not a rule over the 9 `*_Match` columns:** a straightforward majority/threshold rule over the 9 field-level match columns agrees with the actual label only **39.0%** of the time, and the mean mismatch-count is nearly identical across all three status categories (0.89 for "Match", 0.86 for "Mismatch", 0.96 for "Partial Match" — i.e., claims labeled "Mismatch" do not, on average, have more field-level mismatches than claims labeled "Match"). **Conclusion: treat `Overall_Consistency_Status` as an independently-assigned synthetic label, not a genuine aggregate of the 9 detailed fields.**

**Evidence that `AI_Recommendation` is not linked to the real outcome:** cross-tabulating `AI_Recommendation` against `Final_Decision` shows near-uniform counts in every cell (e.g. `Approve`→`Approved` 81, `Approve`→`Partially Approved` 78, `Approve`→`Rejected` 71 — i.e. recommending "Approve" makes almost no difference to the actual outcome distribution). **Conclusion: the entire `claim_decision_audit` AI-recommendation/confidence trail is a synthetic placeholder and must never be treated as a real model's historical output.**

**Explicit limitation statement (per the instruction not to assume any field is ground truth):** every "AI"-named or "risk/consistency-scored" column in this dataset (`Fraud_Label`, `Fraud_Risk_Score`, `Anomaly_Score`, `Overall_Risk_Score`, `Risk_Category`, `Overall_Consistency_Status`, `Estimate_Anomaly_Score`, `AI_Recommendation`, `AI_Confidence_Score`) is a **synthetically generated proxy**, not a verified real-world outcome. Any model trained against them should be described as learning to reproduce this dataset's synthetic labeling function, not as detecting real fraud — this must be stated plainly in any report, demo, or paper produced from Step 5.2 onward.

---

## 5. Data Leakage Audit

| Category | Columns | Why |
|---|---|---|
| **Definitely leaked** (never use as a feature) | `claims.Final_Decision`, `Decision_Date`, `Decision_Reason`, `Approved_Amount`, `Claim_Processing_Days`, `Repair_Duration_Days`; all of `claim_decision_audit.*` (`aud_` prefix); all of `tp_claims.*` (`tp_` prefix); all `TP_*`, `Wider_Legal_Liability_Amount`, `PA_*_Amount`, `Open_Provision_*`, `Closing_Provision_*` on `claims` | Only known once the claim is decided/settled, or generated by the very audit process a decision-support model would sit upstream of |
| **Leaked *for a specific target* (same-table siblings)** | If target = `Fraud_Label` or `Risk_Category`: exclude the rest of `fraud_risk_analysis.*` (`frd_`). If target = `Overall_Consistency_Status`: exclude the rest of `cross_document_consistency.*` (`cdc_`). If target = `Excessive_Claim_Amount_Indicator`: exclude the rest of `repair_estimates.*` (`est_`) | These columns are produced by the same generation/analysis process as the candidate target itself — using them as inputs is circular |
| **Leakage-adjacent (exclude by default, may experiment with care)** | `claims.Claim_Status` | Its own vocabulary (`Approved`/`Rejected`/`Partially Approved`/…) directly echoes `Final_Decision` |
| **Requires special handling** | `est_Actual_Repair_Days` (only known after repair completes); `insp_*` (only ~81% coverage, missing-not-at-random — presence itself may be informative, but must not be silently imputed); `Estimate_Anomaly_Score`, `frd_Anomaly_Score` (near-uniform-random signature, verify before trusting as a real signal) | |
| **Safe pre-decision features** | `customers.*`, `vehicles.*` (except the constant policy-date columns), `policies.*`, `claims.*` intake fields (`Claim_Type`, `Claim_Amount`, `Claim_Date`, `Claim_Intimation_Date`, `Place_of_Accident`, descriptive/code fields), `accidents.*`, the aggregated `documents`/`evidence` summaries, `insp_*` (with the missing-inspection caveat above) | Available at or before the point a claims officer would need a decision-support signal |

`ai_ml/common/feature_builder.py` implements this as code, not just documentation: `leaked_columns_for_target(target, df)` and `safe_feature_columns(target, df)` compute the exact excluded/included column lists per candidate target. The run confirmed, e.g., for `frd_Fraud_Label`: **187 safe feature columns, 61 excluded**; for `Final_Decision`: **201 safe, 47 excluded**.

---

## 6. Duplicate / Group-Leakage Analysis

| Check | Result |
|---|---|
| Same customer in multiple claims? | **Yes** — 151 of 487 customers (31.0%) who ever file a claim have 2 or 3 claims (max 3) |
| Same vehicle in multiple claims? | **No** — every one of the 654 claiming vehicles appears in exactly 1 claim |
| Same policy in multiple claims? | **No** — every one of the 654 claiming policies appears in exactly 1 claim |
| Same document reused across *different* claims? | **No** — 0 of 3936 `Document_Name` values appear under more than one `Claim_ID` |
| Same evidence file reused across *different* claims? | **No** — 0 of 1301 `File_Name` values appear under more than one `Claim_ID` |

**Recommended split strategy:** split by **`Customer_ID`**, not by raw claim row (a `GroupKFold`/grouped train-test split keyed on `Customer_ID`). Because 31% of customers contribute more than one claim, a naive random row-level split would let one customer's claims appear in both train and test, leaking that customer's demographic/behavioral signal across the split and inflating apparent performance. Splitting by vehicle or policy is unnecessary (no repeats exist), but customer-level grouping is not optional.

**A genuine dataset limitation, not a defect:** the complete absence of repeat claims on the same vehicle, and of any cross-claim document/evidence reuse, means this synthetic dataset **cannot** be used to validate detection of two classic real-world fraud patterns — the same vehicle claiming repeatedly, and the same photo/document being resubmitted across unrelated claims. `Duplicate_Evidence_Indicator` (52.8% True) and `Document_Mismatch_Indicator`-type flags exist as pre-set boolean columns, but they are not backed by any actual cross-claim duplication in the raw files — treat them as synthetic per-row flags, not evidence of verified real duplication.

---

## 7. Class Balance

| Target | Classes (count, %) | Imbalance ratio | Accuracy misleading? |
|---|---|---|---|
| `Fraud_Label` | 0: 555 (84.9%) · 1: 99 (15.1%) | **5.6 : 1** | **Yes** — predicting "not fraud" for everyone scores 84.9% accuracy while catching zero fraud |
| `Risk_Category` | Medium 213 (32.6%) · Low 198 (30.3%) · High 160 (24.5%) · Critical 83 (12.7%) | ~2.6 : 1 (Medium vs. Critical) | Mild — macro-averaged metrics still needed |
| `Overall_Consistency_Status` | Match 394 (60.2%) · Partial Match 204 (31.2%) · Mismatch 56 (8.6%) | **7.0 : 1** (Match vs. Mismatch) | **Yes** — the operationally important "Mismatch" class is the smallest |
| `Excessive_Claim_Amount_Indicator` | False 347 (53.1%) · True 307 (46.9%) | 1.1 : 1 | No — close to balanced |
| `Final_Decision` | Partially Approved 222 (33.9%) · Approved 218 (33.3%) · Rejected 214 (32.7%) | 1.04 : 1 | No — almost perfectly balanced |

**Recommended metrics, chosen per target rather than applied blindly:**
- `Fraud_Label`, `Overall_Consistency_Status` (imbalanced, minority class matters most): **Precision, Recall, F1 on the minority class, PR-AUC** (more informative than ROC-AUC under this level of imbalance), and a full confusion matrix. Plain accuracy should not be reported as the headline number for either.
- `Risk_Category`: macro-averaged Precision/Recall/F1 across the 4 classes, plus a confusion matrix (per-class recall matters more than overall accuracy since "Critical" is the smallest and most operationally important class).
- `Excessive_Claim_Amount_Indicator`, `Final_Decision`: accuracy is not misleading here given the near-balance, but Precision/Recall/F1/confusion-matrix should still be reported for consistency and to catch any per-class weaknesses accuracy would hide.

No rebalancing (SMOTE, undersampling, class weights, etc.) has been applied — per the instruction, this is deferred to Step 5.2 model development, to be chosen and justified against the real class counts above.

---

## 8. "Without AI" Baseline Design

A transparent, non-ML, rule-based screening baseline, implemented as a **configurable framework** rather than hard-coded thresholds — the dataset audit gives no independent way to justify a specific numeric cutoff (e.g. "OCR confidence below 0.7 is suspicious") without either an existing regulatory/business rule or a labeled validation set to calibrate against, and neither exists yet.

Design (see `ai_ml/common/feature_builder.py` output columns — the baseline consumes exactly the "safe feature" columns, nothing else):

| Rule family | Signal used (all pre-decision / safe) | Threshold status |
|---|---|---|
| Document completeness | `document_count`, `distinct_document_types`, `has_document_*` one-hot flags, `document_completeness_mean` | **Requires calibration** — flag as "incomplete" below some completeness cutoff, cutoff TBD |
| Document quality | `document_ocr_confidence_mean` / `_min` | **Requires calibration** |
| Evidence pattern | `evidence_count`, `evidence_any_duplicate_flag`, `distinct_evidence_types` | **Requires calibration**, and per Section 6, `evidence_any_duplicate_flag` is not backed by real cross-claim duplication in this dataset — flag with reduced confidence |
| Repair-estimate reasonableness | `est_Repair_Estimate`, `est_Parts_Cost`, `est_Labour_Cost`, `est_Painting_Cost` vs. `Claim_Amount` | **Requires calibration** |
| Timing pattern | Days between `pol_Policy_Start_Date` and `Claim_Date` (claim soon after policy start) | **Requires calibration** |
| Consistency signal | `cdc_*_Match` field-level flags (only when the baseline is *not* being compared against `Overall_Consistency_Status` as the target, to avoid the Section 5 same-table leakage) | Rule is transparent (count of "Mismatch"/"Partial Match" fields), no calibration needed for the count itself, only for the alert cutoff |

Every threshold is left as a named, documented configuration value rather than an invented number. **The baseline and any ML model in Step 5.2 must be evaluated on the exact same held-out test set and the same legitimate target** (most likely `Fraud_Label`, with `Risk_Category`/`Overall_Consistency_Status` as secondary comparisons) so the eventual "Rule-Based vs. ML" comparison in the project's core contribution is apples-to-apples.

---

## 9. AI Model Plan (not trained yet)

Given ~654 claims, a 15.1% positive rate for the primary target, and a firm requirement for explainability to support (not replace) a claims officer, the smallest practical model set is:

1. **Logistic Regression** — the transparent baseline classifier. Coefficients are directly interpretable ("a mismatch in accident location is associated with a 2.3x increase in odds"), trains reliably on ~650 rows, and gives a principled probability output for the "Confidence / Human Review" stage of the architecture diagram.
2. **Random Forest** (or Gradient Boosting, e.g. `HistGradientBoostingClassifier`) — captures non-linear interactions (e.g. "high repair estimate **and** recent policy start **and** document mismatch" is a compound signal a linear model cannot represent well) while still supporting SHAP explanations. Tree ensembles are also robust to the mixed numeric/boolean/categorical feature set built in Section 3 without extensive scaling.
3. **No third model / no deep learning is justified.** ~654 rows is far too small to benefit from a neural network, and it would materially weaken explainability — directly against the project's stated customer-centric, human-in-the-loop principle. If a future step adds substantially more real or synthetic-but-realistic data, a gradient-boosting library (XGBoost/LightGBM) is the natural next step before any deep model.

Both models should be trained per candidate target independently (`Fraud_Label` primary; `Risk_Category`, `Overall_Consistency_Status`, `Excessive_Claim_Amount_Indicator` as secondary sub-models matching the architecture's four analysis boxes), each restricted to that target's `safe_feature_columns(...)` output, each evaluated with a customer-grouped split (Section 6) and the metrics chosen in Section 7.

---

## 10. Explainable AI Plan

Two distinct explanation layers, kept clearly separate so a claims officer always knows which is which:

1. **Model-based explanations (SHAP).** For the tree-ensemble model, SHAP values attribute each prediction to specific input features (e.g. "+0.18 from `document_completeness_mean` being low", "+0.09 from a policy started 12 days before the claim"). This is a Step 5.2+ deliverable (`shap` is not yet installed — see Section 12) but the leakage-safe feature set from Section 5 is exactly what a SHAP explanation would run against, so no rework is needed later.
2. **Rule-based reason codes.** Independent of any model, the Section 8 baseline rules generate plain-language reason codes ("Document set incomplete: 3 of 8 expected types missing", "Repair estimate 2.1x the median for this claim type"). These remain available even if the ML model is unavailable or under review, and they double as a sanity check on the model's own explanations.

**Target output shape for a claims officer** (illustrative structure only — no real number is being asserted here):
```
Risk Level: <derived from model probability + rule count, calibrated in Step 5.2>
Main contributing factors:
- <top SHAP feature, in plain language>
- <top SHAP feature, in plain language>
- <matching rule-based reason code, if any>
```
The explanation is explicitly a decision-support artifact: it must never render a verb like "rejected" or "approved" — only risk/consistency information for the officer described in Section 11's Make Decision page, who remains the sole decision-maker (already enforced in Step 4.5's frontend: no automatic decision endpoint exists, and the UI states "AI provides decision support. Final decision remains with the Claims Officer.").

---

## 11. Novelty Analysis

No claim of "first", "novel algorithm", or "new AI model" is made — none is evidenced by this audit. What *is* technically feasible with the current dataset, and can legitimately be framed as CI-MICOP's contribution, is the **integration**, not any single algorithm:

| Idea | Feasible with this dataset? | Basis |
|---|---|---|
| Cross-document narrative consistency | **Yes** | `cross_document_consistency` gives 9 field-level match signals + documents/evidence to build features from directly |
| Repair-estimate reasonableness / leakage detection | **Yes** | `repair_estimates` gives full cost breakdown + an (unreliable, per Section 4) anomaly score to compare against |
| Multi-signal risk fusion (combining the 4 architecture boxes into one risk view) | **Yes** | All 4 signal sources exist per claim (consistency, estimate, fraud indicators, evidence); this is the most defensible "integration" novelty claim |
| Explainable, human-in-the-loop investigation workflow | **Yes** | Already partly built in Step 4.5 (tabbed claim workspace, explicit "AI supports, officer decides" wording, no auto-decision endpoint) |
| Graph-based fraud relationships | **No, not with this data** | No shared garages/addresses/witnesses/phone numbers link different claims — Section 6 found zero cross-claim entity overlap beyond the expected customer repeat-claims, so there is no graph structure to mine yet |
| Customer-facing explanations | **Partially** | The Customer Portal (Step 4.3) already shows claim status/timeline; genuine AI-explanation-for-customers is not yet designed and raises separate fairness/disclosure questions best deferred |
| Regulatory/customer-rights awareness | **Not yet** | Explicitly out of scope per this step's own instructions; requires verified legal sources, not dataset analysis |

**Recommended framing:** CI-MICOP's contribution is a transparent, multi-signal, human-in-the-loop claims-risk workflow that fuses independently-checkable evidence (documents, consistency, repair estimate, fraud indicators) into one explained view for a claims officer — not a novel ML algorithm.

---

## 12. ACO (Ant Colony Optimization) Feasibility — preparation only, not implemented

Candidate: **Surveyor Assignment Optimization**. Checked which of the requested objective factors actually exist in the data:

| Factor | Exists? | Detail |
|---|---|---|
| Surveyor workload | **Yes — real** | `surveyor_inspections.Surveyor_ID` gives a real per-surveyor caseload: 20 of 30 Surveyor accounts have ≥1 inspection in this export, mean 26.55, range 17–36 |
| Claim/accident location | **Yes — real** | `accidents.Accident_City/State/Pincode/Location` and `surveyor_inspections.Inspection_Location` (text) exist for every claim |
| Surveyor home-base / location | **No** | `authentication_users` has no address/location field for any staff role |
| Travel distance | **No — cannot be computed** | Requires both a surveyor home-base (missing) *and* a pincode-to-coordinate reference table (not present in this dataset) |
| Claim priority | **No explicit field** | Could be proxied from `Claim_Type` or `Risk_Category`, but the latter is a same-pipeline-derived, synthetic field (Section 4) — using it to drive assignment priority is a different, acceptable use case from using it as a fraud-model feature, but should be labeled as a proxy, not a real SLA/priority field |
| Surveyor specialization | **No** | No skill/specialty field exists anywhere |
| Surveyor availability/schedule | **No** | No calendar/availability field exists anywhere |

**Conclusion:** only workload (real) and claim location (real) are directly supported. Distance, specialization, and availability are **not** present in the real dataset and must not be fabricated as if they were. **Recommendation for Step 5.2+:** build the ACO-vs-baseline comparison using the real workload/location data for those two factors, and add a clearly-labeled, separately-stored **synthetic operational scaffold** (surveyor home-base coordinates, a specialization tag, an availability calendar) generated specifically for the optimization demo — kept in its own file/module, never merged into the fraud/consistency modeling dataset, and always presented as synthetic scaffolding rather than real insurer data. Candidate metrics once that scaffold exists: total travel distance, workload-balance (variance across surveyors), assignment time, and priority-adherence — comparing "current/manual-style assignment" vs. "ACO-based assignment" on the same claim set.

---

## 13. Dataset Limitations & Research-Funding Notes

- **The dataset is synthetic.** Every "AI"-named column was shown in Section 4 to be either statistically independent of its supposed explanatory fields or to follow a suspiciously uniform-random distribution. Several structural fields (`vehicles.Policy_Start/End_Date`, `authentication_users.Last_Login/Created_Date`) are literal constants stamped at export time. This is a generated demonstration dataset, not de-identified real insurer data, and nothing in these files supports a claim otherwise.
- **Limitations of synthetic data:** models trained on it can only be shown to reproduce this dataset's synthetic generation function; they cannot be claimed to detect real fraud, and any accuracy/F1/AUC numbers from Step 5.2 must be reported as *internal, synthetic-data validation only*.
- **External validation need:** real insurer claims data (de-identified, with genuine investigator-confirmed fraud outcomes) is required before any performance claim can be generalized beyond this dataset.
- **Privacy/anonymization:** the current files already appear to be synthetic/fabricated (customer names, emails, phone numbers do not need de-identification because they were never real), but any future real-data collaboration would require formal de-identification, data-processing agreements, and IRB/ethics review appropriate to the receiving institution.
- **Future collaboration:** a realistic path is a data-sharing agreement with one insurer or a claims-data research consortium, under a university or research-institution umbrella, with a clearly scoped, time-boxed access period and independent oversight of re-identification risk.
- **Funding:** obtaining and securely processing real claims data typically requires funding for secure storage/compute, legal/compliance review, and a data-protection officer or equivalent role — this is noted here as a limitation to disclose, not something CI-MICOP currently has arranged.

---

## 14. Potential Loopholes and Mitigations

| Loophole | Impact | Mitigation |
|---|---|---|
| Data leakage via same-table sibling columns (Section 5) | Inflated, non-generalizable accuracy | `feature_builder.safe_feature_columns()` enforces exclusion in code, not just documentation |
| Synthetic-label bias (Section 4) | A model "detecting fraud" may just be learning the synthetic generator's noise pattern | Always report Step 5.2 results as synthetic-data validation, never as real-world fraud-detection accuracy |
| Class imbalance (`Fraud_Label` 5.6:1, `Overall_Consistency_Status` 7.0:1) | Accuracy looks good while missing the minority class entirely | PR-AUC + minority-class recall reported alongside accuracy (Section 7); no blind accuracy headline |
| Customer-level group leakage (31% of customers have 2–3 claims) | Optimistic train/test performance if split naively | Mandatory `Customer_ID`-grouped split (Section 6) |
| Evidence/document "duplicate" flags not backed by real duplication (Section 6) | A model may learn to trust a flag that carries no genuine duplication signal in this dataset | Document explicitly as a synthetic per-row flag; do not present as validated duplicate-detection capability |
| Over-reliance on one feature (e.g. `Overall_Risk_Score` if ever leaked in) | Fragile model, poor generalization if that one field is absent/changed | Leakage rules already exclude same-table risk fields (Section 5); recommend feature-importance review in Step 5.2 to check no single feature dominates |
| False positives (flagging genuine claims as high-risk) | Customer harm, erodes trust, contradicts the project's customer-centric principle | Human-in-the-loop by design (Step 4.5 UI already enforces no auto-decision); report precision alongside recall |
| False negatives (missing genuine fraud) | Financial loss, but the graver harm here is over-flagging genuine customers given the synthetic-label caveat | Track recall on the (small, noisy) positive class explicitly; do not optimize for accuracy alone |
| Explainability limitations of tree ensembles at scale | An officer may not trust or understand a SHAP plot | Pair every model explanation with a rule-based reason code (Section 10) in plain language |
| Adversarial/document manipulation, OCR errors | A manipulated or misread document could flip a decision | Out of scope for Step 5.1; flag as a requirement for the eventual OCR module (confidence thresholds, manual-review fallback) |
| Incomplete documents (avg 6.02 of 8 types per claim) | Missing-document patterns could be confused with fraud signal rather than benign process variation | Model `has_document_*` presence explicitly rather than assuming missing = suspicious; calibrate against real outcomes before treating incompleteness as a strong signal |
| Distribution shift / model drift | A model trained on this snapshot will not track real claim-pattern changes over time | Not addressed by this dataset; flag as a Step 5.2+/production concern requiring monitoring, out of scope here |
| Customer/vehicle repeated-claim bias | A customer with 3 prior claims might be flagged mainly for being a repeat claimant rather than for claim-specific evidence | `Previous_Claim_Count` is a legitimate feature but should be inspected for outsized influence in Step 5.2's feature-importance review |

---

## 15. Recommended Step 5.2

1. Add `ai_ml/requirements.txt` (scikit-learn, matplotlib/seaborn for EDA plots, shap) — nothing beyond what Section 9/10 actually needs.
2. Implement the Section 8 rule-based baseline as real, runnable code (`ai_ml/common/` or a new `ai_ml/rule_baseline/` module), with every threshold as a named, overridable constant flagged "requires calibration."
3. Train Logistic Regression + Random Forest/Gradient Boosting on `Fraud_Label` using `feature_builder.safe_feature_columns("frd_Fraud_Label", df)`, with a `Customer_ID`-grouped train/test split, reporting Precision/Recall/F1/PR-AUC/confusion matrix (never accuracy alone).
4. Repeat step 3 for `Risk_Category` and `Overall_Consistency_Status` as secondary sub-models, matching the architecture's four analysis boxes.
5. Run the rule-based baseline and the ML model on the *same* held-out test set and report the quantitative Rule-Based vs. ML comparison the project promises.
6. Add SHAP explanations for the tree-ensemble model and pair them with rule-based reason codes per Section 10, still without wiring anything into the production backend/frontend yet.
7. Explicitly label every result as synthetic-data validation, per Section 13.
8. Only after 1–7 are done and reviewed: revisit whether a small ACO surveyor-assignment demo (Section 12) is worth building, using the real workload/location data plus a clearly-labeled synthetic scaffold for the missing factors.

---

## Files created this step

**Reusable pipeline (`ai_ml/`):**
- `ai_ml/__init__.py`, `ai_ml/common/__init__.py` — make the pipeline importable as `ai_ml.common.*`
- `ai_ml/common/data_loader.py` — loads all 15 tables from the raw Excel files, with the same authoritative-file choice as the Step 2 database build
- `ai_ml/common/data_quality.py` — missing-value, duplicate, numeric-range, date-range, categorical-value, and referential-integrity checks, reused throughout this report
- `ai_ml/common/preprocessing.py` — aggregates `documents` and `evidence` to one row per claim (the only two tables that need it)
- `ai_ml/common/feature_builder.py` — assembles the verified 654-row claim-level dataset and implements the leakage rules from Section 5 as executable code (`safe_feature_columns`, `leaked_columns_for_target`)
- `ai_ml/run_audit.py` — runs the full audit end-to-end and asserts the row-count/uniqueness guarantees (this is what produced the verification numbers in Section 3)

**Documentation:**
- `docs/project_documentation/AI_ML_DATASET_AUDIT.md` — this report

## Files modified

None outside `ai_ml/` and `docs/project_documentation/`. No frontend, backend, database schema, model, migration, or raw dataset file was changed.
