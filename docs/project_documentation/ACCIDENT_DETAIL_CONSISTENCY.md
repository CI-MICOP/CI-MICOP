# Accident-Detail Consistency (Step 5.8.16)

## 1. Objective

Roadmap item 6: strengthen document consistency where real extraction is
available. Step 5.8.13-B compares two identifiers (registration and policy
number) with the claim's records, and Step 5.8.13-C compares the accident
location between the FIR and the Survey Report. Two further facts are
stored in the `accidents` table but were never checked against the
documents:

- the **accident date** (`Accident.Accident_Date`), and
- the **FIR number** (`Accident.FIR_Number`).

This step adds both as deterministic MATCH / MISMATCH / UNAVAILABLE checks,
in the same style as Step 5.8.13-B. It is not fraud detection, not NLI and
not a confidence score. No dependency, schema, migration, risk-fusion or
decision change.

## 2. Files

| File | Change |
|---|---|
| `backend/app/services/accident_consistency.py` | New - extraction and comparison |
| `backend/app/schemas/semantic_consistency.py` | Added `AccidentDetailsConsistencyOut`; `accident_details` field on the response |
| `backend/app/api/v1/routers/officer.py` | Semantic-consistency endpoint also returns `accident_details` |
| `backend/tests/accident_consistency_corpus.py` | New - 20 hand-written cases |
| `backend/tests/test_accident_consistency.py` | New - 38 tests |
| `frontend/src/components/officer/ConsistencyFindingsPanel.jsx` | New "Accident Details" section |
| `frontend/src/components/officer/__tests__/ConsistencyFindingsPanel.test.jsx` | 3 new tests |

The Step 5.8.13-B module (`document_consistency.py`) and its registration/
policy results are unchanged; the new checks live in their own module and
their own response field, so neither can alter the other (asserted by a
backend and a frontend test).

## 3. Method

Both checks read only `Document.Extracted_Text` already persisted by Step
5.8.12's analyze endpoints. They never run OCR and never write to the
database.

**FIR number** - from **FIR** documents only:

- Recognised labels: `FIR No`, `FIR Number`, `F.I.R. No.`, `First Information
  Report No/Number` (any case). A number word is required, so the bare title
  "FIR" or a sentence such as "an FIR was lodged" is never read as a number.
- The value must contain a digit and may contain `/` and `-`
  (Indian FIR numbers are often written serial/year, e.g. `123/2026`).
- Compared after removing spaces and upper-casing.
- One distinct value: MATCH or MISMATCH. Several values: MATCH if one of them
  equals the record, otherwise UNAVAILABLE (too ambiguous to call a
  mismatch).

**Accident date** - from **FIR and Survey Report** documents:

- Only a date that is explicitly **labelled** as the accident date is used:
  `Date of accident / incident / occurrence / collision`,
  `Accident / Incident / Collision date`, and
  `The accident / incident / collision occurred / happened / took place on`.
  Unlabelled dates (report date, inspection date, policy dates) are ignored,
  so they can never be mistaken for the accident date.
- Supported shapes: `20/08/2026`, `20-08-2026`, `20.08.2026`, `2026-08-20`,
  `20 August 2026`, `20th Aug 2026`, `August 20, 2026`. Numeric day/month
  dates are read **day-first**, the Indian convention. An impossible date
  (e.g. 31/02/2026) is discarded, never guessed.
- MATCH when every labelled date in the FIR and Survey Report equals the
  record. MISMATCH when any of them differs; the explanation names every
  disagreeing document and the date it states.

**UNAVAILABLE**, never MISMATCH, when: there is no accident record, no
FIR/Survey Report document, no labelled value in the text, or no value on
record. As in every earlier step, UNAVAILABLE is not negative evidence.

## 4. Endpoint and UI

`POST /api/v1/officer/claims/{claim_id}/documents/semantic-consistency`
(unchanged access: Claims Officer or Admin) now also returns:

```json
"accident_details": {
  "accident_date": { "status": "...", "structured_value": "2026-08-20", "extracted_value": "...", ... },
  "fir_number":    { "status": "...", "structured_value": "123/2026",   "extracted_value": "...", ... }
}
```

Each entry has the same fields as the registration/policy results. On the
officer's Document Consistency tab, **Check Consistency** now also shows an
**Accident Details** section with the value on record, the value found, the
source document and the explanation, using the same badge tones (MISMATCH
amber, UNAVAILABLE grey).

## 5. Validation Corpus

`backend/tests/accident_consistency_corpus.py` holds 20 hand-written cases
(record: accident date 2026-08-20, FIR number 123/2026). `ideal` is what a
careful reader would conclude; `observed` is what the check returned on
2026-10-03, recorded from a real run.

