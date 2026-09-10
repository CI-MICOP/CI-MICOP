# Risk Fusion, Uncertainty, and Explainability (Step 5.4)

**Validation-study disclaimer:** This experiment is a validation study using the currently available CI-MICOP dataset. The dataset is synthetic/de-identified and therefore the measured performance must not be interpreted as production fraud-detection, risk-scoring, or consistency-checking accuracy. Real-world validation requires appropriately governed insurer claims data.

---

## 1. Motivation

CI-MICOP is a software platform that assists existing motor insurance companies with claims operations - it does not replace the insurer's own decision-making. Steps 5.1-5.3 built and rigorously validated single-model approaches (a rule baseline, Logistic Regression, Random Forest) against several candidate targets, using leakage-safe features and Customer_ID-grouped validation. Step 5.4 asks a different question: rather than continuing to search for a single model that predicts one target well - which Step 5.3 showed is not supported by this dataset - can a **transparent combination of several independent, pre-decision signals**, paired with an **explicit uncertainty estimate**, give a Claims Officer more useful decision support than any one signal alone?

## 2. The problem with single-model decision making

A single model (or single rule) collapses many different kinds of claim evidence into one number, and typically reports that number with unwarranted confidence - even when the underlying signal is weak, even when critical evidence is missing, and even when the model disagrees with other equally-valid indicators. Three concrete problems motivate the fusion+uncertainty design:

1. **One weak signal looks the same as one strong signal.** A 0.9 fraud-screening score computed from a model that performs near chance (Step 5.2/5.3) is presented identically to a 0.9 score from a hypothetical highly-validated model - the officer has no way to tell the difference.
2. **Missing evidence is invisible.** A model trained on complete features silently imputes or drops missing values; it never tells the officer "this part of the assessment could not be evaluated."
3. **Risk and confidence get conflated.** A high score is read as "high risk," full stop - there is no way to express "the evidence suggests risk, but we aren't sure" versus "the evidence clearly and consistently suggests risk."

## 3. Existing Step 5.2 findings (recap)

Single train/test split, `frd_Fraud_Label`: Rule Baseline PR-AUC 0.167 (Precision 0.146, Recall 0.905 - over-triggers), Logistic Regression PR-AUC 0.222, Random Forest PR-AUC 0.233 (best single-split PR-AUC, Precision 0.333/Recall 0.048 at threshold 0.5).

## 4. Existing Step 5.3 findings (recap)

Under 5-fold x 3-seed `StratifiedGroupKFold` repeated grouped CV: Logistic Regression PR-AUC 0.189, Random Forest PR-AUC 0.177, Rule Baseline v1/v2 PR-AUC 0.156 (identical - only the decision threshold differs, not the ranking). **The Step 5.2 "Random Forest wins" ordering reverses and is not statistically stable** (gap 0.012, combined std 0.033). `Risk_Category`, `Overall_Consistency_Status`, and `Excessive_Claim_Amount_Indicator` all showed near-chance predictive performance. Conclusion: further hyperparameter tuning on this exact synthetic dataset is not justified - see `AI_ML_VALIDATION_FINDINGS.md`.

## 5. Proposed multi-signal architecture

```
ai_ml/risk_fusion/
├── signal_schema.py    - common Signal representation (Part A)
├── signal_builder.py   - builds 7 signals per claim from EXISTING leakage-safe columns
├── fusion_engine.py     - equal-weight + configurable-weighted fusion, risk bands (Part B/C)
├── uncertainty.py       - confidence/uncertainty scoring, independent of risk (Part D)
├── reason_codes.py      - officer-facing reason codes (Part E)
├── review_priority.py   - prototype review-priority recommendation (Part F)
└── validation.py         - no-NaN / no-claim-loss / renormalization integrity checks
```

No new database tables, no new raw data, no modification to `ai_ml.common.feature_builder`'s leakage-control rules. Every signal is built from a column already verified SAFE for `frd_Fraud_Label` in Step 5.1/5.2 (`safe_feature_columns`), or from the existing `RuleBasedFraudScreener`.

## 6. Signal representation

Every `Signal` carries: `claim_id`, `signal_name`, `category`, `signal_value` (risk contribution in [0,1], direction-adjusted, `None` if unavailable), `raw_value` (original measurement, for traceability), `signal_direction`, `confidence`, `availability` (`AVAILABLE` / `UNAVAILABLE` / `NOT_EVALUATED` / `INSUFFICIENT_EVIDENCE`), `evidence_available`, `explanation`, `source_module`. Seven signals are defined:

