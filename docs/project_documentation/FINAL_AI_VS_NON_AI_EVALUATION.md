# Final AI vs. Non-AI Evaluation (Step 5.7)

**This is a research-prototype evaluation on a synthetic/de-identified dataset. It is the consolidated comparison of results already measured in Steps 5.1-5.6 - no new experiments were run to produce this report, and no number below was invented.**

---

## 1. Research question

The panel asked: *"Make a comparison on what are the results when you use AI and when you don't."* This report answers: **"How does an AI-assisted CI-MICOP workflow compare with a conventional baseline workflow for motor insurance claim analysis and operational support?"**

## 2. Evaluation methodology

This report consolidates the ACTUAL results already produced by Steps 5.1-5.6 (`ai_ml/model_artifacts/evaluation_results.json`, `secondary_targets/secondary_targets_summary.json`, `risk_fusion/risk_fusion_summary.json`, `aco/aco_results.csv`). It is generated programmatically by `ai_ml/experiments/run_final_evaluation.py`, which reads those files directly and fails loudly if one is missing, rather than substituting a fabricated value. Every quantitative figure in this report is traceable to one of those four files; every row is included in the machine-readable `ai_ml/model_artifacts/final_evaluation/final_comparison.csv`.

## 3. Non-AI baseline ("research prototype baseline")

Represents a conventional, non-AI claims workflow: (1) manual/standard document review, (2) manual cross-document comparison, (3) rule-based/basic fraud screening (`ai_ml/baselines/rule_based_fraud.py` - transparent, threshold-based, no learned model), (4) manual repair-estimate review, (5) manual prioritization (e.g. FIFO), (6) greedy nearest-available surveyor assignment, (7) Claims Officer final decision. **This does not claim to represent every real insurance company's actual process** - it is a documented, implemented reference point for comparison.

## 4. CI-MICOP AI-assisted workflow

(1) OCR/information extraction fields already present in the dataset, (2) document consistency analysis, (3) evidence analysis, (4) repair-estimate anomaly analysis, (5) fraud screening (rule + ML), (6) claim-pattern analysis, (7) multi-signal risk fusion, (8) confidence/uncertainty estimation, (9) explainable reason codes, (10) review prioritization, (11) human Claims Officer investigation, (12) final human decision. **AI assists the Claims Officer. AI does not make the final claim decision** - enforced throughout Steps 5.4-5.6 (no automatic approval/rejection/settlement anywhere in this codebase).

## 5. Dataset

654 claims, 15 relational tables, synthetic/de-identified (Step 5.1 `AI_ML_DATASET_AUDIT.md`). 20 real surveyors appear in `surveyor_inspections`. All quantitative results below come from this single dataset export.

## 6. Experimental controls

Customer_ID-grouped train/test splitting and repeated grouped cross-validation (Step 5.2/5.3) to prevent customer-level leakage; a documented SAFE/POTENTIAL_LEAKAGE/DEFINITE_LEAKAGE feature classification (Step 5.1/5.3) to prevent target leakage; fixed, pre-registered model/cost-function/ACO hyperparameters not tuned against the reported results (Steps 5.2-5.6); identical scenarios given to baseline and ACO in Step 5.6 (`assert_scenarios_match`).

## 7. Fraud comparison

| Comparison | Baseline | AI method | Metric | Baseline | AI | Interpretation |
|---|---|---|---|---:|---:|---|
| Single split (Step 5.2) | Rule Baseline | Logistic Regression | PR-AUC | 0.167 | 0.222 | LR nominally higher |
| Single split (Step 5.2) | Rule Baseline | Random Forest | PR-AUC | 0.167 | 0.233 | RF nominally highest single-split result |
| Repeated grouped CV (Step 5.3) | Rule Baseline v1 | Logistic Regression | PR-AUC | 0.156 | 0.189 | LR nominally higher |
| Repeated grouped CV (Step 5.3) | Rule Baseline v1 | Random Forest | PR-AUC | 0.156 | 0.177 | RF nominally higher |
| Repeated grouped CV (Step 5.3) | Logistic Regression | Random Forest | PR-AUC | 0.189 | 0.177 | **RF's single-split lead over LR reversed and was not stable** (gap 0.012 < combined std 0.033) |

**Full source data:** `ai_ml/model_artifacts/final_evaluation/final_comparison.csv`, rows 1-7.

## 8. Risk fusion comparison

| Comparison | Baseline | AI method | Metric | Baseline | AI | Interpretation |
|---|---|---|---|---:|---:|---|
| Repeated grouped CV (Step 5.4) | Individual fraud signal | Equal-weight fusion | PR-AUC | 0.156 | 0.155 | Fusion did NOT outperform the individual signal |
| Repeated grouped CV (Step 5.4) | Individual fraud signal | Configurable weighted fusion | PR-AUC | 0.156 | 0.167 | Weighted fusion produced a nominally higher PR-AUC, but the difference (0.011) was smaller than its own cross-validation standard deviation (0.030) - **not statistically meaningful** |

