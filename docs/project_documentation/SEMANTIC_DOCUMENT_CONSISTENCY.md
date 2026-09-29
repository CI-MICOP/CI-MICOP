# Semantic Cross-Document Consistency Prototype (Step 5.8.13-C)

## 1. Objective

Step 5.8.13-B answered "does an extracted *identifier* (registration
number, policy number) match the claim's structured record?" with a
deterministic, exact-value comparison. It explicitly left one gap open:
whether two documents' *narrative text* agree about the accident itself.

Step 5.8.13-C is a narrow **research prototype** that closes one specific
slice of that gap: whether a claim's FIR and Survey Report describe the
accident as happening at the **same stated location**, a **different**
one, or whether there isn't enough usable text to tell.

This is explicitly **not**: fraud detection, a fraud score, a risk score,
an automatic claim decision, an automatic rejection mechanism, or a
production-grade NLI system. Its result is presented purely as an
investigative signal for a Claims Officer to consider - never as an
automated outcome.

## 2. Supported Document Types

Exactly one pair, per the brief's "keep the scope small" instruction:

- **FIR** (`fir_copy` at upload; `Document_Type = "FIR"`)
- **Survey Report** (`survey_report` at upload; `Document_Type = "Survey Report"`)

Both are genuine entries in this project's own live upload vocabulary
(`services/document_upload.py::ALLOWED_DOCUMENT_TYPES`) - no other
document-type pair was assessed as more reliably populated during the
audit that preceded this step, and none was substituted.

## 3. Semantic Method

**No NLI model, sentence-embedding model, or transformer of any kind is
used.** A repository-wide search before writing this module (for `NLI`,
`entailment`, `contradiction`, `sentence-transformers`, `transformers`,
`embeddings`, `cosine similarity`, `semantic similarity`) found no such
infrastructure anywhere in this codebase, and `backend/requirements.txt`
carries no `torch`/`tensorflow`/`transformers`/`sentence-transformers`/
`spaCy` dependency. None was added in this step either.

Two reasons, not just dependency-avoidance:

1. **No real, labelled, multi-document corpus exists to validate a model
   against.** Introducing embeddings now would risk presenting an
   unvalidated capability as if it worked - exactly the risk Step
   5.8.13-B's own documentation flagged when it deferred NLI.
2. **Cosine similarity cannot detect this domain's actual failure mode.**
   "The accident happened in Gandhipuram." and "The accident happened in
   Peelamedu." are lexically and structurally near-identical sentences -
   an embedding model would likely score them as *highly similar* while
   they in fact disagree about the one fact that matters. Using
   similarity as a proxy for contradiction would have been actively
   misleading, and the brief explicitly forbids it.

Instead, this module reuses the same style of narrow, deterministic,
keyword-anchored extraction already established by Step 5.8.13-A/B
(`services/entity_extraction.py`, `services/document_consistency.py`): it
extracts an explicit location mention from each document's text using a
locative-preposition regex, then compares the two extracted values
directly. **This is a genuine contradiction-capable method** - an
explicit disagreement between two extracted values, not a similarity
score mislabelled as one - and it is honest about covering only one
narrow slice of "narrative consistency," not narrative consistency in
general.

### Dependencies added

None. `services/semantic_consistency.py` uses only the Python standard
library (`re`, `dataclasses`).

## 4. Preprocessing

Deliberately conservative, per the brief's Section 8:

- Only the first 5,000 characters of a document's `Extracted_Text` are
  scanned (`_MAX_COMPARISON_TEXT_CHARS`) - a safety bound against
  pathological OCR output making the regex scan unboundedly slow, not a
  business rule; well above any realistic single narrative section.
- No stopword removal, no stemming, no aggressive normalization. Place
  names, numbers, dates, and registration numbers are never stripped -
  they are exactly what this module needs to preserve.
- The only normalization applied is to the *extracted location value
  itself* (`normalize_location`): uppercase, strip punctuation, collapse
  whitespace - the same conservative style as
  `entity_extraction.normalize_registration`/`normalize_policy`.

## 5. Document Pairing

Only documents belonging to the **same claim** are ever compared (loaded
via `crud_document.list_by_claim(db, claim.Claim_ID)` - the same
claim-scoped query every other analysis service in this codebase uses).
Documents are never fetched or accepted from another claim.