| Category | Signal name | Source (existing, leakage-safe) |
|---|---|---|
| DOCUMENT_CONSISTENCY | `document_consistency_mismatch` | `cross_document_consistency` mismatch flags |
| REPAIR_ESTIMATE_ANOMALY | `repair_estimate_anomaly` | `est_Excessive_Claim_Amount_Indicator` + repair/claim-amount ratio |
| EVIDENCE_DUPLICATION | `evidence_duplication` | `evidence_any_duplicate_flag` |
| FRAUD_SCREENING | `fraud_screening_rule_score` | `ai_ml.baselines.rule_based_fraud.RuleBasedFraudScreener` (Step 5.2, reused as-is) |
| CLAIM_PATTERN_ANOMALY | `claim_pattern_anomaly` | days between policy start and claim date |
| DOCUMENT_COMPLETENESS | `document_completeness` | mean document completeness |
| INFORMATION_QUALITY | `information_quality` | mean OCR/image/evidence confidence, surveyor-inspection presence |

On CI-MICOP's current 654-claim dataset, **all 7 signals are AVAILABLE for 100% of claims** - every claim in this export has at least one document and one evidence item recorded. This is itself a finding, not an assumption: the `UNAVAILABLE`/`INSUFFICIENT_EVIDENCE` code paths exist and are tested (`ai_ml/tests/test_risk_fusion.py`), but this particular dataset never exercises them structurally. A real-world deployment, where evidence is genuinely incomplete for some claims, would be expected to exercise them.

## 7. Equal-weight fusion

Every available signal contributes equally: `overall_risk_score = mean(available signal_values)`. Serves as the "no domain assumptions" baseline fusion strategy.

## 8. Configurable weighted fusion

Fixed, documented, **NOT learned or statistically optimized** weights, chosen by reasoning about which signal families are most directly tied to claim-handling risk (document consistency and fraud screening weighted highest; information quality weighted lowest, since it primarily informs *confidence*, not risk):

```
document_consistency_mismatch: 0.20   repair_estimate_anomaly: 0.20
evidence_duplication:          0.15   fraud_screening_rule_score: 0.20
claim_pattern_anomaly:         0.10   document_completeness: 0.10
information_quality:           0.05
```

These are explicitly labeled **"research prototype weights" / "configurable fusion weights"** throughout the code and outputs - never presented as learned or validated.

## 9. Missing-signal handling

`fusion_engine._fuse` filters to only `AVAILABLE` signals, then renormalizes their configured weights to sum to 1 before computing the weighted average - a missing signal is excluded, never treated as 0 (no risk). If every signal is unavailable, the result is `overall_risk_score=None`, `risk_band="UNSCORED"` - never a fabricated score. Verified by `ai_ml/risk_fusion/validation.py` and covered by dedicated tests.

## 10. Uncertainty estimation

`confidence_score = coverage x agreement x signal_trust x reliability_multiplier`:
- **coverage** = fraction of the 7 defined signals that were available.
- **agreement** = 1 - population std-dev of the available signal values (signals that disagree with each other lower confidence).
- **signal_trust** = mean of each contributing signal's own `confidence` (the fraud-screening signal is fixed at 0.40, reflecting Step 5.2/5.3's near-chance finding).
- **reliability_multiplier** = a fixed 0.85 discount applied whenever a model/rule-derived signal contributes, independent of that signal's own confidence - a structural reminder that the underlying predictive approach is not highly reliable.

`confidence_band` thresholds are **calibrated as percentiles of this dataset's own confidence-score distribution** (85th/50th/15th percentile), not fixed generic numbers - because every claim in this dataset has full signal coverage, a fixed threshold scheme compressed nearly all 654 claims into one band (empirically confirmed during development: 652/654 fell into a single band under the generic thresholds). This calibration reads no label - `confidence_score` has no ground truth to tune against - so it is unsupervised normalization, the same category of operation as `RuleBasedFraudScreener`'s own training-data-quantile calibration in Step 5.2. `INSUFFICIENT_EVIDENCE` is reserved strictly for claims where fewer than 2 signals are genuinely available; a fully-evidenced claim whose signals merely disagree is `LOW_CONFIDENCE`, never mislabeled as "insufficient evidence."

