# Narrative Location-Consistency Validation (Step 5.8.13-E)

> **Update (Step 5.8.17):** V12, V15 and V17 were fixed and held-out cases
> V19-V23 were added - the corpus now agrees on 15 / 23 cases with 2 false
> contradictions. The tables below record this step's original results. See
> `CONSISTENCY_IMPROVEMENTS.md` for the before/after comparison.

## 1. Objective

Step 5.8.13-C added a narrow research prototype
(`backend/app/services/semantic_consistency.py`) that compares the accident
location stated in a claim's FIR with the one stated in its Survey Report,
and returns CONSISTENT, CONTRADICTION or INCONCLUSIVE. Until now it had only
been exercised by a handful of unit tests written alongside it.

This step validates it against a controlled multi-document corpus (roadmap
item 2) and records, honestly, where it agrees with a careful human reader
and where it does not.

This step is **validation only**. The prototype itself was not changed, even
where errors were found. No dependency, schema, migration, risk-fusion or
decision change was made.

## 2. Files

| File | Purpose |
|---|---|
| `backend/tests/semantic_validation_corpus.py` | 18 hand-written FIR / Survey Report text pairs, each with an `ideal` and an `observed` label |
| `backend/tests/test_semantic_consistency_corpus.py` | 24 tests: corpus integrity, every case against the prototype, the agreement summary below, and 4 cases through the real upload -> PDF extraction -> endpoint pipeline |
| `docs/project_documentation/SEMANTIC_CONSISTENCY_VALIDATION.md` | This report |

## 3. Method

- **Corpus.** 18 FIR / Survey Report pairs written by hand for this step.
  None of the text is real accident data, and none comes from the synthetic
  research dataset (whose document text is unrelated filler).
- **Ideal label.** For each pair, what a careful human reader would conclude
  about whether the two documents state the same accident location. Written
  before running the prototype.
- **Observed label.** What the prototype actually returned, recorded from a
  real run on 2026-10-02 (not predicted). The extracted location candidates
  for each document were inspected at the same time to explain each result.
- **Regression guard.** `test_prototype_returns_recorded_result_for_corpus_case`
  asserts the prototype still returns the observed label for every case, and
  `test_agreement_summary_matches_validation_report` asserts the counts in
  Section 5. A future change to the prototype therefore fails these tests
  until the corpus and this report are updated together.
- **Pipeline check.** Cases V01, V04, V10 and V12 (one of each outcome type)
  are also uploaded as genuine PyMuPDF-built PDFs, analyzed, and compared
  through `POST /api/v1/officer/claims/{claim_id}/documents/semantic-consistency`.
  All four give the same result as the direct call, so native PDF text
  extraction does not change the outcome for these phrasings.

The corpus was deliberately weighted towards phrasings expected to be
difficult (10 of the 18 cases). The agreement count below therefore
describes this corpus only and is **not** an accuracy rate.

## 4. Results

How the prototype finds a location: it looks for `near`, `at`, `in` or
`close to` followed by one to three words that each start with a capital
letter, normalises case and punctuation, and requires exactly one distinct
location per document.

| Case | Situation | Ideal | Observed | Agrees | Why |
|---|---|---|---|---|---|
| V01 | Same place, same wording | CONSISTENT | CONSISTENT | Yes | Baseline |
| V02 | Same place, `at` vs `near` | CONSISTENT | CONSISTENT | Yes | Both keywords accepted |
| V03 | Same place, `ANNA SALAI` vs `Anna Salai` | CONSISTENT | CONSISTENT | Yes | Case normalised |
| V04 | Anna Salai vs Guindy | CONTRADICTION | CONTRADICTION | Yes | Baseline |
| V05 | Velachery vs Tambaram (`in`) | CONTRADICTION | CONTRADICTION | Yes | Baseline |
| V06 | `at 6 PM near Anna Salai` | CONSISTENT | CONSISTENT | Yes | `at 6` ignored (not capitalised) |
| V07 | No place in Survey Report | INCONCLUSIVE | INCONCLUSIVE | Yes | Nothing to compare |
| V08 | No place in either | INCONCLUSIVE | INCONCLUSIVE | Yes | Nothing to compare |
| V09 | `in Chennai near Anna Salai` | CONSISTENT | INCONCLUSIVE | No | Two mentions -> ambiguous |
| V10 | Anna Salai vs Anna Salai Junction | CONSISTENT | **CONTRADICTION** | No | Exact string comparison |
| V11 | Anna Salai vs Mount Road (same road) | CONSISTENT | **CONTRADICTION** | No | No alias knowledge |
| V12 | `At Anna Salai, ...` (sentence start) | CONSISTENT | INCONCLUSIVE | No | Keywords are case-sensitive |
| V13 | `near T. Nagar` in both | CONSISTENT | INCONCLUSIVE | No | Single letter + full stop not captured |
| V14 | `near anna salai` (lower case) | CONSISTENT | INCONCLUSIVE | No | Place must start with a capital |
| V15 | `in March near Anna Salai` | CONSISTENT | INCONCLUSIVE | No | `March` captured as a place |
| V16 | `... treated at Apollo Hospital` | CONSISTENT | INCONCLUSIVE | No | Hospital captured as a place |
| V17 | `near Anna Salai Monday morning` | CONSISTENT | **CONTRADICTION** | No | Capture runs into `Monday` |
| V18 | `in Chennai near Guindy` vs Anna Salai | CONTRADICTION | INCONCLUSIVE | No | Real disagreement hidden by ambiguity |

