# Document Completeness + OCR Pipeline (Step 5.8.12)

## 1. Purpose

Step 5.8.11 built a live AI analysis pipeline but left 5 of its 7 signal
families unavailable because nothing in the repository could genuinely
compute them from live claim data. Two of those five were `document_completeness`
and `information_quality`, both blocked on the same root cause: this
application had no OCR/text-extraction code at all, and the `documents`
table's OCR-related columns (`OCR_Confidence_Score`, `Extracted_Text`,
`Document_Completeness`) were only ever written as honest "not yet
analyzed" placeholders by the live upload endpoint.

Step 5.8.12 closes that specific gap for **document completeness**, by
implementing:

- **A genuine OCR/text-extraction utility** for the documents customers
  actually upload (PDF, JPG, JPEG, PNG).
- **A genuine, deterministic document-completeness calculation** - a
  static, rule-based required-vs-present comparison, not machine learning.

Neither of these makes, or feeds directly into, a claim decision. Both are
evidence-analysis utilities that a human (the claims officer) uses as
supporting information.

## 2. Scope

**In scope:** OCR/text extraction from uploaded documents; deterministic,
rule-based document completeness per claim type; exposing both as
on-demand API endpoints; feeding the completeness result into the Step
5.8.11 live AI pipeline as a third genuine signal.

**Explicitly out of scope** (left for future steps, and NOT implemented
here): fraud detection or fraud scoring, cross-document consistency
checking, evidence-duplication detection, the trained fraud model, full
information/entity extraction (vehicle numbers, policy numbers, accident
dates, etc.), document mismatch/fraud flagging, claim approval automation,
asynchronous job architecture (Celery/Redis/queues), or cloud storage
migration. `Document_Mismatch_Indicator` remains `False` for every
document - no comparison logic for it exists or was added.

## 3. Architecture

Two clearly separated responsibilities live in one new service module,
`backend/app/services/document_analysis.py`:

```
                 POST /documents/{id}/analyze
                              |
                              v
                 resolve_document_path()  <- reuses document_storage.py,
                              |               never a new path scheme
                              v
                 extract_document_text()  (A: OCR/extraction)
                    |                |
              PDF (.pdf)      image (.jpg/.jpeg/.png)
           PyMuPDF native text   Pillow + pytesseract
           text, else rasterize
           + pytesseract OCR
                              |
                              v
              crud_document.update_analysis_fields()
              (Extracted_Text, OCR_Confidence_Score)

                 POST /officer/claims/{id}/documents/analyze
                              |
                              v
              calculate_claim_document_completeness()  (B: completeness)
              required_document_types(claim.Claim_Type)
                     vs. present Document_Type values
                              |
                              v
              persisted onto every Document row of the claim
```

`ai_pipeline.py` (Step 5.8.11) calls `calculate_claim_document_completeness`
directly (not the persisted column) to build its `document_completeness`
signal - see Section 16.

## 4. Supported File Types

Unchanged from the existing upload endpoint: `.pdf`, `.jpg`, `.jpeg`,
`.png`. Any other extension is rejected by `extract_document_text` with an
honest "unsupported file type" result rather than a crash (defense in
depth - the upload endpoint already rejects these at upload time).

## 5. OCR Workflow (images)

1. Check whether the Tesseract executable is actually reachable
   (`pytesseract.get_tesseract_version()`). If not, return an honest
   `unavailable` result immediately - no attempt, no fabricated output.
2. Open the image with Pillow, convert to grayscale (the only
   preprocessing step - deliberately minimal and deterministic, not a
   computer-vision pipeline).
3. Run `pytesseract.image_to_string` for the text and
   `pytesseract.image_to_data` for per-word confidence values.
4. Compute a genuine mean confidence via `calculate_ocr_confidence`,
   ignoring Tesseract's `-1` sentinel (used for non-word boxes) - see
   Section 8.

## 6. PDF Workflow

1. Open the PDF with PyMuPDF. Encrypted or corrupted PDFs, and PDFs with
   zero pages, are all handled as honest `unavailable`/`empty` results,
   never a crash.
2. For each page, first try PyMuPDF's own native text extraction
   (`page.get_text()`). If it returns at least 10 characters, that text is
   used directly with confidence `1.0` - this is the exact source text
   embedded in the PDF, not a probabilistic OCR guess, so `1.0` states
   "not inferred," it is not a fabricated OCR score.
3. If a page's native text is too short (a scanned/image page, or a
   near-blank one), and Tesseract is available, the page is rasterized at
   200 DPI and OCR'd exactly like an image (Section 5).
4. Page texts are combined in page order. The document's overall OCR
   confidence is the mean of only the pages that produced a scoreable
   result (native text is always scoreable at 1.0; an OCR page with no
   valid Tesseract confidence contributes nothing to that mean, not a 0).
