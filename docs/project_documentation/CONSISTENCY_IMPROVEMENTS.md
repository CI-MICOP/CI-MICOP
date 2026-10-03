# Consistency Check Improvements and Accident Time (Step 5.8.17)

## 1. Objective

Roadmap item 6 (continued): strengthen date/time/location/entity
consistency. Steps 5.8.13-E and 5.8.16 recorded specific weaknesses in the
location, accident-date and FIR-number checks without changing the code.
This step:

1. **fixes four recorded weaknesses**, measured before and after on the
   existing validation corpora;
2. **checks the fixes on new, held-out cases** written before they were run,
   so the improvement is not just the original cases being "taught" to pass;
3. **adds an accident-time check**.

Still deterministic and rule-based: no AI model, no new dependency, no
schema or migration change, no decision or risk-fusion change.

## 2. Files

| File | Change |
|---|---|
| `backend/app/services/accident_consistency.py` | FIR and date fixes; new accident-time check |
| `backend/app/services/semantic_consistency.py` | Location keyword and calendar-word fixes |
| `backend/app/schemas/semantic_consistency.py` | `accident_time` added to `accident_details` |
| `backend/app/api/v1/routers/officer.py` | Returns `accident_time` |
| `backend/tests/accident_consistency_corpus.py` | 3 cases updated, 5 held-out cases, 11 time cases |
| `backend/tests/semantic_validation_corpus.py` | 3 cases updated, 5 held-out cases |
| `backend/tests/test_accident_consistency.py` | Time tests, updated summary counts |
| `backend/tests/test_semantic_consistency_corpus.py` | Updated summary counts |
| `frontend/src/components/officer/ConsistencyFindingsPanel.jsx` | "Accident Time" row; rows missing from a response are skipped |
| `frontend/src/components/officer/__tests__/ConsistencyFindingsPanel.test.jsx` | 1 new test |

## 3. Fixes

| # | Check | Weakness (case) | Fix |
|---|---|---|---|
| 1 | FIR number | `123 / 2026` read as `123` - a **false MISMATCH** (F07) | Spaces allowed around `/` when digits follow. Not around `-`, so "FIR No: 123 - registered" cannot pull in the next word |
| 2 | Accident date | `20-AUG-2026` not read (A12) | `-` and `/` accepted between day, month name and year |
| 3 | Accident date | "occurred near Anna Salai on 20/08/2026" not read (A09) | Up to 60 characters allowed between "occurred/happened" and "on", never crossing a full stop or line break |
| 4 | Location | "At Anna Salai, ..." not read (V12); "in March" taken as a place (V15); "near Anna Salai Monday" (V17, a **false CONTRADICTION**) | Keyword may start with a capital letter (the place still must); day and month names removed from the end of a place, and ignored when they are the whole "place" |

Not fixed, deliberately: "Anna Salai" vs "Anna Salai Junction" (V10). Treating
one name contained in another as the same place would also merge real
neighbouring areas such as "Anna Nagar" and "Anna Nagar West".

## 4. Results Before and After

**Original cases** (same text, same ideal labels):

| Check | Before | After | Changed cases |
|---|---|---|---|
| Location (V01-V18) | 8 / 18 agree, 3 false contradictions | **11 / 18** agree, 2 false contradictions | V12, V15, V17 now correct |
| Accident date + FIR (A01-A12, F01-F08) | 14 / 20 agree, 1 false mismatch | **17 / 20** agree, **0** false mismatches | A09, A12, F07 now correct |

No case got worse.

**Held-out cases**, written after the fixes but before they were run, with
wording the fixes had not seen:

| Case | Text | Ideal | Observed |
|---|---|---|---|
| V19 | `At Gandhipuram, two cars collided.` vs `near Gandhipuram` | CONSISTENT | CONSISTENT |
| V20 | `near Guindy Tuesday evening` vs `near Guindy` | CONSISTENT | CONSISTENT |
| V21 | `In April the vehicle met with an accident near Velachery.` vs `near Velachery` | CONSISTENT | CONSISTENT |
| V22 | `At Guindy the car hit a road divider.` vs `near Tambaram` | CONTRADICTION | CONTRADICTION |
| V23 | `In Chennai the accident happened near Guindy.` vs `near Guindy` | CONSISTENT | INCONCLUSIVE |
| A13 | `The collision happened at Guindy junction on 20th Aug 2026.` | MATCH | MATCH |
| A14 | `Date of accident: 20-08-2026. Report dated 25-AUG-2026.` | MATCH | MATCH |
| A15 | `The accident occurred near Anna Salai. On 22/08/2026 the vehicle was towed.` | UNAVAILABLE | UNAVAILABLE |
| F09 | `FIR No: 123 / 2026 dated 20/08/2026` | MATCH | MATCH |
| F10 | `F.I.R. No. 77 / 2025` | MISMATCH | MISMATCH |

