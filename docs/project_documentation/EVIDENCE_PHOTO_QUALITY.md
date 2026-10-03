# Evidence Photo Quality Check (Step 5.8.15)

## 1. Objective

Roadmap item 5 asks for information-quality analysis. In the Step 5.4
research, the `information_quality` signal is the mean of three dataset
columns: `Document.OCR_Confidence_Score`, `Evidence.Image_Quality` and
`Evidence.Evidence_Confidence_Score`. For anything uploaded through the live
application, the two evidence columns are always `0.0000` "not yet
analyzed" placeholders, so the signal is always unavailable.

This step adds the photo part: a check of whether each evidence photo is
large, bright, contrasty and sharp enough to rely on. It reports plain flags
to the Claims Officer. It does **not** connect anything to risk fusion
(roadmap item 8: only validated signals are integrated).

Out of scope for this step:

- **Document readability.** It is already shown per document by "Analyze
  Documents" on the Document Consistency tab (Step 5.8.12 extraction status
  and OCR limitations).
- **Document-mismatch summary** (combining the Step 5.8.13 consistency
  results into one claim-level result). That is integration work and
  belongs with roadmap item 8.

## 2. Files

| File | Change |
|---|---|
| `backend/app/services/evidence_quality.py` | New - measurements and flags |
| `backend/app/schemas/evidence_quality.py` | New - response models |
| `backend/app/api/v1/routers/officer.py` | One new endpoint |
| `backend/tests/photo_quality_corpus.py` | New - 15 generated-image cases |
| `backend/tests/test_evidence_quality.py` | New - 28 tests |
| `frontend/src/components/officer/PhotoQualityPanel.jsx` | New panel |
| `frontend/src/pages/officer/EvidenceCheckPage.jsx` | Panel added below the photo copy check |
| `frontend/src/services/officerService.js` | Added `checkPhotoQuality()` |
| `frontend/src/components/officer/__tests__/PhotoQualityPanel.test.jsx` | New - 7 tests |
| `frontend/src/pages/officer/__tests__/EvidenceCheckPage.test.jsx` | Updated for the second panel |

No dependency, schema or migration change.

## 3. Method

No AI or image-recognition model is used. Pillow (already a backend
dependency) computes, on a greyscale copy of the photo:

| Measurement | How | Flag | Threshold |
|---|---|---|---|
| Resolution | the photo's own width x height | `LOW_RESOLUTION` | shorter side < 480 px |
| Brightness | mean grey level, 0 (black) - 255 (white) | `TOO_DARK` / `TOO_BRIGHT` | < 60 / > 200 |
| Contrast | standard deviation of grey levels | `LOW_CONTRAST` | < 15 |
| Blur | **re-blur ratio**: edge detail left after an extra Gaussian blur (radius 2), divided by the photo's own edge detail | `BLURRY` | > 0.80 |

The re-blur ratio works because blurring a sharp photo destroys most of its
edge detail (low ratio), while blurring an already-blurry photo changes
little (ratio near 1). Being a ratio, it does not depend on how bright or
contrasty the photo is. Photos wider than 640 px are shrunk to 640 px wide
before brightness, contrast and blur are measured, so results are
comparable and fast; smaller photos are never enlarged, because enlarging
would itself make them look blurry. Resolution is always reported from the
original file.

There is deliberately **no single combined quality score**: the officer sees
the raw measurements and the plain flags they triggered.

## 4. Endpoint and Results

`POST /api/v1/officer/claims/{claim_id}/evidence/quality-check`
(Claims Officer or Admin only; customers and surveyors receive 403). Only
this claim's own photos are read.

| Status | Meaning |
|---|---|
| `NO_ISSUES_FOUND` | No flag triggered |
| `ISSUES_FOUND` | One or more flags, listed with an explanation suggesting a clearer photo |
| `UNAVAILABLE` | The stored file is missing or cannot be decoded as an image |

**Read-time only.** `Evidence.Image_Quality` and
`Evidence.Evidence_Confidence_Score` are not written (asserted by a test),
and `Final_Decision`, `Approved_Amount` and `claim_decision_audit` are never
touched (asserted by a test). No explanation or limitation uses the word
"fraud" (asserted by tests).

**Officer UI.** A **Photo Quality** panel on the Evidence Check tab, with
one **Check Quality** button (nothing runs on page load). Each photo shows
its status, one amber badge per flag, the explanation, and the four
measurements, followed by the limitations list.

## 5. Choosing the Thresholds

During development, scratch measurements were taken on 12 generated images
under each degradation. Two kinds of generated image were used: smooth
shapes only, and the same shapes with fine random texture (closer to the
small-scale detail of a real photo).

**Brightness and contrast** (both image kinds gave the same ranges):

| Degradation | Brightness | Contrast |
|---|---|---|
| None | 92 - 162 | 23 - 54 |
| Blur radius 8 | 92 - 162 | 21 - 50 |
| 30% brightness | 27 - 48 | 7 - 16 |
| 15% brightness | 13 - 24 | 3 - 8 |
| 250% brightness | 187 - 237 | 15 - 56 |
| 20% contrast | 92 - 162 | 5 - 11 |

**Blur.** A first attempt used raw edge strength (Laplacian variance). It
was rejected: on smooth images, sharp and blurred results overlapped
heavily, and darkened images scored as *sharper*. The re-blur ratio was then
measured:

