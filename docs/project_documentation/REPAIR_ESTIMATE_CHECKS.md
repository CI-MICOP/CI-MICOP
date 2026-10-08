# Repair Estimate Checks (Steps 5.8.21 and 5.8.22)

## 1. Objective

Roadmap item 10: "Complete repair-estimate leakage pipeline."

- **Step 5.8.21 (first part):** a read-only check with six comparisons, three
  of them verdict-giving and three shown for information only, because the
  reference dataset was not on the machine.
- **Step 5.8.22 (second part):** the dataset is now available. Reference
  ranges were computed for the three information-only comparisons, and all
  six now give a verdict.

Before these steps a repair estimate was stored and shown, but nothing
compared it with anything. The officer's Estimate Analysis page showed
"Excessive Claim Amount: Not Flagged" and "Estimate Anomaly Score: 0.0000"
for every live estimate. Those are placeholder values
(`SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md`, Sections 11-13), not results.

The check answers: is there anything here worth a second look when the
estimate is set against the claim's own other records?

It is **not** fraud detection, not a risk score and not a decision. No AI
model, no new backend dependency, no schema or migration change, no decision
or risk-fusion change.

## 2. Files

| File | Change |
|---|---|
| `backend/app/services/repair_estimate_checks.py` | New in 5.8.21; reference ranges and three verdicts added in 5.8.22 |
| `backend/app/schemas/repair_estimate_checks.py` | New - response schema |
| `backend/app/api/v1/routers/officer.py` | New endpoint |
| `backend/tests/repair_estimate_corpus.py` | New - 16 hand-written cases; 16 more in 5.8.22 |
| `backend/tests/test_repair_estimate_checks.py` | New - 35 tests; 52 after 5.8.22 |
| `ai_ml/experiments/compute_repair_estimate_reference.py` | New in 5.8.22 - computes the reference ranges |
| `frontend/src/components/officer/RepairEstimateChecksPanel.jsx` | New - officer panel (unchanged in 5.8.22) |
| `frontend/src/components/officer/__tests__/RepairEstimateChecksPanel.test.jsx` | New - 8 tests |
| `frontend/src/pages/officer/EstimateAnalysisPage.jsx` | Shows the panel |
| `frontend/src/services/officerService.js` | `checkRepairEstimates()` |

## 3. Endpoint

`POST /api/v1/officer/claims/{claim_id}/repair-estimates/check`

Claims Officer or Admin only. Reads this claim's `repair_estimates`,
`vehicle_damage` and `accidents` rows and the claim amount. Writes nothing.

The response lists every estimate on the claim with six checks each, plus a
side-by-side comparison when the claim has two or more estimates. There is
deliberately no combined score. The response shape did not change in 5.8.22.

## 4. The Checks

Each check returns FLAGGED, NOT_FLAGGED, or UNAVAILABLE (nothing to compare,
for example no accident record, no damage recorded, or actual repair days
not recorded yet).

### 4.1 Checks based on the claim's own records

| Check | Raises a point when | Basis |
|---|---|---|
| Estimate date | The estimate is dated before the accident | A date order that cannot be right |
| Replaced parts vs damage recorded | The estimate lists replaced parts, but every damage record the surveyor made says "Repair" | The two records disagree in kind, not in amount |

### 4.2 Checks based on a reference range

Each raises a point when the value is above the 90th percentile of the
654-claim reference dataset.

| Check | Value compared | Median | 90th percentile (limit) | Added |
|---|---|---|---|---|
| Estimate vs claim amount | Estimate / claim amount | 0.84 | 2.97 | 5.8.21 (reference from `ai_pipeline.py`) |
| Repair cost vs estimate | Repair cost / estimate | 1.00 | 1.154 (15.4% above the estimate) | 5.8.22 |
| Estimate vs surveyor's damage cost | Estimate / total damage cost recorded | 1.42 | 5.34 | 5.8.22 |
| Repair days | Actual days minus estimated days | 3 | 12 | 5.8.22 |

Only "too high" raises a point. A repair cost below the estimate, or a
repair that finished early, is NOT_FLAGGED. Every FLAGGED explanation says
there can be valid reasons.

### 4.3 Estimates side by side

When a claim has two or more estimates, the response gives the lowest, the
highest and the gap between them. Information only, no verdict: every
reference claim has exactly one estimate, so there is no reference for a
normal gap.

### 4.4 Status of an estimate

- **POINTS_TO_REVIEW** - at least one check is FLAGGED.
- **NO_POINTS_FOUND** - no check is FLAGGED and at least one could run.
- **UNAVAILABLE** - no check could run.

## 5. Design Choices

- **Part counts are not compared number for number.** The reference dataset
  has exactly one damage record per claim (confirmed in 5.8.22: 654 rows,
  654 claims), so "more replaced parts than damage records" would point at
  most claims. One damage record can cover several parts.
- **The cost breakdown is not checked.** `SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md`
  (Section 8) found that Repair Cost never equals Parts + Labour + Painting
  in the reference dataset, so any tolerance would be an invented rule.