9 of 10 held-out cases agree. V23 still fails because a city and a street in
one sentence remain ambiguous by design (the same limitation as V09). A15
confirms the wider "occurred ... on" window does not pick up a date from the
next sentence, and V22 confirms the capital-letter fix also exposes real
disagreements, not only agreements.

**Corpus totals now:** location 15 / 23 agree (2 false contradictions, 5
missed agreements, 1 missed contradiction, 0 false agreements); accident
date and FIR 22 / 25 agree (3 reported unavailable, 0 false mismatches, 0
false matches).

## 5. Accident Time Check

Compares a **labelled** accident time in the FIR and Survey Report with
`Accident.Accident_Time`, returned as `accident_details.accident_time` and
shown as an "Accident Time" row in the officer's Accident Details section.

- Labels: `Time of accident/incident/occurrence/collision`,
  `Accident/Incident/Collision time`, and "<accident> occurred/happened/took
  place ... at <time>" (same 60-character, same-sentence window as dates).
- Shapes: `18:30`, `18.30`, `6:30 PM`, `6.30 p.m.`, `6 PM`, `1845 hrs`.
  A dotted date such as `20.08.2026` is not read as a time.
- **Tolerance: within 30 minutes counts as MATCH**, because reported times
  are usually approximate. A documented design choice, not a measured value.
  Differences are measured across midnight (23:50 vs 00:10 is 20 minutes).
- **A recorded 00:00 is treated as "no time on record"** (UNAVAILABLE).
  `claim_creation.py` stores 00:00 when the customer leaves the time blank,
  so 00:00 cannot be told apart from a genuine midnight accident.

Validation corpus (record 18:30), all written before the check was first run:

| Case | Text | Ideal | Observed |
|---|---|---|---|
| T01 | `Time of accident: 18:30` | MATCH | MATCH |
| T02 | `Time of accident: 6:30 PM` | MATCH | MATCH |
| T03 | `The accident occurred near Anna Salai at 6.30 p.m.` | MATCH | MATCH |
| T04 | `Accident time: 1845 hrs` (15 min) | MATCH | MATCH |
| T05 | `Time of accident: 7:15 PM` (45 min) | MISMATCH | MISMATCH |
| T06 | `Time of accident: 6:30 AM` | MISMATCH | MISMATCH |
| T07 | FIR `18:30`, Survey Report `21:00` | MISMATCH | MISMATCH |
| T08 | `Report generated at 10:15 AM.` (unlabelled) | UNAVAILABLE | UNAVAILABLE |
| T09 | `The accident occurred at around 6:30 PM.` | MATCH | **UNAVAILABLE** |
| T10 | `The accident occurred in the evening.` | UNAVAILABLE | UNAVAILABLE |
| T11 | `Date of accident: 20.08.2026` | UNAVAILABLE | UNAVAILABLE |

10 / 11 agree; T09 ("at around") is missed and reported UNAVAILABLE, never as
a wrong verdict.

## 6. Limitations

- All corpora are hand-written; no real FIR or survey documents.
- The fixes were designed after seeing the original failures; the held-out
  cases reduce, but cannot remove, that bias.
- Not fixed: month-first and two-digit-year dates (A10, A11), "Cr. No."
  (F08), "at around <time>" (T09), city + street ambiguity (V09, V23),
  name variants and aliases (V10, V11), hospital names (V16).
- Accident city is not checked: the customer form stores the free-text place
  of accident as the city (`claim_creation.py`), so there is no separate,
  reliable city value to compare against.

## 7. Validation

- Backend: 459 tests collected, 458 passing (35 new). The one failure
  (`test_valid_risk_fusion_result_returned_correctly`) is unrelated: it
  needs the git-ignored Step 5.4 risk-fusion artifacts under
  `ai_ml/model_artifacts/`, which are not present on this machine.
- Frontend: 152/152 tests passing (1 new). On this low-memory laptop the
  suite must be run with `npx vitest run --maxWorkers=1`; run in parallel it
  ran out of memory. oxlint reports no warnings on the changed files;
  `vite build` succeeds.