## 9. Consistency comparison

| Comparison | Baseline | AI method | Metric | Baseline | AI | Interpretation |
|---|---|---|---|---:|---:|---|
| Repeated grouped CV (Step 5.3) | Majority-class baseline ("always predict Match", 60.2%) | Logistic Regression | Accuracy | 0.602 | 0.451 | **LR scored BELOW the trivial majority-class baseline** |
| Repeated grouped CV (Step 5.3) | Majority-class baseline | Random Forest | Accuracy | 0.602 | 0.499 | **RF also scored below the trivial majority-class baseline** |

No defensible rule-based (non-AI, non-trivial) baseline could be constructed for this target (Step 5.3, Section 7) - the individual field-level match columns showed no relationship to the overall status.

## 10. Repair-estimate (Excessive Claim Amount) comparison

| Comparison | Baseline | AI method | Metric | Baseline | AI | Interpretation |
|---|---|---|---|---:|---:|---|
| Repeated grouped CV (Step 5.3) | Rule baseline (repair-ratio threshold) | Logistic Regression | PR-AUC | 0.4725 | 0.4695 | Both at chance level (base rate ~46.9%); neither meaningfully beats the other |
| Repeated grouped CV (Step 5.3) | Rule baseline | Random Forest | PR-AUC | 0.4725 | 0.4576 | Both at chance level; RF nominally lower |

## 11. Surveyor assignment comparison

Mean across 5 evaluation scenarios (seeds 101/202/303/404/505), 50 claims / 20 surveyors:

| Metric | Greedy (baseline) | ACO | Interpretation |
|---|---:|---:|---|
| Total assignment cost | 13.299 | 13.307 | ACO higher (worse) |
| Total distance | 935.97 | 953.23 | ACO higher (worse) |
| Workload imbalance (std) | 0.2064 | 0.2010 | ACO lower (better) |
| Priority handling score | 0.1299 | 0.1296 | ACO lower (better) |
| Runtime (s) | 0.011 | 11.505 | ACO ~1000x slower |
| Unassigned claims | 0 | 0 | No difference |

**ACO did not consistently outperform greedy assignment** - it traded a small distance/cost regression for a small workload/priority-balance improvement, at far greater computational cost (Step 5.6, `ACO_SURVEYOR_ASSIGNMENT.md`).

## 12. Capability comparison

| Capability | Traditional/Non-AI | CI-MICOP AI-assisted | Evidence status |
|---|---|---|---|
| OCR/information extraction | Manual reading | Field-level data already structured; no OCR engine built | PARTIAL |
| Cross-document consistency | Manual comparison | Implemented, real signal | AVAILABLE |
| Repair-estimate anomaly analysis | Manual review | Implemented, real signal | AVAILABLE |
| Evidence duplication analysis | Manual review | Implemented, real signal | AVAILABLE |
| Fraud screening | Rule-of-thumb | Rule + ML, weak-to-chance predictive performance | EXPERIMENTAL |
| Risk fusion | Not applicable | Implemented; no significant improvement measured | EXPERIMENTAL |
| Uncertainty estimation | Implicit | Explicit, independent of risk score | EXPERIMENTAL |
| Explainability | Officer's own reasoning | Reason codes + plain-language explanation for every signal | AVAILABLE |
| Review prioritization | FIFO/manual | 4-band recommendation, rule-based on risk+confidence | EXPERIMENTAL |
| Surveyor optimization | Manual/ad hoc | Greedy + ACO compared; ACO not consistently better | EXPERIMENTAL |
| Auditability | Paper/manual trail | Every signal/score traceable to source columns | AVAILABLE |
| Customer-facing explanation | Officer explains verbally | Not built | NOT MEASURED |
| Human-in-the-loop | Officer decides everything | Enforced everywhere; no autonomous decision exists | AVAILABLE |

Full table with per-row justification: `ai_ml/model_artifacts/final_evaluation/final_comparison.csv` (rows labeled `qualitative`).

## 13. Explainability comparison

Non-AI baseline: an officer's reasoning is typically undocumented beyond free-text notes. CI-MICOP AI-assisted: every fraud/risk signal and fused score carries a machine-generated, plain-language reason code (`ai_ml/explainability/`, `ai_ml/risk_fusion/reason_codes.py`) with a fixed vocabulary that never claims "fraud confirmed." This is a **functional capability difference**, not a measured effectiveness claim - no study measured whether officers make better decisions with these explanations than without them.

## 14. Uncertainty comparison