- **A zero estimate amount is UNAVAILABLE**, not a low ratio.
- **Actual repair days of 0 means "not recorded yet"**, following
  `repair_estimate_creation.py`.
- **Repair days are compared as days over, not as a ratio.** "13 days longer
  than estimated" is what the officer already sees on the row. The cost is
  that a short estimate that runs several times over is missed (case T06).
- **The same percentile is used for every reference check.** The 90th
  percentile is the one `ai_pipeline.py` and the rule baselines already use
  (`calibration_percentile = 0.90`). No limit was tuned by hand.
- **Nothing is written back.** `Excessive_Claim_Amount_Indicator` and
  `Estimate_Anomaly_Score` are left as they are. The checks are not wired
  into `ai_pipeline.py`; the live AI run's `repair_estimate_anomaly` signal
  is unchanged.

## 6. Reference Ranges (Step 5.8.22)

Computed once by `ai_ml/experiments/compute_repair_estimate_reference.py`
from `08_vehicle_damage.xlsx` and `09_repair_estimates.xlsx`, and copied as
constants into `repair_estimate_checks.py`. They are never recomputed from
live data. The existing estimate / claim amount reference was re-checked
against the dataset in this step and matches (0.836 and 2.975).

| Quantity | Rows | Min | Median | 90th percentile | Max | Correlation of the two sides |
|---|---|---|---|---|---|---|
| Repair cost / estimate | 654 | 0.80 | 1.004 | 1.154 | 1.20 | 0.971 |
| Estimate / damage cost | 654 | 0.06 | 1.415 | 5.343 | 26.05 | 0.045 |
| Actual minus estimated days | 654 | -12 | 3 | 12 | 18 | -0.022 |

What the data supports:

- **Repair cost vs estimate - supported.** The two amounts move together
  (0.97), and the ratio stays between 0.80 and 1.20. The limit of 15.4%
  above the estimate has a clear meaning.
- **Estimate vs damage cost - weak.** The two amounts are unrelated in the
  dataset (0.05), so the range is very wide. The limit of 5.34 shows what
  is common in this dataset; it is not evidence of what a normal ratio is.
  The same is true of the existing estimate / claim amount reference
  (correlation 0.05).
- **Repair days - weak.** Estimated and actual days are unrelated in the
  dataset (-0.02). The limit of 12 days over shows what is common here only.

The two weak checks were still turned into verdicts, with these caveats
shown to the officer in the limitations list, because the alternative is to
show a number with no context. Whether to keep them as verdicts is a
decision for review.

### 6.1 How often the checks raise a point on the reference dataset

All six rules applied to the 654 reference claims themselves:

| Check | Claims with a point | Share |
|---|---|---|
| Estimate date | 28 | 4.3% |
| Estimate vs claim amount | 66 | 10.1% |
| Replaced parts vs damage recorded | 271 | 41.4% |
| Repair cost vs estimate | 66 | 10.1% |
| Estimate vs surveyor's damage cost | 66 | 10.1% |
| Repair days | 59 | 9.0% |
| At least one of the six | 403 | 61.6% |

The four reference checks are near 10% by construction. Two results were
not expected:

- **Replaced parts vs damage recorded points at 41% of reference claims.**
  This check was designed in 5.8.21 without the data. In the dataset the
  estimate's replaced-part count and the surveyor's Repair/Replace value are
  unrelated, so the "disagreement" is very common. The check was left
  unchanged in 5.8.22; it needs a decision (keep, soften, or make
  information-only).
- **4.3% of reference estimates are dated before the accident.** This is a
  property of the synthetic data.

So on this dataset the six checks together are not selective: about 6 in 10
claims get at least one point. This says how the checks behave on synthetic
data whose fields were generated independently. It does not say how they
would behave on real claims.

## 7. Validation Corpus

32 hand-written cases (`backend/tests/repair_estimate_corpus.py`): 16 from
5.8.21 and 16 added in 5.8.22 for the three new verdicts. The ideal label is
what a careful Claims Officer would want.