If multiple FIRs or multiple Survey Reports exist on one claim, this
module does **not** compare every pair. It picks exactly one of each type
using a documented, deterministic rule: **the most recently submitted
document of that type** (`Document_Submitted_Date` descending, ties
broken by `Document_ID` descending).

**Why "most recent," not "first by ID"** - this rule was revised during
this step's own manual validation. An initial "ascending Document_ID"
version was implemented first and then rejected after testing against the
real development claim `DEV-CLM-001` concretely exposed why it fails:
that claim carries a hand-seeded placeholder FIR row
(`Document_ID = "DEV-DOC-001"`, generic filler text, no physical file
behind it) whose ID sorts alphabetically *before* every genuinely
uploaded document's generated ID (`"DEV-..."` < `"DOC-..."`). Under an
ascending rule, every real FIR uploaded afterward would be silently
ignored forever in favor of that stale placeholder - the comparison would
always run against the wrong document without any error or warning. See
`services/semantic_consistency.py::_select_document_pair`'s docstring and
`tests/test_semantic_consistency.py::test_document_pairing_ignores_stale_placeholder_with_earlier_id_but_later_submission`
for the regression test this finding produced. Preferring the newest
submission also matches how a Claims Officer would expect a
resubmitted/corrected document to take precedence over an older one.

Only documents with usable, non-empty `Extracted_Text` are compared. If
either selected document has no text yet (not analyzed, or OCR genuinely
found nothing), the result is `INCONCLUSIVE` - missing OCR is never
treated as a contradiction.

## 6. Result Semantics

Three states only, per the brief - never a forced binary:

- **CONSISTENT** - both documents yield exactly one, unambiguous location
  mention, and the two normalize to the same value.
- **CONTRADICTION** - both documents yield exactly one, unambiguous
  location mention, and the two normalize to *different* values.
- **INCONCLUSIVE** - anything else: a required document is missing, one or
  both have no usable text, or one or both mention zero or *more than
  one* distinct location (ambiguous - never guessed at).

`confidence` is **always `null`**. No calibrated or learned probability
exists anywhere in this prototype, and a raw similarity score is never
exposed labelled as a confidence value (there is no similarity score in
this design at all - see Section 3).

## 7. Location Handling

Location comparison is implemented as its own small, self-contained
function (`normalize_location` / `_extract_location_candidates` /
`_resolve_single_location`) inside `semantic_consistency.py`, and it is
also the sole signal that decides `relationship` in this prototype - see
Section 3 for why a general sentence-similarity approach was not used
instead. No geocoder, gazetteer, or fuzzy/near-match string comparison was
introduced; the comparison is an exact match on the normalized extracted
value only, distinguishing exact match, explicit disagreement, and
unavailable (ambiguous or absent), exactly as the brief's Section 12
requires.

The extraction pattern is keyword-anchored and requires the captured
phrase to look like a proper noun (starts with an uppercase letter):

```
\b(?:near|at|in|close to)\s+([A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,2})
```

This deliberately will not fire on ordinary lowercase prepositional
phrases such as "in an accident" or "at the scene" - only on an explicit,
capitalized place-like token following a locative preposition.

## 8. Deterministic vs. Semantic Layers - Kept Separate

Step 5.8.13-B's registration/policy `MATCH`/`MISMATCH`/`UNAVAILABLE`
result (`services/document_consistency.py`) is **returned completely
unmodified** alongside this step's narrative result, never merged or
overridden in either direction. The new endpoint
(`POST /officer/claims/{claim_id}/documents/semantic-consistency`)
returns both as two separate top-level fields, `narrative` and
`deterministic`:

```json
{
  "Claim_ID": "DEV-CLM-001",
  "narrative": {
    "document_a": {"document_id": "DOC-20260927-ABC123", "document_type": "FIR"},
    "document_b": {"document_id": "DOC-20260927-DEF456", "document_type": "Survey Report"},
    "relationship": "CONTRADICTION",
    "confidence": null,
    "explanation": "The FIR states Gandhipuram as the accident location, while the Survey Report states Peelamedu. Document inconsistency identified for officer review.",
    "limitations": ["..."]
  },
  "deterministic": {
    "registration": {"status": "MATCH", "...": "..."},
    "policy": {"status": "UNAVAILABLE", "...": "..."}
  }
}
```

