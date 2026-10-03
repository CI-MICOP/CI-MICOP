# Live Signal Integration into Risk Fusion (Step 5.8.18)

## 1. Objective

Roadmap item 8: "Only integrate validated signals into risk fusion."

The live AI run (`POST /api/v1/officer/claims/{claim_id}/ai-analysis/run`,
`backend/app/services/ai_pipeline.py`, Step 5.8.11) combines the 7 signal
families defined by the Step 5.4 research. Until now only 3 could be
computed for a live claim (claim timing, repair-estimate ratio, document
completeness); the other 4 were always reported unavailable because no live
check produced their inputs.

Steps 5.8.13-B to 5.8.17 built and validated those checks. This step feeds
three of them into the existing signals. The fusion and uncertainty formulas
are **unchanged**.

| Signal | Before | After | Fed by |
|---|---|---|---|
| `claim_pattern_anomaly` | live | live | unchanged |
| `repair_estimate_anomaly` | live | live | unchanged |
| `document_completeness` | live | live | unchanged |
| `document_consistency_mismatch` | always unavailable | **live** | Steps 5.8.13-B/C, 5.8.16, 5.8.17 |
| `evidence_duplication` | always unavailable | **live** | Step 5.8.14 |
| `information_quality` | always unavailable | **live (photo part)** | Step 5.8.15 |
| `fraud_screening_rule_score` | always unavailable | always unavailable | roadmap item 9 |

## 2. Files

| File | Change |
|---|---|
| `backend/app/services/ai_pipeline.py` | Three new signal functions; updated reasons and limitations |
| `backend/tests/test_live_signal_integration.py` | New - 9 end-to-end tests |
| `docs/project_documentation/LIVE_SIGNAL_INTEGRATION.md` | This document |

No schema, migration, dependency, frontend or decision change. The officer's
AI Insights live-run panel already lists all 7 signals generically, so the
new values appear there without UI changes.

## 3. How Each Signal Is Computed

All three reuse the existing check's result unchanged and follow the
research convention: a value from 0 to 1, **higher = more concerning**. A
check that could not run never contributes a number - the signal is
reported unavailable with a specific reason instead.

**`document_consistency_mismatch`** - share of the claim's document
consistency checks that found a disagreement, out of those that could
actually compare something:

- checks: registration number, policy number, accident date, accident time,
  FIR number (MATCH / MISMATCH) and FIR vs Survey Report location
  (CONSISTENT / CONTRADICTION);
- UNAVAILABLE and INCONCLUSIVE results are left out of both counts;
- example: location CONTRADICTION, date MATCH, the rest unavailable -> 1/2 =
  0.5;
- unavailable when nothing could be compared, with a reminder to upload the
  documents and run "Analyze Documents" (the checks read the text that
  analysis extracts).

This is the live counterpart of the research signal, which averaged three
mismatch flags from the synthetic `cross_document_consistency` table.

**`evidence_duplication`** - `1.0` if any readable photo on the claim is an
exact or near copy of another stored photo, otherwise `0.0`. Binary, like the
research `evidence_any_duplicate_flag`. Unavailable when the claim has no
photos or none can be read.

**`information_quality`** (photo part) - share of the claim's readable
evidence photos with at least one quality flag (low resolution, too
dark/bright, low contrast, blurry). The research signal also averaged
document OCR confidence; that part is left out because native PDF text has
no OCR confidence and Tesseract is not installed in this environment.
Signal confidence is 1.0 when a surveyor inspection is on record and 0.85
otherwise - ported unchanged from the research `signal_builder`.

All three use signal confidence as the research did; the remaining
uncertainty is visible through the existing coverage and agreement terms.

## 4. What This Changes for an Officer

- A claim with analyzed documents and photos can now be scored on up to
  **6 of 7** signals instead of 3, which raises the coverage term of the
  confidence estimate.
- Status is still `"partial"`: `"completed"` needs all 7 and fraud screening
  stays off.
- Every new signal's explanation states which checks ran, what they found,
  and that these are rule/fingerprint checks validated only on controlled
  test data. No explanation uses the word "fraud" (asserted by tests).
- The AI result remains advisory. The live run never writes the claim,
  `Final_Decision`, `Approved_Amount` or `claim_decision_audit` (asserted by
  a test), and is not persisted.

## 5. Validation Basis ("only validated signals")

Each fed check was validated before this step, on controlled data:

| Signal | Check | Validation |
|---|---|---|
| Document consistency | Registration/policy | Step 5.8.13-B tests and manual run on DEV-CLM-001 |
| | Location | 15/23 corpus cases agree, 2 false contradictions (`CONSISTENCY_IMPROVEMENTS.md`) |
| | Date + FIR | 22/25 agree, 0 false mismatches |
| | Time | 10/11 agree, 0 false mismatches |
| Evidence duplication | Fingerprints | 7/13 copies caught, 0 false matches (`EVIDENCE_DUPLICATION.md`) |
| Information quality | Photo measures | 12/15 exact, 1 false "blurry" flag (`EVIDENCE_PHOTO_QUALITY.md`) |

These are controlled, hand-written or generated corpora, not real claims.
"Validated" here means the behaviour is measured and documented, not that
real-world accuracy is known. That limitation is carried into every signal
explanation and the run's limitations list.

## 6. Tests

`backend/tests/test_live_signal_integration.py` (real API, database and file
storage):

- location contradiction -> document consistency `1.0`, "1/1";
- agreeing documents -> `0.0`;
- no comparable text -> unavailable, mentioning "Analyze Documents";
- the same photo twice -> evidence duplication `1.0`; an original photo ->
  `0.0`;
- no photos -> evidence duplication and information quality unavailable;
- one clear and one dark photo -> information quality `0.5`, confidence 1.0
  (inspection on record);
- fraud screening still unavailable, status `"partial"`, and the overall
  score equals the mean of the available signals (unchanged fusion);
- claim, decision and audit log unchanged after a run.

The existing Step 5.8.11 pipeline tests pass unchanged: a claim with no
documents or photos still reports these signals unavailable and gets no
score.

- Backend: 468 tests collected, 467 passing. The one failure
  (`test_valid_risk_fusion_result_returned_correctly`) is unrelated: it
  needs the git-ignored Step 5.4 risk-fusion artifacts under
  `ai_ml/model_artifacts/`, which are not present on this machine.
- Frontend: 152/152 passing (no frontend change).

## 7. Limitations

- Validation is on controlled data only (Section 5); the fused score is a
  research prototype, not a calibrated probability.
- The checks run on every live AI run (including fingerprinting every
  stored evidence photo for the duplication signal) - fine for this
  prototype's volume, not for production scale.
- Document consistency depends on "Analyze Documents" having been run.
- Fraud screening remains unavailable until roadmap item 9 decides whether
  the fraud model can be served on live inputs.