## 5. Summary

| Outcome | Count | Cases |
|---|---:|---|
| Agrees with ideal label | 8 / 18 | V01-V08 |
| **False contradiction** (same place reported as different) | 3 | V10, V11, V17 |
| Missed agreement (same place reported as INCONCLUSIVE) | 6 | V09, V12-V16 |
| Missed contradiction (different places reported as INCONCLUSIVE) | 1 | V18 |
| False agreement (different places reported as CONSISTENT) | 0 | - |

## 6. Findings

1. **The prototype is reliable only for clean, explicit phrasing.** Every
   case with one capitalised place name after a lower-case keyword, in both
   documents, was handled correctly (V01-V08).
2. **False contradictions are the most important weakness.** In V10, V11 and
   V17 the officer would see CONTRADICTION for two documents that describe
   the same place. The cause is exact string comparison: the prototype has
   no notion of a longer form of a name, of aliases, or of where a place name
   ends. The existing UI wording ("not an accusation of wrongdoing", amber
   rather than red, officer decides) limits the harm, but officers should
   be told this is the known failure mode.
3. **Most other failures fall back to INCONCLUSIVE**, the designed safe
   outcome (V09, V12-V16). These lose information but do not mislead.
   However, the same ambiguity rule can also hide a genuine disagreement
   (V18).
4. **No false agreement was observed.** The prototype never reported two
   different places as CONSISTENT on this corpus.
5. **PDF extraction is not a source of error** for these phrasings: the four
   end-to-end cases matched the direct results exactly.

## 7. Possible Improvements (not implemented)

Recorded for a future, separately agreed step. Each would need its own tests
and an update to this corpus and report.

- Case-insensitive keyword matching (`At`, `Near`) - addresses V12.
- Stop the capture at common non-place words (days, months, `Hospital`,
  `Police Station`) - addresses V15, V16, V17.
- Treat one location contained in the other (`Anna Salai` /
  `Anna Salai Junction`) as CONSISTENT, or as a separate weaker outcome -
  addresses V10.
- When a document mentions a city and a street, compare on the most
  specific mention instead of declaring ambiguity - addresses V09, V18.
- A small, documented alias list (e.g. Mount Road -> Anna Salai) - addresses
  V11, but only if its source and scope are justified.

None of these is a reason to add an NLI or embedding model. As Step
5.8.13-C already notes, similarity scores cannot tell agreement from
contradiction, and there is still no labelled real accident-narrative
corpus to validate one against.

## 8. Limitations

- The corpus is small (18 pairs), hand-written, and deliberately weighted
  towards difficult phrasings. It is not a sample of real reports.
- Only native-text PDFs were used. Tesseract is not installed in this
  environment, so scanned or photographed documents were not tested.
- Ideal labels were written by the project team, not by independent
  annotators or claims staff.
- No precision, recall, F1 or accuracy figure is claimed for real-world use.

## 9. Validation

- Backend: 325 tests collected, 324 passing. The 24 new tests all pass. The
  one failure (`test_valid_risk_fusion_result_returned_correctly`) is
  unrelated to this step: it needs the git-ignored Step 5.4 risk-fusion
  artifacts under `ai_ml/model_artifacts/`, which are not present on the
  machine used for this step.
- No production code was changed. The new tests only call the document
  upload, analyze and semantic-consistency endpoints; none of them calls the
  decision endpoint, and the existing
  `test_semantic_consistency_does_not_touch_final_decision_or_audit` still
  passes.