A concrete test (`test_end_to_end_registration_match_and_location_contradiction_remain_separate`)
uploads an RC document whose registration number matches the insured
record, together with an FIR/Survey Report pair whose narrated locations
disagree, and asserts `deterministic.registration.status == "MATCH"` and
`narrative.relationship == "CONTRADICTION"` simultaneously - proving
neither dimension silently overrides the other.

## 9. Explanations

Explanations are generated only from what was actually extracted/compared
- never a template implying more certainty than the method provides:

- `CONSISTENT`: *"The FIR and Survey Report describe the accident as
  occurring at the same stated location (Gandhipuram)."*
- `CONTRADICTION`: *"The FIR states Gandhipuram as the accident location,
  while the Survey Report states Peelamedu. Document inconsistency
  identified for officer review."* - never "Fraud detected."
- `INCONCLUSIVE`: *"The available document text is insufficient for a
  reliable semantic comparison - no single, unambiguous accident-location
  mention could be found in one or both documents."* (or a document-
  missing/empty-text variant of the same message).

The word "fraud" never appears anywhere in this module's output - checked
by a dedicated test (`test_never_claims_fraud_or_uses_a_probability`).

## 10. API Integration

One new endpoint, exactly as suggested in the brief:

`POST /api/v1/officer/claims/{claim_id}/documents/semantic-consistency`

Officer/Admin only (`require_roles("Claims Officer", "Admin")`, the same
dependency every other officer-only endpoint in this router already
uses). It:

1. Resolves the claim server-side (`crud_claim.get`, 404 if missing) -
   never accepts a client-supplied document list.
2. Loads this claim's own documents only (`compare_claim_narrative`).
3. Selects the FIR/Survey Report pair per the deterministic rule above.
4. Ignores documents without usable text (returns `INCONCLUSIVE` instead).
5. Runs the location comparison.
6. Returns `narrative` and the unmodified `deterministic` result together.
7. Makes no database write of any kind.

Not exposed to Customer or Surveyor roles, and not added to any
customer-facing endpoint - this remains an internal, officer-side
investigative tool.

## 11. Confidence Limitations

`confidence` is always `null`. There is no learned or calibrated
probability anywhere in this design - see Section 3 for the full
reasoning on why a similarity score was not introduced as a stand-in.

## 12. Security / RBAC

- Officer/Admin-only access, confirmed by a dedicated test asserting 403
  for Customer and Surveyor tokens.
- Unknown `claim_id` returns 404, confirmed by a dedicated test.
- No filesystem path, storage location, Tesseract configuration, or
  credential ever appears in the response - only document IDs/types
  (already public within this claim to Officer/Admin), the relationship,
  and text explicitly derived from the compared documents' own narrative.
- No cross-claim comparison is possible by construction - documents are
  always loaded scoped to the one claim being analyzed.

## 13. Controlled Test Fixtures (Unit/Algorithm Level)

All six scenarios required by the brief are covered directly against
`services.semantic_consistency.compare_narrative`, with no database
dependency:

1. Same stated location -> `CONSISTENT`.
2. Different stated location -> `CONTRADICTION`.
3. No comparable location mention in either text -> `INCONCLUSIVE`.
4. One document with empty text -> `INCONCLUSIVE`.
5. Different claims -> structurally impossible (documents are always
   loaded scoped to one claim; a dedicated RBAC test also confirms
   non-officer roles cannot reach the endpoint at all).
6. Registration numbers agree, narrative locations disagree -> the
   deterministic and semantic results are asserted to remain separate and
   non-overriding (Section 8).

Plus: ambiguous multi-location text -> `INCONCLUSIVE` (not guessed at);
document-pairing tests (most-recent-wins, and the DEV-CLM-001 stale-
placeholder regression); a case-and-punctuation normalization test; and a
"never claims fraud or exposes a probability" test.

## 14. Validation Limitations - Read Carefully

This section exists specifically to avoid overstating what has been
validated, per the brief's explicit scientific-honesty requirement.

- **Unit-test validation**: thorough for the algorithm itself (Section
  13) - fast, deterministic, no database dependency.
- **Controlled synthetic validation**: the six required scenarios plus
  extras were also run end-to-end through the real API against the
  pytest fixture claim (`seed_data["claim1"]`), uploading genuine
  PyMuPDF-built PDFs with controlled narrative text through the real
  upload -> OCR -> analyze -> semantic-consistency pipeline.