| Case | Check | Situation | Ideal | Observed |
|---|---|---|---|---|
| D01 | Date | Estimate 2 days after accident | NOT_FLAGGED | NOT_FLAGGED |
| D02 | Date | Same day | NOT_FLAGGED | NOT_FLAGGED |
| D03 | Date | 1 day before accident | FLAGGED | FLAGGED |
| D04 | Date | No accident record | UNAVAILABLE | UNAVAILABLE |
| D05 | Date | 406 days after accident | FLAGGED | **NOT_FLAGGED** |
| R01 | Amount | Ratio 0.80 | NOT_FLAGGED | NOT_FLAGGED |
| R02 | Amount | Ratio 3.00 | FLAGGED | FLAGGED |
| R03 | Amount | Ratio 2.96 | NOT_FLAGGED | NOT_FLAGGED |
| R04 | Amount | Claim amount zero | UNAVAILABLE | UNAVAILABLE |
| R05 | Amount | Estimate zero | UNAVAILABLE | UNAVAILABLE |
| P01 | Parts | Both say replace | NOT_FLAGGED | NOT_FLAGGED |
| P02 | Parts | Estimate replaces, surveyor says repair only | FLAGGED | FLAGGED |
| P03 | Parts | Nothing replaced | NOT_FLAGGED | NOT_FLAGGED |
| P04 | Parts | No damage recorded | UNAVAILABLE | UNAVAILABLE |
| P05 | Parts | 6 replaced parts, 1 damage record | FLAGGED | **NOT_FLAGGED** |
| P06 | Parts | Surveyor says replace, estimate replaces nothing | NOT_FLAGGED | NOT_FLAGGED |
| C01 | Cost | Cost 4% above estimate | NOT_FLAGGED | NOT_FLAGGED |
| C02 | Cost | Cost 20% above estimate | FLAGGED | FLAGGED |
| C03 | Cost | Cost below estimate | NOT_FLAGGED | NOT_FLAGGED |
| C04 | Cost | Cost 15.0% above estimate | NOT_FLAGGED | NOT_FLAGGED |
| C05 | Cost | Estimate zero | UNAVAILABLE | UNAVAILABLE |
| M01 | Damage cost | Ratio 2.00, two damage records | NOT_FLAGGED | NOT_FLAGGED |
| M02 | Damage cost | Ratio 6.00 | FLAGGED | FLAGGED |
| M03 | Damage cost | Ratio 5.30 | NOT_FLAGGED | NOT_FLAGGED |
| M04 | Damage cost | No damage recorded | UNAVAILABLE | UNAVAILABLE |
| M05 | Damage cost | Ratio 3.00 | FLAGGED | **NOT_FLAGGED** |
| T01 | Days | 5 days over | NOT_FLAGGED | NOT_FLAGGED |
| T02 | Days | 13 days over | FLAGGED | FLAGGED |
| T03 | Days | 12 days over | NOT_FLAGGED | NOT_FLAGGED |
| T04 | Days | Finished early | NOT_FLAGGED | NOT_FLAGGED |
| T05 | Days | Actual days not recorded | UNAVAILABLE | UNAVAILABLE |
| T06 | Days | 2 days estimated, 12 actual | FLAGGED | **NOT_FLAGGED** |

**28 / 32 agree. 4 missed points (D05, P05, M05, T06), 0 false points.**

- D05: there is no upper limit on the delay between accident and estimate.
  A reference is now available (in the dataset the 90th percentile is 154
  days) but was not added in this step.
- P05: counts are deliberately not compared (Section 5).
- M05: the reference range for estimate / damage cost is wide (Section 6).
- T06: days over are compared, not how many times longer (Section 5).

In all four the check stays silent; it does not give a wrong verdict.

## 8. Tests

`backend/tests/test_repair_estimate_checks.py`:

- every corpus case, and the 28 / 32 summary above;
- each reference check: below the limit, above it, and its UNAVAILABLE
  cases;
- end to end through the real API and database: an estimate with no points,
  an estimate with all six points, a claim with no accident or damage
  records, two estimates side by side, a claim with no estimates;
- only the claim's own estimates are checked;
- Customer and Surveyor get 403, no token gets 401, an unknown claim 404;
- no explanation or limitation contains the word "fraud";
- the estimate's flag and score columns, the claim's decision and amount,
  and the audit log are unchanged after a run.

Results after Step 5.8.22:

- Backend: 520 tests collected, 520 passing (52 in this file, 17 of them
  new in 5.8.22). The one failure reported in 5.8.21
  (`test_valid_risk_fusion_result_returned_correctly`) now passes: the
  risk-fusion artifacts under `ai_ml/model_artifacts/` are present.
- Frontend: not re-run in 5.8.22, because no frontend file changed. The
  5.8.21 result was 160 / 160 passing, oxlint clean, `vite build` succeeds.

## 9. Limitations

- The corpus is small, hand-written, and was written together with the
  checks, not held out. It shows the checks do what they are designed to
  do; it is not an accuracy estimate.
- All four reference ranges come from the synthetic dataset, not from real
  insurer claims. Step 5.3 found that dataset's own "excessive amount" label
  could not be predicted better than chance, so the ranges describe what is
  common in that data, not what is wrong.
- Two of the three new ranges compare amounts that are unrelated in the
  dataset (Section 6).
- On the reference dataset the six checks point at 62% of claims, mostly
  because of the replaced-parts check (Section 6.1).
- The panel was verified by component tests and a successful build. It was
  not checked by hand in a browser in either step.
- The older "Excessive Claim Amount" and "Estimate Anomaly Score" cards on
  the Estimate Analysis page still show the stored placeholder values. They
  were left unchanged.
- No garage history is used: there is no Garage table, and the local
  database has too few estimates to compare garages.
- The reference script needs pandas and openpyxl
  (`ai_ml/requirements.txt`). They are not in `backend/venv` on the machine
  used for this step; the script was run from `ai_ml/venv`.

## 10. Open Points for Review

1. Keep, soften or demote the replaced-parts check, given that it points at
   41% of reference claims.
2. Keep the two weak reference checks (damage cost, repair days) as
   verdicts, or return them to information only.
3. Add an upper limit to the estimate-date check (case D05).