5. If some but not all pages were scoreable, the result is honestly
   labeled `partial`, with a limitation noting how many pages could not be
   analyzed.

## 7. Tesseract Requirement

**`pytesseract` is only a Python wrapper.** Installing it via `pip` (see
`backend/requirements.txt`) does **not** install the Tesseract OCR engine
itself - that is a separate system-level executable that must be
installed independently on every machine that needs to run OCR (a
development laptop, a CI runner, a production server).

At the time this step was implemented, **the Tesseract executable was not
installed in this development environment** (confirmed via
`pytesseract.get_tesseract_version()` raising `TesseractNotFoundError`).
Every OCR call in this codebase is guarded to fail into an honest
`unavailable` result rather than crashing when this is the case - this was
verified directly, not assumed (see Section 15 for exactly what was and
was not demonstrated).

Setup (not performed as part of this step):
- **Windows:** install the Tesseract-OCR distribution (e.g. from the
  UB-Mannheim builds) and either add its install directory to `PATH`, or
  set the `TESSERACT_CMD` environment variable to its full `.exe` path.
- **Linux:** `apt-get install tesseract-ocr` (or the equivalent for your
  distribution).
- **macOS:** `brew install tesseract`.

The application reads an optional `TESSERACT_CMD` setting
(`backend/app/core/config.py`, `backend/.env.example`) - if set, it is
passed to `pytesseract.pytesseract.tesseract_cmd`; if unset (the default),
pytesseract falls back to whatever `tesseract` resolves to on `PATH`. No
developer-specific path is hardcoded anywhere in the code.

## 8. OCR Confidence Methodology

`calculate_ocr_confidence(raw_confidences)`:

1. Tesseract's `image_to_data` reports a confidence value per detected
   box, but uses `-1` as a sentinel for boxes that are not actual
   recognized words (page/block/paragraph/line-level rows). Those `-1`
   values - and any other non-numeric value - are discarded, never
   averaged in as if they were real confidence scores.
2. If at least one valid (`>= 0`) confidence value remains, the result is
   their mean, divided by 100 to land in this project's expected 0-1
   range (Tesseract itself reports 0-100).
3. If nothing valid remains, the function returns `None` - the caller then
   sets `OCR_Confidence_Score = 0.0000` and marks the result
   `extracted_ocr_no_confidence` or `unavailable`, never a fabricated
   number just because some text happened to come back.

**A non-empty extracted text does NOT automatically mean high-confidence
OCR** - text and confidence are computed and reported independently.

## 9. Completeness Methodology

`calculate_claim_document_completeness(claim_type, documents)` is a
**deterministic, rule-based calculation - not machine learning**:

```
ratio = |required_document_types ∩ present_document_types|
        / |required_document_types|
```

- `present_document_types` is the **set** of `Document_Type` values
  actually present among the claim's uploaded documents - duplicate
  uploads of the same type do not change the ratio.
- **Zero documents is not the same as 0% complete.** A claim with no
  documents at all returns `available: false` (see Section 10 in the
  original audit) rather than a fabricated 0% score - there is no
  analyzable document set yet, which is a different fact from "we checked,
  and none of the required types are present."

**Schema note:** `Document_Completeness` exists on each `Document` row,
not on `Claim` (see Section 11) - there is no claim-level completeness
column, and this step does not add one. `POST
/officer/claims/{claim_id}/documents/analyze` computes ONE claim-level
ratio and writes that same value onto every one of that claim's `Document`
rows, since the schema has no other place to put a claim-level fact. The
single-document endpoint (`POST /documents/{document_id}/analyze`)
deliberately does **not** persist completeness - it only OCRs that one
document and *returns* the claim's current completeness (computed live,
not from the possibly-stale persisted column) so a customer viewing one
document isn't silently rewriting every other document row on their claim.

## 10. Claim-Type Document Rules

