# Decision: Live Fraud-Model Serving (Step 5.8.20)

## 1. Objective

Roadmap item 9: "Only integrate validated fraud-model serving if
preprocessing/model performance are defensible."

"Serving" means running the trained fraud model on a real, newly submitted
claim and showing its score to the Claims Officer. Today the fraud models
(rule baseline, Logistic Regression, Random Forest) exist only as offline
research in `ai_ml/`. In the live AI run, the `fraud_screening_rule_score`
signal is always reported as unavailable.

This step is a **decision only**. No code, dependency, schema, migration,
risk-fusion or decision-logic change was made.

## 2. Decision

**Deferred, not rejected. The fraud model is not served on live claims in
the current phase.**

Fraud-model serving stays in the project plan as future work, for the
"Model Development, Validation & Expanded Data Collection" phase (November
2026 - January 2027). Section 6 lists what has to be ready first.

Until then:

- `fraud_screening_rule_score` stays unavailable in the live AI run, with
  its existing explanation;
- the live run can use up to 6 of 7 signals and its status stays `"partial"`
  (`LIVE_SIGNAL_INTEGRATION.md`);
- the fraud models remain documented offline research.

## 3. What Was Measured

All figures are from Steps 5.2 and 5.3 on the synthetic 654-claim dataset
(`FINAL_AI_VS_NON_AI_EVALUATION.md`, `AI_ML_VALIDATION_FINDINGS.md`). No new
experiment was run for this step.

PR-AUC is a score for how well a model puts the fraud cases at the top of
its list. A model that guesses at random scores about the same as the share
of fraud cases in the data, which here is **0.151** (99 of 654 claims).

| Method | PR-AUC, single split | PR-AUC, repeated grouped CV |
|---|---:|---:|
| Random guessing (base rate) | 0.151 | 0.151 |
| Rule baseline | 0.167 | 0.156 |
| Logistic Regression | 0.222 | 0.189 |
| Random Forest | 0.233 | 0.177 |

The repeated grouped CV column is the more trustworthy one. It repeats the
test 15 times on different customer-grouped splits instead of once.

## 4. Reasons for Not Doing It Now

### 4.1 The model is only slightly better than guessing

Under repeated testing, the best model scores 0.189 against 0.151 for
random guessing. The models' scores also move by about 0.03 to 0.04 from one
run to the next, which is as large as the gap between the models
themselves. Which model is "best" changed between the single split and the
repeated test.

A score this weak, shown next to a real claim, would point officers at the
wrong claims about as often as the right ones.

### 4.2 The cause is the data, so more tuning will not fix it

Step 5.3 found that the dataset's `Fraud_Label` does not appear to be
derived from the claim's own recorded facts. It behaves like a value
generated separately. `AI_ML_VALIDATION_FINDINGS.md` (Question 8) concludes
that no further feature engineering or tuning on this dataset is likely to
help, because the pattern a model would need is not in the data.

### 4.3 Live claims do not have the inputs the model was trained on

The models and the full rule screener were trained on the synthetic
dataset's own indicator columns, such as `Duplicate_Evidence_Indicator` and
the cross-document mismatch flags. For a live claim, those database columns
still hold "not yet analyzed" placeholder values.

Running the model on placeholders would score every live claim as low risk.
That is worse than showing nothing, because it looks like a real result.

The live checks built in Steps 5.8.13 to 5.8.17 now produce real values for
document consistency, evidence duplication and photo quality. But they are
defined differently from the synthetic columns the model learned from, so
they cannot simply be swapped in. The model would have to be retrained on
inputs that match what a live claim actually provides.

### 4.4 A fraud score carries more risk than the other signals

The other live signals each state a checkable fact ("these two documents
give different dates"). A fraud score is a judgement about a person. The
project rules already say a document mismatch must never be called "fraud".
Showing a weak model's output under the word "fraud" would break the spirit
of that rule, even with a human making the final decision.

## 5. What Is Given Up

- The live AI run cannot reach `"completed"` status; it stays `"partial"`.
- The system must **not** be described as detecting fraud on live claims.
  In presentations, fraud scoring should be labelled as offline research
  with weak results, and live serving as planned.
- The SHAP explanations built for the fraud models also stay offline,
  because they explain a model that is not running live.

## 6. What Must Be Ready First

Start live fraud-model serving once all of these hold:

1. **Better data.** A dataset where the fraud label is actually derived from
   recorded claim facts: real insurer data, or a synthetic dataset rebuilt
   with documented label rules.
2. **A model that clearly beats the rule baseline.** The improvement under
   repeated customer-grouped cross-validation must be larger than the
   run-to-run variation, not just larger in one split.
3. **Matching inputs.** The model is trained on the same inputs a live claim
   produces (the live consistency, duplication and quality checks), not on
   the synthetic indicator columns.
4. **A score that means something.** The output is checked for calibration,
   or it is shown as a ranking band and not as a probability.
5. **Advisory only.** The score remains supporting information. It never
   writes `Final_Decision`, `Approved_Amount` or `claim_decision_audit`.

Until condition 1 is met, the others cannot be tested.

## 7. Limitations of This Decision

- It rests on one synthetic dataset. The weak results say the labels in
  this dataset are not learnable; they do not say fraud models cannot work
  on real insurance data.
- No new experiment was run. The figures are copied from the Step 5.2 and
  5.3 reports. The result files those reports were generated from are
  git-ignored and are not present on the machine used for this step, so the
  figures could not be re-checked against them here.

## 8. Validation

Documentation only. No code was changed and the test suites were not re-run
for this step.
