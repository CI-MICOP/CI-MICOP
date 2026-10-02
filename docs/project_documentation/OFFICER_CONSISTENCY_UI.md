# Claims Officer Document Consistency UI (Step 5.8.13-D)

## 1. Objective

Steps 5.8.12, 5.8.13-B and 5.8.13-C added three backend capabilities -
document OCR/completeness, deterministic registration/policy comparison,
and the FIR <-> Survey Report location prototype - but no officer screen
called any of them. The officer "Document Consistency" tab only displayed
the seeded `cross_document_consistency` row, which comes from the
synthetic research dataset and is not computed from the claim's uploaded
documents.

This step surfaces the existing live results to the Claims Officer. It is
**frontend-only**: no backend, schema, migration, risk-fusion or decision
change.

## 2. Files

| File | Change |
|---|---|
| `frontend/src/services/officerService.js` | Added `analyzeClaimDocuments(claimId)` and `checkClaimConsistency(claimId)` |
| `frontend/src/components/officer/ConsistencyFindingsPanel.jsx` | New panel |
| `frontend/src/pages/officer/DocumentConsistencyPage.jsx` | Panel added at top; stored row relabelled as "Recorded Dataset Values" |
| `frontend/src/components/officer/__tests__/ConsistencyFindingsPanel.test.jsx` | 13 tests |
| `frontend/src/pages/officer/__tests__/DocumentConsistencyPage.test.jsx` | 3 tests |
| `frontend/src/services/__tests__/officerService.test.js` | 2 tests |

## 3. Two Explicit Actions

| Button | Endpoint | Database effect |
|---|---|---|
| **Analyze Documents** | `POST /api/v1/officer/claims/{claim_id}/documents/analyze` | Writes only each document's own analysis fields (Step 5.8.12). Never `Final_Decision`, `Approved_Amount` or `claim_decision_audit`. |
| **Check Consistency** | `POST /api/v1/officer/claims/{claim_id}/documents/semantic-consistency` | None (read-only). |

They are deliberately separate so the officer can see which action writes
OCR output and which only reads it. Neither runs automatically on page
load. The consistency check only reads already-extracted text, so a claim
whose documents have not been analyzed yet will correctly return
UNAVAILABLE/INCONCLUSIVE. After a re-analysis, any previously displayed
findings are cleared, because the underlying text may have changed. Both
buttons are disabled while either request is in flight.

The Analyze summary shows the number of documents analyzed, the
completeness explanation, missing document types, and each document's
extraction status together with the backend's own reason when extraction
failed (e.g. Tesseract not installed) - OCR limitations are shown, not
hidden.

## 4. Two Separate Result Sections

The response's `deterministic` and `narrative` fields are rendered as two
independent sections and are never merged into a single verdict or score:

- **Identifier Checks** - registration and policy number: status, value on
  record, value found in the document, source document, and the backend's
  explanation.
- **Narrative Check (Research Prototype)** - FIR vs. Survey Report stated
  accident location: relationship, the two compared document IDs, the
  backend's explanation, and its limitations list.

A test asserts that a registration MATCH and a narrative CONTRADICTION are
displayed simultaneously, each in its own section.

## 5. Badge Tones

The generic `getStatusTone()` helper would render MATCH as neutral and
MISMATCH as red. The panel uses an explicit mapping instead:

| Status | Tone | Reason |
|---|---|---|
| MATCH, CONSISTENT | success (green) | Agreement found |
| MISMATCH, CONTRADICTION | warning (amber) | Needs officer review - red would read as an accusation |
| UNAVAILABLE, INCONCLUSIVE | neutral (grey) | Absence of evidence is never shown as negative evidence |

## 6. Wording and Human-in-the-Loop

Every render shows: *"Investigative findings for officer review only. A
mismatch or contradiction is not an accusation of wrongdoing. Final claim
decision remains with the Claims Officer."* The panel never displays the
word "fraud" and never shows a confidence value (the narrative prototype's
`confidence` is always `null`); both are asserted by a test. The panel
does not import or call `submitDecision`, also asserted by a test.

## 7. Validation

- Frontend: 124/124 tests passing (106 pre-existing + 18 new); `oxlint`
  reports no new warnings; `vite build` succeeds.
- Response field names were checked against the backend Pydantic schemas
  (`schemas/document_consistency.py`, `schemas/semantic_consistency.py`,
  `schemas/document_analysis.py`) and the extraction status strings in
  `services/document_analysis.py`.
- Manual end-to-end run (2026-10-02) against a live backend and
  PostgreSQL 18, on the seeded `DEV-CLM-001`, logged in as `dev_officer`:
  - Before either button: only the Recorded Dataset Values section shows
    (Partial, 0.9200); nothing runs on page load.
  - **Analyze Documents**: "1 document(s) analyzed. 0 of 5 required
    document type(s) are present for this 'Own Damage' claim", missing
    Accident Photos, Driving Licence, Insurance Policy, RC, Repair Estimate;
    the FIR (`DEV-DOC-001`) shows "Extraction unavailable" with the
    backend's reason (the seeded record has no stored file).
  - **Check Consistency**: registration (`TN01AB0001`) and policy
    (`DEV-POLICY-001`) both UNAVAILABLE (no RC / Insurance Policy
    document); narrative check INCONCLUSIVE (no Survey Report). All three
    badges render neutral grey, each section shows the backend's
    explanation, and the narrative limitations list is displayed.
  - MATCH / MISMATCH / CONTRADICTION states were not exercised live, as
    the seed claim has no RC, Insurance Policy or Survey Report document;
    they remain covered by the automated tests above.
- Backend suite on the same machine: 300/301 passing. The one failure
  (`test_valid_risk_fusion_result_returned_correctly`) is unrelated to this
  step: it needs the git-ignored Step 5.4 risk-fusion artifacts under
  `ai_ml/model_artifacts/`, which are not present on this machine.

## 8. Limitations

- Inherits every limitation of Steps 5.8.12/5.8.13-B/5.8.13-C: native PDF
  text only unless Tesseract is installed; registration/policy only;
  location-only narrative check with explicit phrasing.
- Results are not persisted; they disappear on navigation, matching the
  backend's read-time design.
- Consistency findings are not connected to risk fusion or the AI
  Insights tab.