**No business rule for "required documents per claim type" existed
anywhere in this repository before this step** (confirmed by the Step
5.8.12 audit - `NewClaimPage.jsx`'s "Required documents vary by claim
type" text was cosmetic only). The mapping below is therefore a
**documented assumption, not a discovered fact**, built only from
`Document_Type` values the live upload endpoint actually accepts
(`ALLOWED_DOCUMENT_TYPES` in `services/document_upload.py`) and the exact
`Claim_Type` values the live app offers (`CLAIM_TYPES` in
`NewClaimPage.jsx`):

| Claim Type | Required Document Types |
|---|---|
| *(base set, every claim type)* | Driving Licence, RC, Insurance Policy |
| Own Damage | + Repair Estimate, Accident Photos |
| Third Party | + FIR, Accident Photos |
| Theft | + FIR |
| *(any other/future claim type)* | falls back to the base set only |

Rationale: every motor claim needs proof of driver/vehicle/policy
identity (the base set). Own Damage claims additionally need evidence of
the damage/repair cost. Third Party and Theft claims additionally need a
police FIR, since both involve an external party or a criminal act.
`Survey_Report` is intentionally never "required" here, since it is
typically produced by a surveyor after inspection, not something the
customer uploads at claim-filing time.

**This is a conservative, documented starting point, not a validated
insurance business rule** - it should be revisited with real domain input
before being treated as authoritative.

## 11. API Endpoints

### `POST /api/v1/documents/{document_id}/analyze`

- **Auth:** any authenticated user linked to the document's claim under
  the existing rules (`get_claim_or_403` - claim owner, assigned surveyor,
  Claims Officer, or Admin).
- OCRs/extracts text for this one document, persists `Extracted_Text` and
  `OCR_Confidence_Score`, and returns the claim's current document
  completeness (computed live, not persisted by this endpoint).
- 404 if the document does not exist; RBAC 403/401 exactly as the existing
  `GET`/`POST /documents` endpoints.

### `POST /api/v1/officer/claims/{claim_id}/documents/analyze`

- **Auth:** Claims Officer or Admin only (`require_roles`, matching every
  other officer-only AI endpoint).
- OCRs every document currently on the claim, computes ONE claim-level
  completeness ratio, and persists it onto every one of that claim's
  `Document` rows.
- 404 if the claim does not exist. A claim with zero documents returns
  `200` with `documents_analyzed: 0` and an honest unavailable
  completeness, not an error.

Both endpoints are **analysis-only**: neither can reach
`Claim.Final_Decision`, `Claim.Approved_Amount`, or
`claim_decision_audit` - there is no import of, or call path to, those
modules from `document_analysis.py`.

Response schemas (`backend/app/schemas/document_analysis.py`) never expose
the physical storage path, Tesseract command details, or any
environment/secret value - only metadata and genuinely derived values.

## 12. Storage Behavior

Unchanged. The existing `document_storage.py` abstraction
(`storage_path_for`, with its own root-escape check) is reused as-is to
re-derive a document's physical path for reading - this step never
constructs a storage path independently, and never introduces a second
storage mechanism.

## 13. Security

- **Path traversal:** unaffected - path resolution reuses
  `document_storage.storage_path_for`, including its existing
  root-escape assertion. No new path-construction code was added.
- **Authorization:** both new endpoints reuse the existing
  `get_claim_or_403`/`require_roles` dependencies; no new access-control
  logic was invented.
- **No client-supplied path:** the analyze endpoints take only a
  `document_id`/`claim_id` path parameter - never a filesystem path.
- **No raw file download added:** this step does not add any endpoint
  that returns raw file bytes; only metadata and extracted text (already
  gated by the same claim-access check as the file itself) are returned.
- **Existing upload security is untouched:** file-size limit (10 MB),
  magic-byte validation, extension allow-list, and filename sanitization
  in `document_upload.py`/`document_storage.py` were not modified - all 18
  pre-existing upload tests still pass unchanged.

## 14. Failure Handling

Every failure mode below returns an honest result - `unavailable`,
`empty`, or `partial`, each with a human-readable limitation - rather than
raising an unhandled exception:

Tesseract not installed; corrupted image; corrupted PDF;
password-protected PDF; empty (zero-page) PDF; blank image (no words
detected); OCR producing text but no valid confidence; a missing/deleted
physical file; an unsupported file extension; a claim with zero documents;
one unreadable page inside an otherwise-readable multi-page PDF.

"Unavailable is better than fabricated" is the governing principle
throughout - see `document_analysis.py`'s `ExtractionResult`/
`CompletenessResult` dataclasses, both of which have an explicit
`available`/status field rather than ever silently defaulting to a
plausible-looking number.

## 15. Test Coverage

- `backend/tests/test_document_analysis.py` - 34 tests covering: image OCR
  (honest unavailable-without-Tesseract, corrupted image, and two tests
  that simulate Tesseract's own output shape to unit-test the
  confidence-ignoring/aggregation logic - clearly labeled as simulated,
  not a claim of real OCR execution); `calculate_ocr_confidence` directly;
  native PDF extraction (real, unmocked, multi-page, order-preserving);
  scanned-PDF handling (real unavailable-without-Tesseract, plus one
  simulated-Tesseract test); encrypted/empty/corrupted PDFs; unsupported
  extensions; missing-file handling; all 6 completeness scenarios (all
  present, one missing, multiple missing, duplicate type, zero documents,
  unknown claim type); authorization (customer/owner, cross-customer 403,
  assigned surveyor, officer, admin, unauthenticated, 404); persistence
  (`Extracted_Text`/`OCR_Confidence_Score` persisted by the single-document
  endpoint, `Document_Completeness` persisted only by the claim-level
  endpoint, `Verification_Status`/`Document_Status` left untouched); and
  an explicit human-in-the-loop test confirming neither endpoint touches
  `Final_Decision`, `Approved_Amount`, or `claim_decision_audit`.
- `backend/tests/test_ai_pipeline.py` - 2 new tests confirming
  `document_completeness` becomes a genuine `available` signal once a
  claim has documents, that fusion/uncertainty correctly average 3 (not
  2) signals with no change to their own logic, and that it stays honestly
  `unavailable` for a zero-document claim.
- `backend/tests/test_document_upload.py` - all 18 pre-existing tests
  still pass unchanged.
- Frontend: `documentService.test.js` (+1 test for `analyzeDocument`),
  new `DocumentsPage.test.jsx` (7 tests: Analyze action renders, loading
  state, successful result including missing-document-types display,
  honest OCR-unavailable state, honest zero-document completeness state,
  API failure, and state reset between documents).
- **Genuine, unmocked end-to-end verification** was additionally performed
  by hand against the real PostgreSQL dev database via
  `fastapi.testclient.TestClient` (not a synthetic unit test) - see the
  Step 5.8.12 final implementation report for the exact request/response
  pairs.

## 16. AI Pipeline Integration

`backend/app/services/ai_pipeline.py` (Step 5.8.11) gained one new
function, `_document_completeness_signal(claim, documents)`:

- Calls `document_analysis.calculate_claim_document_completeness` directly
  on the claim's **live, current** documents - not the persisted
  `Document_Completeness` column. This is a deliberate choice: it keeps
  the signal correct and available regardless of whether/when a human
  happened to run `POST .../documents/analyze` first, and avoids any risk
  of the AI signal reading a stale persisted value that no longer matches
  the claim's actual current documents.
- If completeness is unavailable (zero documents), falls back to the same
  `_unavailable_signal("document_completeness")` used by every other
  unsupported signal.
- If available, `signal_value = 1 - completeness_ratio` (higher =
  more concerning), matching the direction convention of the other two
  live signals, with a plain-language explanation, e.g. *"4 of 5 required
  document type(s) are present for this 'Own Damage' claim. Missing:
  Accident Photos."* - never a bare "AI score = 0.75".

**Nothing else changed:** `_fuse` (ported `equal_weight_fusion`) and
`_compute_uncertainty` (ported `compute_uncertainty`) are byte-for-byte
unmodified - they already treated "available" vs. "unavailable" signals
generically, so a claim can now reach 3/7 available signals (previously
capped at 2/7) with zero changes to the fusion/confidence math itself.
`information_quality` remains unavailable - OCR text existing is not the
same as validated information quality, and no genuine methodology for the
latter exists yet (see Section 17).

## 17. Limitations

- This is a research-prototype pipeline, not production-grade OCR or
  fraud detection. No accuracy, precision, or recall figures are claimed
  anywhere in this codebase for OCR, because no such measurement has been
  performed against a labeled evaluation set.
- OCR quality depends entirely on document/scan/image quality, resolution,
  language (Tesseract's English-only default model is used; no other
  language pack is configured), layout complexity, and - fundamentally -
  on whether the Tesseract executable is installed on the machine running
  this code at all.
- The required-document-per-claim-type mapping (Section 10) is a
  documented assumption, not a validated business rule.
- `information_quality` remains unavailable: extracting text is not the
  same as validating its correctness, and this step does not claim
  otherwise.
- `Document_Mismatch_Indicator` remains `False` for every document - no
  cross-field or cross-document comparison exists or was added; treating a
  naive text match/mismatch as a fraud signal was explicitly out of scope.
- Analysis is synchronous and on-demand (an officer or customer must
  explicitly trigger it) - there is no automatic background job, queue, or
  worker, by design (see Phase 29 of this step's implementation brief:
  no Celery/Redis/Kafka in this step).

## 18. Future Work

- Genuine cross-document consistency checking (comparing OCR-extracted
  values across a claim's own documents) - blocked until real entity
  extraction exists.
- Genuine evidence-duplication detection (perceptual hashing or similar)
  for the surveyor evidence pipeline.
- A validated, evidence-based required-document-per-claim-type ruleset,
  ideally reviewed against real underwriting/claims-handling guidance
  rather than this step's conservative assumption.
- Measuring actual OCR accuracy against a labeled sample of real claim
  documents, so any future confidence/accuracy claim in this project's
  documentation would be backed by evidence rather than omitted.
- Only once the above exist would it become safe to reconsider integrating
  the trained fraud model or the full rule-based fraud screener, both of
  which the Step 5.8.11 audit found depend on exactly these missing
  inputs.