**Risk and confidence are independent axes.** A claim can be `CRITICAL` risk with `HIGH_CONFIDENCE`, or `CRITICAL` risk with `LOW_CONFIDENCE` (evidence points toward risk but the pointer itself is shaky), or `LOW` risk with `LOW_CONFIDENCE` (too little/contradictory evidence to say anything). This distinction - not collapsing "the model said X" into "X is true" - is the central research contribution of this step; see the representative examples in Section 16.

## 11. Explainability

Every claim-level output can be traced back to its 7 underlying `Signal` objects, each with a plain-language `explanation` naming the concrete data that produced it (e.g. "Repair-estimate/claim-amount ratio 2.93 (reference median 0.84, 90th percentile 2.97)"). Nothing is a black box: no neural network, no opaque embedding - every number in the chain from raw column to final risk band is inspectable.

## 12. Reason codes

Four Step 5.2 codes are reused unchanged (`DOCUMENT_INCONSISTENCY`, `REPAIR_ESTIMATE_ANOMALY`, `DUPLICATE_EVIDENCE`, `UNUSUAL_CLAIM_PATTERN`); four new codes are added, each wired to a real, reachable code path (`ai_ml/risk_fusion/reason_codes.py::reason_codes_for_claim`):

| Code | Fires when | Severity |
|---|---|---|
| `MISSING_EVIDENCE` | Any signal is unavailable for the claim | MEDIUM |
| `MULTI_SIGNAL_DISAGREEMENT` | Available signals disagree (agreement < 0.6) | MEDIUM |
| `LOW_MODEL_CONFIDENCE` | A model-derived signal contributes AND confidence is LOW/INSUFFICIENT | MEDIUM |
| `INSUFFICIENT_DATA` | Genuinely too few signals available to assess the claim | HIGH |

Officer-facing wording is always decision-support phrasing - **"AI risk signal: repair estimate anomaly detected"** - never a verdict such as "AI detected fraud" or "fraud confirmed" (enforced by `test_reason_codes_never_claim_confirmed_fraud`).

## 13. Human-in-the-loop workflow

```
Data --> Signal Building --> Multi-Signal Fusion --> Uncertainty Estimation
      --> Explainability / Reason Codes --> Review Prioritization
      --> HUMAN REVIEW (Claims Officer) --> Claims Officer Decision
```

The system never approves or rejects a claim. `review_priority.recommend_review_priority` only orders claims for human attention; a `CRITICAL`-risk-but-unreliable-confidence claim is routed to `HIGH_REVIEW` (not auto-rejected, not silently deprioritized) precisely because low confidence means a human judgment call is needed, not less scrutiny.

## 14. Review prioritization

Four prototype bands - `URGENT_REVIEW` / `HIGH_REVIEW` / `STANDARD_REVIEW` / `LOW_REVIEW` - derived from risk band, confidence band, evidence count, and signal disagreement (see `ai_ml/risk_fusion/review_priority.py` for the exact decision table). Explicitly labeled a **prototype research prioritization mechanism**, not a validated triage protocol.

## 15. Ablation methodology

Configurable-weighted fusion was re-evaluated under the same repeated grouped CV with one signal family removed (or isolated) at a time, using only signal families that actually exist in the current implementation (document consistency, repair estimate, evidence, fraud screening) - no fabricated ablation arms.

## 16. Experimental results

**Part G - strategy comparison** (5-fold x 3-seed grouped CV against `frd_Fraud_Label`, mean PR-AUC):

| Strategy | PR-AUC | F1 | Recall | Coverage |
|---|---:|---:|---:|---:|
| Individual fraud-screening signal alone | 0.156 (std 0.023) | 0.227 | 0.441 | 1.000 |
| Equal-weight fusion | 0.155 (std 0.022) | 0.184 | 0.223 | 1.000 |
| Configurable weighted fusion | **0.167** (std 0.030) | 0.171 | 0.273 | 1.000 |

Configurable weighted fusion has the highest mean PR-AUC of the three, but the improvement (0.167 vs 0.156, gap 0.011) is well within one standard deviation (0.030) - **not a statistically meaningful improvement**, consistent with Step 5.3's finding that this dataset does not support fine model comparisons. Fusion also does not beat the individual signal on F1/Recall - it trades recall for a marginal PR-AUC gain by incorporating additional weak signals.