- **Real development-document validation**: manually run against the real
  development claim `DEV-CLM-001` (see Section 15) - genuine PDFs,
  genuine OCR/text-extraction path, genuine API calls, cleaned up after
  each case so the claim was left exactly as found.
- **Real-world validation**: **does not exist.** There is no labelled
  corpus of real, independently-verified FIR/Survey Report narrative
  pairs anywhere in this project - the offline synthetic dataset's
  document text is Faker-generated filler unrelated to any real claim
  fact (per the Step 5.8.13 audit) and was not used here for the same
  reason it was excluded from Steps 5.8.12/5.8.13-A/B.
- **No accuracy/precision/recall/F1 is reported anywhere in this
  document**, because no genuine labelled evaluation dataset exists to
  compute one honestly. Any such number would be fabricated.
- The location-extraction regex is narrow by design (Section 7) and will
  legitimately return `INCONCLUSIVE` for any narrative that does not use
  an explicit `near`/`at`/`in`/`close to` + capitalized-place-name
  phrasing - it does not attempt to recover location information stated
  in other forms.

## 15. Performance

Measured during the real, end-to-end DEV-CLM-001 manual validation (see
Section 14) - no heavyweight model, so no model-initialization cost
exists at all:

| Case | Comparison-only latency (the `POST .../semantic-consistency` call) | Full case time (2x upload + 2x OCR/analyze + comparison + cleanup) |
|---|---|---|
| Same location (`CONSISTENT`) | ~34.6 ms | ~189.5 ms |
| Different location (`CONTRADICTION`) | ~23.9 ms | ~180.5 ms |
| No comparable location (`INCONCLUSIVE`) | ~29.4 ms | ~171.9 ms |

No background workers, queues, or async processing were introduced - the
comparison runs synchronously, in-request, exactly like Step 5.8.13-B.
Memory/dependency footprint: zero new third-party dependencies (Section
3) - the entire module is standard-library `re` and `dataclasses`.

## 16. Why This Is Not a Fraud Detector

A `CONTRADICTION` here is reported only as a fact about two pieces of
text disagreeing on one specific, narrow point (stated accident
location) - never as an accusation, a probability of wrongdoing, or a
claim outcome. The word "fraud" is never produced by this module (Section
9), and no fraud-adjacent label, score, or category is computed, stored,
or returned anywhere in this step.

## 17. Why This Is Not Connected to Risk Fusion Yet

`services/ai_pipeline.py` already documents, in its own signal-
unavailability messages, that no cross-document consistency pipeline is
wired into live claims yet
(`document_consistency_mismatch` is one of the four signals it lists as
always explicitly unavailable rather than fabricated). This step does
**not** change that. `ai_pipeline.py`, its fusion weights, its
uncertainty formula, signal count, and confidence aggregation are all
untouched - confirmed by `git diff` only ever touching
`officer.py`/the two new `semantic_consistency` files/this document/its
test file. A future step may consider consuming
`compare_claim_narrative()`'s result as a new signal family only after
this prototype has been reviewed and, ideally, validated against a real,
labelled corpus - mirroring exactly how Step 5.8.12's document
completeness was integrated only after review, and how Step 5.8.13-B
itself remains unintegrated today.

## 18. No Database Migration

`cross_document_consistency` was not modified. It still lacks
provenance/explanation fields (per the Step 5.8.13 audit), and this
step's result needs exactly that provenance
(`document_a`/`document_b`/`explanation`) to be honest and explainable.
The result is computed at read time and never persisted - the same
"read-time result when persistence isn't cleanly supported" pattern
established across every AI-adjacent step in this project so far.

## 19. Future Integration Possibilities

- Extending the location extractor to recognize additional phrasing
  patterns, once real narrative text is available to validate against.
- Extending the same narrow, extraction-based approach to other narrow,
  well-defined narrative facts (e.g. an explicitly stated accident date)
  - each would need its own dedicated, documented extraction and
  comparison rule, not a generic NLI upgrade.
- Introducing an actual NLI/entailment model only once: (a) a real,
  labelled corpus of accident narratives exists to validate it against,
  and (b) the project's dependency footprint is deliberately expanded to
  support it - a decision explicitly deferred, not made in this step.
- Consuming this result as a new `ai_pipeline.py` signal family (Section
  17) only after independent review.