| Case | Text | Ideal | Observed |
|---|---|---|---|
| A01 | `Date of accident: 20/08/2026.` | MATCH | MATCH |
| A02 | `Accident date: 2026-08-20` | MATCH | MATCH |
| A03 | `The accident occurred on 20 August 2026.` | MATCH | MATCH |
| A04 | `Date of incident: August 20, 2026` | MATCH | MATCH |
| A05 | `Date of accident: 20.08.2026` | MATCH | MATCH |
| A06 | `Date of accident: 21/08/2026` | MISMATCH | MISMATCH |
| A07 | FIR `20/08/2026`, Survey Report `22/08/2026` | MISMATCH | MISMATCH |
| A08 | `Report printed on 25/08/2026. ...` (unlabelled) | UNAVAILABLE | UNAVAILABLE |
| A09 | `The accident occurred near Anna Salai on 20/08/2026.` | MATCH | **UNAVAILABLE** |
| A10 | `Date of accident: 08/20/2026` (month-first) | MATCH | **UNAVAILABLE** |
| A11 | `Date of accident: 20/08/26` (two-digit year) | MATCH | **UNAVAILABLE** |
| A12 | `DATE OF ACCIDENT : 20-AUG-2026` | MATCH | **UNAVAILABLE** |
| F01 | `FIR No: 123/2026` | MATCH | MATCH |
| F02 | `F.I.R. No. 123/2026 registered at Guindy.` | MATCH | MATCH |
| F03 | `fir no: 123/2026` | MATCH | MATCH |
| F04 | `FIR No: 124/2026` | MISMATCH | MISMATCH |
| F05 | `An FIR was lodged at Guindy police station.` | UNAVAILABLE | UNAVAILABLE |
| F06 | `FIR No: 123/2026. Previous complaint ref FIR No: 77/2025.` | MATCH | MATCH |
| F07 | `First Information Report Number: 123 / 2026` | MATCH | **MISMATCH** |
| F08 | `Cr. No. 123/2026, Guindy Police Station` | MATCH | **UNAVAILABLE** |

Summary:

| Outcome | Count | Cases |
|---|---:|---|
| Agrees with ideal | 14 / 20 | A01-A08, F01-F06 |
| Missed, reported as UNAVAILABLE | 5 | A09-A12, F08 |
| **False mismatch** | 1 | F07 |
| False match | 0 | - |

The corpus deliberately includes difficult phrasings, so 14/20 describes
this corpus only and is not an accuracy rate.

## 6. Findings

1. **Clearly labelled dates and FIR numbers are handled reliably**,
   including mixed case, several date formats, an extra older FIR
   reference (F06), and a disagreement between FIR and Survey Report (A07).
2. **Unlabelled dates are ignored as designed** (A08), which avoids
   mistaking a report or inspection date for the accident date - at the
   cost of missing a date written inside a sentence (A09).
3. **Unsupported formats fall back to UNAVAILABLE**, never to a wrong
   verdict: month-first (A10), two-digit years (A11), `20-AUG-2026` (A12).
4. **One false mismatch (F07).** `123 / 2026` with spaces around the slash
   is read as `123`, so the officer would see MISMATCH for the right
   number. The "Found in Document" value (`123`) makes the cause visible,
   but this is the most important weakness to fix.
5. **"Cr. No." is not recognised (F08).** Indian police records often use
   "Crime No." for the registered case number; whether it can be treated as
   the FIR number should be confirmed before adding it.

## 7. Limitations

- Hand-written test text only; no real FIR or survey documents.
- Only native-text PDFs were used (Tesseract is not installed in this
  environment), so OCR errors in scanned documents were not tested.
- Claims filed before the follow-up change below have no FIR number on
  record, so their FIR check reports UNAVAILABLE. **Follow-up:** the
  customer New Claim form now has an optional **FIR Number** field (sent as
  `FIR_Number`, empty -> `null`; also sets `Police_Report_Available`), and
  the backend rejects values longer than the 30-character column with a 422
  instead of a database error.
- Only one accident record per claim is used (the first by Accident_ID).
- Not persisted and not connected to risk fusion.

## 8. Validation

- Backend: 423 tests collected, 422 passing. The 38 new tests and the
  existing Step 5.8.13-B/C consistency tests all pass. The one failure
  (`test_valid_risk_fusion_result_returned_correctly`) is unrelated: it
  needs the git-ignored Step 5.4 risk-fusion artifacts under
  `ai_ml/model_artifacts/`, which are not present on this machine.
- Frontend: 149/149 tests passing (3 new); oxlint reports no warnings on the
  changed files; `vite build` succeeds.

## 9. Possible Next Steps (not implemented)

- Allow spaces around `/` and `-` inside FIR numbers (fixes F07).
- Accept `dd-MON-yyyy` and a date later in the same "occurred ... on"
  sentence (A12, A09).
- Confirm with the team whether "Cr. No." should count as the FIR number.
- Accident time and city are also stored and could be checked the same way.