**Part H - ablation** (mean PR-AUC, delta vs. all 7 signals):

| Configuration | PR-AUC | Delta |
|---|---:|---:|
| All signals | 0.167 | - |
| Without document consistency | 0.167 | +0.001 |
| Without fraud screening | 0.166 | -0.000 |
| Without repair estimate | 0.160 | -0.007 |
| Without evidence | 0.156 | -0.011 |
| Only repair estimate | 0.165 | -0.002 |
| Only fraud screening | 0.156 | -0.011 |
| Only document consistency | 0.147 | -0.020 |

No single signal family drives the fusion score, and removing any one family changes PR-AUC by at most 0.011-0.020 - **combining signals does not meaningfully outperform the best individual signal on this dataset**, and no family is indispensable. This directly answers Part H's research question honestly: on this synthetic dataset, multi-signal combination provides *architectural* value (transparency, coverage tracking, uncertainty) but not a demonstrated *predictive* advantage over the strongest single signal.

**Full-dataset scoring (654 claims, reference = full dataset):**

| Risk band | Count | | Confidence band | Count | | Review priority | Count |
|---|---:|---|---|---:|---|---|---:|
| MEDIUM | 368 | | LOW_CONFIDENCE | 327 | | HIGH_REVIEW | 412 |
| HIGH | 213 | | MEDIUM_CONFIDENCE | 229 | | STANDARD_REVIEW | 183 |
| LOW | 70 | | HIGH_CONFIDENCE | 98 | | LOW_REVIEW | 59 |
| CRITICAL | 3 | | | | | |

Mean signal coverage: 100.0% (7/7 signals available for every claim in this export).

## 17. Limitations

- Fusion weights are hand-chosen, not learned - they should not be read as reflecting the "true" relative importance of any signal family.
- Because every claim in this dataset has complete evidence, the `UNAVAILABLE`/coverage-driven part of the uncertainty mechanism is never exercised here - only the agreement/reliability-discount components produce variation. A dataset with genuinely incomplete evidence would likely show a wider, more informative confidence spread.
- The fusion layer inherits every limitation already documented for `Fraud_Label` (Steps 5.1-5.3): the target behaves as a weakly/independently generated synthetic label, so no combination of pre-decision signals should be expected to predict it strongly.
- No claim in the current dataset genuinely qualifies for the `INSUFFICIENT_EVIDENCE` confidence band (reported honestly in Part I rather than manufacturing an example).

## 18. Synthetic dataset limitations

Current experiments use synthetic/de-identified data. Synthetic labels may not reproduce real-world fraud mechanisms, and Step 5.1-5.3 already established that several target relationships in this dataset are weak or appear independently generated rather than derived from recorded claim facts. Predictive performance measured here - for the individual signal, both fusion strategies, and every ablation configuration - must not be interpreted as real insurance performance.

## 19. Future validation with insurer/de-identified real claims

A realistic future research pathway:
1. Collaborate with insurers.
2. Obtain properly governed historical claims data.
3. De-identify customer information.
4. Obtain ethics/legal/data-sharing approval where required.
5. Define ground-truth fraud outcomes (e.g. confirmed investigation results, not a synthetic proxy label).
6. Maintain strict train/validation/test separation throughout.
7. Re-run the same Customer_ID-grouped repeated-validation protocol already built in Step 5.3.
8. Compare fusion-based review prioritization against existing insurer triage workflows.
9. Evaluate fairness, calibration, and explainability on the real data before any deployment discussion.
10. Seek institutional/research funding where needed for secure data access and infrastructure - no such funding currently exists; this is a described pathway, not a commitment already in place.

## 20. Research contribution

The research contribution of Step 5.4 is **not** a claim that multi-signal fusion beats single-signal screening on this dataset - Section 16 shows it does not, meaningfully. The contribution is the **architecture and methodology**: a signal representation that never fabricates a missing value; a fusion mechanism that renormalizes rather than silently zeroing out missing evidence; an uncertainty layer that keeps risk and confidence as genuinely independent axes and is calibrated honestly against the dataset it runs on; a reason-code and review-priority system that is explicit, at every step, that AI output here is a screening signal for human review - never a verdict, and never an autonomous decision. This is offered as a research-prototype methodology for insurer claims triage, not a production system, not a fraud-detection guarantee, and not validated on real-world data.
