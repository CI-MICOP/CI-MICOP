# Evidence Duplication / Reuse Check (Step 5.8.14)

## 1. Objective

Roadmap item 4: give the Claims Officer a way to see whether a photo on a
claim also appears elsewhere among the evidence photos stored by the
application - either as the identical file or as a lightly edited copy
(resized, re-saved, brightened).

Until now nothing computed this. `services/evidence_upload.py` stores
`Duplicate_Evidence_Indicator=False` as an honest "not yet analyzed"
placeholder, and `services/ai_pipeline.py` reports the
`evidence_duplication` signal as unavailable. This step adds the check
itself. It does **not** connect it to risk fusion (roadmap item 8: only
validated signals are integrated).

This is an investigative aid, not fraud detection. A match means "the same
picture is stored more than once", which can have innocent causes (a
surveyor uploading the same photo twice, a customer resubmitting).

## 2. Files

| File | Change |
|---|---|
| `backend/app/services/evidence_duplication.py` | New - fingerprinting and comparison |
| `backend/app/schemas/evidence_duplication.py` | New - response models |
| `backend/app/api/v1/routers/officer.py` | One new endpoint |
| `backend/app/crud/evidence.py` | Added `list_all()` |
| `backend/tests/evidence_duplication_corpus.py` | New - 18 generated-image cases |
| `backend/tests/test_evidence_duplication.py` | New - 32 tests |
| `docs/project_documentation/EVIDENCE_DUPLICATION.md` | This document |

No dependency, schema, migration, frontend, risk-fusion or decision change.

## 3. Method

No AI or image-recognition model is used. Two fingerprints are computed
for every readable stored evidence file:

1. **SHA-256 of the file bytes.** Equal hashes mean the files are
   byte-for-byte identical: an **exact** copy.
2. **A 64-bit difference hash (dHash)**, a perceptual hash. The image is
   shrunk to a 9 x 8 greyscale thumbnail, and each of the 64 bits records
   whether a pixel is brighter than its right-hand neighbour. Resizing,
   re-compression or a mild brightness change barely moves these
   comparisons; a different picture changes about half of them. Two photos
   are a **near** copy when their hashes differ in at most
   `NEAR_DUPLICATE_MAX_DISTANCE = 10` of the 64 bits.

Both use only Pillow, which the backend already depends on (Step 5.8.12).

This corresponds to the "SHA-256 · pHash" part of the evidence-reuse design
in the project presentation. The embedding-model part (CLIP) is
deliberately deferred: it would need a heavy new dependency (PyTorch) and a
labelled set of real claim photos to validate it against, neither of which
exists. Per the handoff rules, heavy ML dependencies are added only with a
justified research need.

## 4. Endpoint and Results

`POST /api/v1/officer/claims/{claim_id}/evidence/duplication-check`
(Claims Officer or Admin only; customers and surveyors receive 403).

Each photo on the claim is compared with **every other stored evidence
photo**, on the same claim and on other claims, because reuse across claims
is the case this check exists for. Officers and admins may already view
every claim, so this does not widen anyone's access.

Per photo, one of:

| Status | Meaning |
|---|---|
| `EXACT_DUPLICATE` | An identical file is stored as another evidence item |
| `NEAR_DUPLICATE` | A visually near-identical photo is stored as another evidence item |
| `NO_MATCH_FOUND` | No identical or near-identical copy among the stored photos that could be read. This does not prove the photo is original |
| `UNAVAILABLE` | The stored file is missing or unreadable, or cannot be decoded as an image (in which case only the exact check could run) |

Each match lists the other evidence ID, its claim, whether it is on the
same claim, `EXACT` or `NEAR`, and the number of differing hash bits. There
is no score and no confidence value. Explanations end with "Possible
evidence reuse identified for officer review" and never use the word
"fraud" (asserted by tests).

**Read-time only.** Nothing is stored: `Duplicate_Evidence_Indicator` is not
written (asserted by a test), and `Final_Decision`, `Approved_Amount` and
`claim_decision_audit` are never touched (asserted by a test). This follows
the same pattern as Steps 5.8.13-B and 5.8.13-C.

## 5. Choosing the Threshold

During development, a scratch measurement compared the dHash of 20
generated images against edited versions of themselves, and 30 different
generated images against each other (435 pairs):

| Edit | Bits differing (min - max over 20 images) |
|---|---|
| Resized to 50% | 0 - 2 |
| JPEG quality 60 / 30 | 0 - 3 / 0 - 5 |
| Brightened 15% / darkened 25% | 0 - 6 / 0 - 5 |
| Greyscale | 0 - 0 |
| Cropped 3% | 1 - 12 |
| Cropped 10% / 20% | 10 - 31 / 15 - 36 |
| Rotated 5 degrees | 7 - 27 |
| Mirrored / rotated 90 degrees | 24 - 40 / 18 - 44 |
| **Different images** | **19 - 44** |

A threshold of 10 accepts every resize, re-compression, brightness and
greyscale edit, and stays 9 bits below the closest pair of genuinely
different images. It was fixed before the validation corpus below was run
and was not adjusted afterwards.

## 6. Validation Corpus