The non-AI baseline has no formal uncertainty concept. CI-MICOP's risk-fusion layer (Step 5.4) computes an explicit `confidence_score`/`confidence_band`, deliberately kept independent of the risk score itself (a claim can be HIGH risk + LOW confidence). This is a genuine architectural capability; it was not benchmarked against any ground truth because no ground-truth "true confidence" exists to compare against.

## 15. Human-in-the-loop comparison

Identical principle in both workflows: the Claims Officer makes the final decision. The AI-assisted workflow adds intermediate automated analysis steps before that same human decision point - it does not remove, shortcut, or automate the decision itself (Step 5.5 `AI_OFFICER_INTEGRATION.md`; Step 5.6 explicitly avoided any automatic surveyor assignment).

## 16. What improved

Functional capabilities implemented that the non-AI baseline lacks in a comparably systematic form: automated multi-signal generation from existing data (Section 12), a consistent structured signal representation across claims (Step 5.4), explicit machine-generated explanations (Step 5.2-5.5), explicit uncertainty separate from risk (Step 5.4), a repeatable, code-defined analytical workflow (all of Steps 5.1-5.6), and a transparent, inspectable surveyor-assignment cost function (Step 5.6). **These are functional/architectural improvements, not measured performance improvements.**

## 17. What did not improve

- Fraud PR-AUC differences between rule baseline and ML models were within run-to-run cross-validation variability (Section 7).
- Risk_Category and Overall_Consistency_Status prediction were approximately chance level; both ML models scored below the trivial majority-class baseline on accuracy (Sections 7, 9).
- Excessive_Claim_Amount prediction was approximately chance level for both the rule baseline and ML models (Section 10).
- Multi-signal risk fusion did not produce a statistically meaningful PR-AUC improvement over the single strongest signal (Section 8).
- ACO did not consistently outperform greedy surveyor assignment, and was far slower (Section 11).

## 18. Negative findings ("What the experiments do NOT prove")

- AI does not currently demonstrate strong fraud prediction on this synthetic dataset.
- Risk_Category prediction was approximately chance level.
- Consistency prediction was approximately chance level.
- Excessive Claim Amount prediction was approximately chance level.
- Risk fusion did not produce a statistically meaningful improvement.
- ACO did not consistently outperform greedy assignment.
- Synthetic data limits real-world generalization.
- No production insurance workflow was benchmarked.
- No real financial savings were measured.
- No real claim-processing-time reduction was measured.

## 19. Dataset limitations

The dataset is synthetic/de-identified (Step 5.1). Several target labels (`Fraud_Label`, `Risk_Category`, `Overall_Consistency_Status`, `Excessive_Claim_Amount_Indicator`) behave as independently-generated values rather than deterministic functions of their own visible component signals (Step 5.1/5.3 `AI_ML_VALIDATION_FINDINGS.md`). Surveyor-assignment attributes (location, workload, availability) are entirely synthetic (Step 5.6). None of the measured numbers in this report should be read as real-world insurance performance.

## 20. Research contribution

**CI-MICOP proposes an integrated motor insurance claims decision-support architecture that combines leakage-aware AI analysis, multi-signal risk fusion, uncertainty estimation, explainable reasoning, and optimization-assisted surveyor assignment, while retaining human authority over final claim decisions.** This is not claimed to be first, unique, revolutionary, or state-of-the-art - it is a research prototype whose contribution is the integrated, transparent, human-in-the-loop architecture and the disciplined evaluation methodology (grouped repeated validation, leakage control, honest negative-result reporting) applied throughout Steps 5.1-5.6.

## 21. Future work

Real-world validation would require: real insurer claims, verified (not synthetic-proxy) fraud outcome labels, real document-processing benchmarks, human review time measurements, real repair-estimate outcomes, surveyor travel/time data, real workload data, model calibration, fairness evaluation, prospective (not retrospective) evaluation, and direct comparison against an existing insurer's actual workflow. **None of this has been completed; this is a description of what would be required, not a claim that it exists.**

## 22. Final conclusion

**Does CI-MICOP prove that AI is better than non-AI? Not universally, based on the current synthetic dataset.** The experiments did not establish statistically meaningful predictive superiority: fraud-screening PR-AUC differences between the rule baseline and ML models were within run-to-run variability under repeated grouped cross-validation; Risk_Category, Consistency, and Excessive-Claim-Amount prediction were approximately chance level; multi-signal risk fusion did not significantly beat the single strongest signal; and Ant Colony Optimization did not consistently outperform a simple greedy surveyor-assignment baseline. **However, CI-MICOP demonstrates a broader decision-support capability** through automated signal generation, multi-signal fusion, uncertainty estimation, explainability, and structured human-review prioritization - capabilities the non-AI baseline does not provide in a comparably systematic, auditable form, even though none of them was shown to improve predictive accuracy on this dataset.
