# Entity Extraction Foundation (Step 5.8.13-A)

## 1. Purpose

The Step 5.8.13 audit found that no entity extraction, temporal extraction,
or NLI/embedding infrastructure existed anywhere in this repository - live
or offline - and that the live database currently has essentially no
genuine multi-document text to compare across documents. Building
cross-document consistency or semantic contradiction detection directly on
top of that would mean inventing an unvalidated capability with nothing
real to validate it against.

Step 5.8.13-A builds only the narrow, honest first piece: a **deterministic
entity-extraction foundation** that reads `Document.Extracted_Text`
(genuinely produced by Step 5.8.12's OCR/native-PDF pipeline) and returns
best-effort candidate values for two identifiers. It answers exactly one
question - *"what entities can be found in this document's text?"* - and
explicitly does **not** answer *"does this entity match the claim?"* (that
is Step 5.8.13-B, a separate, not-yet-started task).

## 2. Supported Entities

1. **Vehicle registration number**
2. **Policy number**

No other entity type (dates, times, locations, amounts, vehicle models,
damage terms) is extracted at this stage - the Step 5.8.13 audit found no
tractable, format-based path for any of those without a much larger NLP
investment, and this step deliberately stays narrow.

## 3. Extraction Method

`backend/app/services/entity_extraction.py::extract_entities(text, ...)`
is **deterministic and regex/rule-based** - explicitly:

- **NOT** an NLP model.
- **NOT** a general information-extraction system.
- **NOT** a fraud detector.
- **NOT** a consistency detector.

Two independent detection strategies run per entity type:

- **Strict format match** - the value's own shape is recognized directly
  (e.g. the Indian vehicle-registration format, or this project's own
  `POL-XXXXXX` policy-number convention). Higher confidence, since the
  shape itself is distinctive.
- **Keyword-context match** - a value immediately following a relevant
  label ("Registration No", "Policy Number", etc.), regardless of its
  shape. Lower confidence, since no format is verified - this is what lets
  the extractor return a genuinely uncertain candidate instead of either
  inventing false certainty or reporting nothing at all.

If both strategies find the *same* normalized value, only one candidate is
returned (deduplicated) at whichever confidence its detecting method
assigned. If a document's text yields multiple genuinely different-looking
candidates, **all of them are returned** - the extractor never silently
picks one over another when the text is ambiguous.

### Why these specific formats

Before writing any regex, the actual project data was inspected (per the
Step 5.8.13-A brief's own instruction, not invented):

- **Registration number:** the live/dev-representative value
  (`seed_dev_data.py`: `Registration_Number="TN01AB0001"`) follows the
  standard Indian motor-vehicle plate format (2-letter state code, 1-2
  digit RTO code, 1-3 letter series, 4-digit number). **The bulk offline
  synthetic dataset (`ai_ml/datasets/.../03_vehicles.xlsx`) does NOT follow
  this format at all** - it contains unconstrained Faker-generated strings
  in many different shapes (`"CV-8035"`, `"MWP 189"`, `"0AG J82"`, etc.).
  That dataset was deliberately **not** used as the basis for this pattern
  - only the project's own real convention was targeted.
- **Policy number:** the one consistent convention actually present in the
  structured dataset is `POL-XXXXXX` (`policies.Policy_Number`). The dev
  seed data uses a different-looking value (`"DEV-POLICY-001"`), and the
  database schema itself enforces no format at all (`String(30)`, unique,
  no regex constraint) - so this is treated as **one observed convention,
  not a guaranteed universal format**, which is why the keyword-context
  fallback exists and why the strict match's confidence is moderate (0.70),
  not high.

## 4. Normalization Rules

- **Registration number:** uppercased; internal spaces and hyphens are
  removed (`"TN 01 AB 0001"` → `"TN01AB0001"`).
- **Policy number:** uppercased; internal whitespace is collapsed to a
  single space, but hyphens are preserved (they are part of this
  project's own convention).
- The **original matched text is always preserved** alongside the
  normalized value (`value` vs. `normalized_value`) - normalization never
  discards or aggressively mutates the source identifier.

## 5. Confidence Methodology

Every confidence value comes from a fixed, documented rule tied to *how*
the candidate was found - never a fabricated or learned probability:

| Method | Base confidence |
|---|---|
| Registration - strict format match | 0.90 |
| Registration - keyword-context match | 0.40 |
| Policy - strict format match | 0.70 |
| Policy - keyword-context match | 0.50 |

**Document-type context boost:** a fixed `+0.05` (capped at 0.99) is added
when the document's own type is the expected context for that entity -
`RC` for registration numbers, `Insurance Policy` for policy numbers (the
project's actual live document-type vocabulary - see Section 6). A
document of any *other* type is still fully scanned and its candidates are
still returned; the type only affects the boost, never whether extraction
runs at all.

**OCR-confidence rule:** if the document's own OCR confidence (from Step
5.8.12) is below `0.30`, every candidate's confidence is halved. This is
the one explicit, documented rule connecting OCR confidence to entity
confidence - low-confidence OCR text is likely to contain character-level
errors that would corrupt an identifier match, so trusting it at face
value would be dishonest. No other blending or formula is used.

## 6. Document-Type Context

The live upload vocabulary is unchanged from Step 5.8.12
(`services/document_upload.py::ALLOWED_DOCUMENT_TYPES`): FIR, Driving
Licence, RC, Insurance Policy, Repair Estimate, Accident Photos, Survey
Report. `RC` is the strong context for registration numbers and
`Insurance Policy` for policy numbers; every other type is still analyzed
without the confidence boost - a plausible candidate is never rejected
just because the document type isn't ideal.

## 7. API Integration

No new endpoint was created. Both existing Step 5.8.12 analyze endpoints
now include an additional `entities` field in their response:

- `POST /api/v1/documents/{document_id}/analyze`
- `POST /api/v1/officer/claims/{claim_id}/documents/analyze` (per document)

This was the lower-risk integration path: it reuses the exact same RBAC
(`get_claim_or_403` / `require_roles`), the exact same server-side document
lookup (never a client-supplied path), and adds a field that every
existing consumer (tests, frontend) simply ignores unless it looks for it
- confirmed by the full pre-existing test suite passing unchanged.

## 8. No-Persistence Design

Nothing here is written to PostgreSQL. `extract_entities` is a pure
function over a text string; its result is built into the HTTP response
and discarded afterward. No new column, no new table, and no Alembic
migration were created - confirmed via `alembic upgrade head` showing no
pending operations.

## 9. Security Behavior

- Entity extraction runs only on `Extracted_Text` already resolved via the
  existing, RBAC-checked document lookup - it never accepts a
  client-supplied path or arbitrary text.
- The API response never includes a filesystem path, the Tesseract command
  configuration, environment variables, or any other internal detail -
  confirmed by a dedicated test.
- Cross-customer access is blocked by the exact same `get_claim_or_403`
  check the underlying analyze endpoint already enforced - confirmed by a
  dedicated 403 test using a second customer's token.

## 10. Test Coverage

- `backend/tests/test_entity_extraction.py` - 28 unit tests: registration
  extraction (valid format, whitespace/hyphen/case variation, unrelated
  numeric text, malformed values with and without a label, multiple
  candidates, empty/None/whitespace-only text), policy extraction (same
  shape of cases, plus explicitly confirming a claim number is never
  mistaken for a policy number), document-type context boosting (RC/
  Insurance Policy boost applied, FIR/Survey Report/Accident Photos do not
  block a plausible candidate), the OCR-confidence halving rule, and an
  explicit check that no candidate's reason text ever claims a match/
  mismatch verdict against the claim.
- `backend/tests/test_document_analysis.py` - 7 new integration tests
  exercising the real API end-to-end with a genuine PyMuPDF-generated PDF
  containing controlled text (never the offline dataset's Faker-generated
  text): registration extraction with RC-context boost, policy extraction
  with Insurance-Policy-context boost, honest unavailable state when no
  text was extracted, no filesystem-path/secret leakage, cross-customer
  403, per-document entities in the claim-level endpoint, and confirmation
  that no new database field or table exists.
- Full backend regression: 257/257 passing. Full frontend regression:
  106/106 passing.

## 11. Why NLI Is Not Included

No NLI, sentence-embedding, or transformer-based infrastructure exists
anywhere in this repository (confirmed by an exhaustive Step 5.8.13 audit
search). Adding one now, with no real live document corpus to validate
against, would risk presenting an unvalidated capability as if it worked -
exactly what this project's own prior AI steps have consistently avoided.
NLI remains explicitly out of scope for this step.

## 12. Why Cross-Document Comparison Is Not Included

Comparing an extracted candidate against `vehicles.Registration_Number` or
`policies.Policy_Number` is Step 5.8.13-B's job, not this one. This step
only answers what can be found in a document's own text; it never reads
or compares against any other table, and no code path here does so
(confirmed by a dedicated test asserting no candidate's `reason` text ever
mentions a match/mismatch/consistency verdict).

## 13. Known Lack of Real Live Validation Data

**The extractor has not been validated for accuracy against a
representative corpus of real uploaded insurance documents.** The live
development database currently contains a single document with empty
`Extracted_Text` (its physical file was never genuinely uploaded through
the live endpoint). All test coverage in this step uses either the
project's own genuine structured-identifier formats (as controlled test
strings, built into real PyMuPDF-generated PDFs for the API-level tests)
or pure unit-level strings - never the offline dataset's Faker-generated
document text, and never a claim that real-document validation has
occurred. Real-world accuracy on scanned/photographed insurance documents
remains genuinely unknown until this extractor is run against real
uploaded documents at scale.

## 14. Limitations

- Deterministic regex matching cannot understand context the way an NLP
  model could - it will miss valid identifiers in unusual phrasings and
  may occasionally match a coincidental format in unrelated text.
- The registration-number pattern targets the standard Indian format only;
  other real-world formats (or noisy OCR output that corrupts the shape)
  will only be caught by the weaker keyword-context fallback, if at all.
- The policy-number pattern is based on one observed convention
  (`POL-XXXXXX`); this project's own schema enforces no format, so a real
  policy number in a different shape may only be caught via the
  keyword-context fallback, at lower confidence.
- No entity is extracted from any field beyond registration and policy
  numbers - dates, locations, amounts, and vehicle models are all
  explicitly out of scope for this step.