`backend/tests/evidence_duplication_corpus.py` holds 18 cases. Each pair of
images is generated with Pillow from fixed seeds, so the results are
exactly repeatable. `should_match` is what a careful person would say;
`observed` is what the check returned on 2026-10-03.

| Case | Second image | Bits differing | Should match | Observed |
|---|---|---:|---|---|
| D01 | Identical file | 0 | Yes | EXACT |
| D02 | Resized to 50% | 0 | Yes | NEAR |
| D03 | JPEG quality 60 | 2 | Yes | NEAR |
| D04 | JPEG quality 30 | 1 | Yes | NEAR |
| D05 | Brightened 15% | 5 | Yes | NEAR |
| D06 | Darkened 25% | 1 | Yes | NEAR |
| D07 | Greyscale | 0 | Yes | NEAR |
| D08 | Edges cropped 3% | 11 | Yes | **missed** |
| D09 | Edges cropped 10% | 13 | Yes | missed |
| D10 | Edges cropped 20% | 18 | Yes | missed |
| D11 | Mirrored | 21 | Yes | missed |
| D12 | Rotated 90 degrees | 32 | Yes | missed |
| D13 | Rotated 5 degrees | 16 | Yes | missed |
| D14-D18 | Five different images | 27 - 36 | No | no match (all five) |

Summary:

| Outcome | Count |
|---|---:|
| Copies caught | 7 / 13 |
| Copies missed | 6 / 13 |
| Different images correctly not matched | 5 / 5 |
| False matches (different images reported as copies) | 0 |

The corpus is deliberately weighted towards edits expected to defeat a
perceptual hash, so 7 / 13 describes this corpus only and is not a
detection rate.

## 7. Findings

1. **Exact reuse and simple edits are caught reliably.** Identical files,
   resized, re-compressed, brightened, darkened and greyscale copies were
   all found, in the corpus and through the real upload pipeline.
2. **Geometric edits defeat it.** Mirroring, rotation and cropping move the
   thumbnail's pixels, so the hash changes as much as for a different
   photo. Even a 3% crop (D08, 11 bits) fell just outside the threshold. A
   person trying to hide reuse could do this easily.
3. **No false matches were observed.** Different images were never closer
   than 19 bits during threshold selection, or 27 bits in the corpus.
4. **It only sees this application's own photos.** Stock or internet
   photos, or photos held by another insurer, cannot be detected.

## 8. Tests

- Algorithm: exact matching, hash size, undecodable files, missing files,
  no "fraud" wording.
- Corpus: every case pinned to its observed result, plus a summary test
  that pins the counts in Section 6.
- End-to-end through the real API, database and file storage:
  - the same photo uploaded on two different claims by two different
    surveyors -> `EXACT_DUPLICATE`, match on the other claim;
  - a resized, re-saved copy on the same claim -> `NEAR_DUPLICATE`;
  - a different photo -> `NO_MATCH_FOUND`;
  - a file that passes the upload check but is not a real image ->
    `UNAVAILABLE`.
- Access: customer and surveyor 403, admin 200, unknown claim 404.
- Safety: the indicator, the final decision, the approved amount and the
  audit log are unchanged after the check.

Backend: 357 tests collected, 356 passing. The 32 new tests all pass. The
one failure (`test_valid_risk_fusion_result_returned_correctly`) is
unrelated: it needs the git-ignored Step 5.4 risk-fusion artifacts under
`ai_ml/model_artifacts/`, which are not present on the machine used for
this step.

## 9. Limitations

- Generated test images, not real accident photos.
- Every request reads and fingerprints every stored evidence file. Fine for
  this prototype's data volume, but a larger deployment would store each
  file's fingerprints once, at upload time (which would need a schema
  change and is out of scope here).
- Mirrored, rotated and cropped copies are not detected.
- Seeded development rows (e.g. `DEV-EVD-001`) have no physical file and
  report `UNAVAILABLE`.

## 10. Officer UI

An **Evidence Check** tab on the officer's claim workspace
(`/officer/claims/{claim_id}/evidence`) shows these results, following the
Step 5.8.13-D pattern:

- `frontend/src/pages/officer/EvidenceCheckPage.jsx` and
  `frontend/src/components/officer/EvidenceDuplicationPanel.jsx`;
  `checkEvidenceDuplication()` in `services/officerService.js`.
- One explicit **Check Photos** button; nothing runs on page load.
- Each photo shows its status, the explanation, and every match (evidence
  ID, "same claim" or the other claim's ID, exact or near, and differing
  fingerprint bits), followed by the limitations list.
- Badge tones: a copy found is amber ("needs review"), never red; "No copy
  found" and "Unavailable" are grey, because not finding a copy does not
  prove a photo is original.
- The same notice as the consistency panel: findings are for officer review
  only and are not an accusation; the officer makes the final decision.
- 9 frontend tests, including: no automatic run, exact match on another
  claim, near match with bit distance, no photos, error, no "fraud" text,
  and no call to the decision workflow.

## 11. Possible Next Steps (not implemented)

- Also comparing mirrored versions, which is cheap and would catch D11-type
  reuse.
- Once validated, feeding the result to the `evidence_duplication` signal in
  `ai_pipeline.py` (roadmap item 8).
- An embedding model such as CLIP for crop- and rotation-resistant matching,
  only if a labelled real photo set becomes available to validate it.