| Degradation | Smooth images | Textured images |
|---|---|---|
| None | 0.94 - 1.00 | **0.17 - 0.26** |
| Blur radius 1 | 0.94 - 1.00 | 0.45 - 0.59 |
| Blur radius 2 / 4 / 8 | 0.92 - 1.00 | **0.88 - 0.98** |
| 30% brightness | 0.96 - 0.99 | 0.22 - 0.30 |
| 20% contrast | 0.96 - 0.99 | 0.22 - 0.31 |
| JPEG quality 20 | 0.75 - 0.87 | 0.53 - 0.66 |

On textured images the ratio cleanly separates sharp (at most 0.31,
whatever the brightness or contrast) from blurred (at least 0.88), and heavy
JPEG compression is not mistaken for blur. On smooth images everything
measures near 1: an image with no fine detail cannot be told apart from a
blurry one. This is recorded as a limitation (Section 8).

The thresholds in Section 3 sit between these ranges and were fixed before
the validation corpus was run. They were not adjusted afterwards.

## 6. Validation Corpus

`backend/tests/photo_quality_corpus.py` holds 15 cases generated from fixed
seeds, so results are exactly repeatable. `ideal_flags` is what a careful
person would expect, written before running; `observed_flags` is what the
check returned on 2026-10-03.

| Case | Image | Brightness | Contrast | Re-blur | Ideal | Observed |
|---|---|---:|---:|---:|---|---|
| Q01 | Clear | 163.2 | 37.3 | 0.19 | - | - |
| Q02 | JPEG quality 20 | 159.6 | 40.3 | 0.61 | - | - |
| Q03 | Very slight blur (r=1) | 101.7 | 17.8 | 0.41 | - | - |
| Q04 | Blurred (r=2) | 104.9 | 29.7 | 0.90 | Blurry | Blurry |
| Q05 | Blurred (r=4) | 124.7 | 28.4 | 0.93 | Blurry | Blurry |
| Q06 | Very blurred (r=8) | 139.3 | 28.0 | 0.89 | Blurry | Blurry |
| Q07 | Dark (30%) | 41.5 | 10.0 | 0.24 | Too dark | Too dark, **low contrast** |
| Q08 | Very dark (15%) | 20.1 | 4.2 | 0.18 | Too dark, low contrast | Too dark, low contrast |
| Q09 | Over-exposed (250%) | 202.2 | 24.0 | 0.14 | Too bright | Too bright |
| Q10 | Washed out (20% contrast) | 125.4 | 6.9 | 0.24 | Low contrast | Low contrast |
| Q11 | Small, 320 x 240 | 147.9 | 39.1 | 0.34 | Low resolution | Low resolution |
| Q12 | Tiny, 160 x 120 | 137.0 | 19.5 | 0.35 | Low resolution | Low resolution |
| Q13 | Dark and blurred | 38.7 | 10.6 | 0.91 | Too dark, blurry | Too dark, **low contrast**, blurry |
| Q14 | Clear but smooth, little detail | 112.3 | 46.5 | 0.97 | - | **Blurry** |
| Q15 | Large clear, 1920 x 1440 | 160.0 | 34.7 | 0.18 | - | - |

Summary:

| Outcome | Count | Cases |
|---|---:|---|
| Flags exactly as expected | 12 / 15 | Q01-Q06, Q08-Q12, Q15 |
| Expected flags plus one extra | 2 | Q07, Q13 |
| Flag on a photo that should have none | 1 | Q14 |
| Expected flag missed | 0 | - |

## 7. Findings

1. **Every expected problem was flagged**, including when two problems are
   combined (Q13), and clear photos of any size were left alone (Q01-Q03,
   Q15). Heavy compression (Q02) and very slight softness (Q03) were
   correctly not treated as problems.
2. **Darkening also lowers contrast.** In Q07 and Q13 the photo was flagged
   low contrast as well as too dark. This is technically true (darkening
   compresses the grey levels), but a person would describe the problem only
   as "too dark".
3. **Featureless photos look blurry (Q14).** With little fine detail, the
   re-blur ratio cannot distinguish "smooth" from "out of focus". On real
   photos this would affect close-ups of plain surfaces, such as a panel
   with no visible damage.
4. **The over-exposure threshold is borderline.** Q09 measured 202.2,
   just over 200; during threshold selection, 250%-brightness images ranged
   from 187 to 237, so some over-exposed photos would not be flagged.

## 8. Limitations

- Generated test images, not real accident photos; thresholds may need
  revisiting on real photos.
- Featureless photos may be flagged blurry (finding 3).
- Measures clarity only - a clear photo is not necessarily genuine or
  relevant (see the separate photo copy check, Step 5.8.14).
- Not persisted and not connected to the `information_quality` signal in
  `ai_pipeline.py`.

## 9. Validation

- Backend: 385 tests collected, 384 passing. The 28 new tests all pass. The
  one failure (`test_valid_risk_fusion_result_returned_correctly`) is
  unrelated: it needs the git-ignored Step 5.4 risk-fusion artifacts under
  `ai_ml/model_artifacts/`, which are not present on the machine used for
  this step.
- Frontend: 146/146 tests passing (7 new); oxlint reports no warnings on the
  changed files; `vite build` succeeds.

## 10. Possible Next Steps (not implemented)

- Report "too dark" alone when low contrast is only a side effect of
  darkness (finding 2).
- Re-check the thresholds on a small set of real, labelled claim photos.
- Once validated, map these measurements to the `information_quality`
  signal (roadmap item 8), together with OCR confidence where Tesseract is
  available.
