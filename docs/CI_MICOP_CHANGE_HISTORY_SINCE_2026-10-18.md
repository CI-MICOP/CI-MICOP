# CI-MICOP — Change History, 18 October 2026 to 27 October 2026

## 1. Scope and evidence

- **Range:** 18 October 2026 to the repository state on 27 October 2026.
- **Branch:** `master`, HEAD `665a256`, equal to `origin/master` (0 ahead, 0 behind after `git fetch` on 27 October 2026).
- **Sources:**
  - `git log` and `git show --stat` for each commit, and commit message bodies.
  - `git reflog` for local history that is no longer on `master`.
  - `git cherry` and tree diffs against the local branches `delivery/claim-verification-corrections` and `delivery/ocr-and-customer-portal`.
  - The current code and test runs (Section 6).
- **Limits of the evidence:**
  - **Dates.** Author and committer dates are given where they differ. Several commits were rewritten before being pushed (rebased or amended), so the author date is when the change was first written, not when it reached `master`.
  - **Reasons.** These come from commit messages and code comments only. Where a message doesn't say why, none is given.
  - **Test results.** Results quoted from commit messages or earlier session reports were **not** re-run unless Section 6 says so.
  - **Local history.** Local history before 27 October 10:24 (IST) was replaced by a reset to `origin/master`, followed by one consolidated commit (Section 2.9). The replaced local commits are reachable only through the local reflog.

---

## 2. Chronological commit history (reachable from `master`)

### 2.1 `a55bb53` — fix: strengthen JWT security and restrict production API documentation
- **Dates:** author 2026-10-14; committer **2026-10-18** (amended; the reflog shows `commit (amend)` on 2026-10-18 17:56).
- **Files:**
  - `backend/app/core/config.py`, `core/security.py`, `main.py`, `api/v1/deps.py`, `backend/.env.example`
  - `tests/test_startup_security.py` (new), `tests/test_security_regression.py`
  - `SECURITY_AND_REGRESSION_REVIEW.md`
- **Change:**
  - The startup security check (`settings.check_startup_security()`).
  - `/docs`, `/redoc` and `/openapi.json` are served only in development or test environments.
  - Outside development, startup is refused unless `JWT_SECRET_KEY` is a random value of at least 32 characters (per the `.env.example` comment).
- **Impact:** security; no schema, migration, seed or Docker change. `.env.example` gained a comment only.

### 2.2 `b1da341` — fix(ocr): distinguish OCR-unavailable scanned PDFs and correct OCR-misread registration numbers
- **Date:** 2026-10-23.
- **Files:** `document_analysis.py`, `document_consistency.py`, `entity_extraction.py` and their tests.
- **Change:** scanned PDFs are reported as OCR-unavailable rather than empty, and registration numbers that OCR misreads (O/0 and I/1 confusion) are corrected.
- **Impact:** verification accuracy; no schema change.

### 2.3 `7f52886` — feat(frontend): floating dock navigation, simplified customer dashboard and blue theme
- **Dates:** author 2026-10-23; committer 2026-10-26.
- **Files:**
  - `components/common/FloatingDock.jsx` (new), `Sidebar.jsx` (deleted), `TopHeader.jsx`, `layouts/AppShell.jsx`
  - the role dashboards (admin, customer, officer, surveyor), `routes/navConfig.js`, `styles/tokens.js`, `tailwind.config.js`
  - chart components and `AppShell.test.jsx`
- **Change:** the sidebar was replaced by a floating bottom dock for every role; the customer dashboard was simplified; a blue theme was applied.
- **Note:** the same change existed locally as `45f670f` (author time identical). `45f670f` additionally sat on top of the local dataset commit `0a67c33`. Tree comparison shows `7f52886` equals `45f670f` minus the dataset files.
- **Impact:** frontend only.

### 2.4 `04567e2` — feat(customer): enforce document upload rules and camera-only accident photos
- **Date:** 2026-10-26.
- **Files:**
  - Backend: `crud/document.py`, `schemas/document.py`, `services/claim_copy_retention.py` (new), `services/claim_photos.py` (new), `document_analysis.py`, `document_upload.py`, `evidence_duplication.py`, `evidence_quality.py`.
  - Frontend: `AccidentPhotoCapture.jsx` (new), `DocumentUploadGrid.jsx`, `documentCategories.js`, `NewClaimPage.jsx`, `UploadDocumentsPage.jsx`, `DocumentsPage.jsx`, `SupportPage.jsx`.
  - Tests, plus `CUSTOMER_DOCUMENT_UPLOAD.md`.
- **Change (from the commit message):**
  - Driving licence, RC and policy copies are required with every claim.
  - Accident photos are camera-only in the portal.
  - RC, licence and policy copies are read in memory and **not stored**; only the details the checks read are kept, under a neutral name.
  - Accident-photo uploads must be JPEG or PNG.
  - The photo duplicate and quality checks also cover customer photos, labelled by source.
  - The Support FAQ was updated to say the same.
- **Caveat:** camera-only is enforced in the browser; the API accepts any JPEG or PNG for `accident_photos` (current `document_upload.py`).
- **Impact:** "No schema or migration changes" (commit message). Customer documents created afterwards for RC, licence and policy have no stored file.

### 2.5 `3f50131` — fix(verification): accept FIR-No labels and check policy cover on the accident date
- **Date:** 2026-10-26.
- **Files:** `accident_consistency.py`, `policy_cover.py` (new), corpus and tests, `ACCIDENT_DETAIL_CONSISTENCY.md`.
- **Change:** the FIR-number pattern accepts "FIR-No" variants. The new `policy_cover` service returns COVERED, EXPIRED, NOT_STARTED or CANNOT_RUN on the accident date.
- **Tests:** the commit message reports corpus cases F11–F15 added ("27 / 30 agree"). Not re-run as a separate figure here.
- **Impact:** no schema change.

### 2.6 `c7c7261` — feat(verification): distinguish outcomes and check RC, licence and policy validity
- **Date:** 2026-10-26.
- **Files:**
  - `verification_outcome.py` (new), `document_validity.py` (new), `document_fields.py` (new)
  - `accident_consistency.py`, `document_consistency.py`, `claim_copy_retention.py`, `policy_cover.py`
  - `routers/officer.py`, `routers/documents.py`, schemas, `tests/test_document_validity.py`
- **Change:**
  - Seven outcomes (VERIFIED, MISMATCH, NOT_SUBMITTED, REFERENCE_UNAVAILABLE, INVALID_OR_EXPIRED, VERIFICATION_UNAVAILABLE, INCONCLUSIVE), added beside the existing MATCH / MISMATCH / UNAVAILABLE status.
  - RC validity, licence validity, class and number, and policy cover on the accident date.
  - An optional `validity` section in the officer consistency response.
- **Impact:** "No schema, migration or database changes" (commit message).

### 2.7 `ea69899` — feat(officer): show verification outcomes and validity on the accident date
- **Dates:** author 2026-10-26 10:51; committer 2026-10-26 13:54.
- **Files:** `components/officer/ConsistencyFindingsPanel.jsx` and its test.
- **Change:**
  - Shows the outcome labels (Verified, Not submitted, No insurer record, Invalid / expired, Could not check, Inconclusive, Mismatch).
  - States that identifiers are compared with structured insurer records, not an insurer-held document.
  - Adds "Validity on the Accident Date".
- **Impact:** frontend only.

### 2.8 Local history that was replaced (not reachable from `master`)
Evidence: `git reflog`.

| Local commit | Date | Message | What happened to it |
|---|---|---|---|
| `0a67c33` | 2026-10-23 | feat(seed): add 20-scenario synthetic seed dataset with offline validation | **Never pushed.** Dataset only (`backend/scenario_seed/*`, `test_scenario_seed_dataset.py`, 4 `.gitignore` lines). Its content was restored into the working tree, uncommitted (Section 5) |
| `45f670f` | 2026-10-23 | feat(frontend): floating dock navigation, … | Superseded by `7f52886` (same change, without the dataset) |
| `77a4e02` | 2026-10-27 10:01 | feat(surveyor): camera-only evidence workflow with server-enforced separation, corrections and schedule | **Never pushed.** Its content was re-applied onto `origin/master` and became part of `665a256` |

On 2026-10-27 10:24 local `master` was reset to `origin/master` (`ea69899`), and `665a256` was created on top of it.

### 2.9 `665a256` — feat(surveyor): secure claim document viewing
- **Date:** 2026-10-27 10:44.
- **Size:** 72 files, +8,860 / −1,980.
- **Scope:** this one commit holds the whole Surveyor Dashboard work (the content of local `77a4e02`) plus the Claim Documents viewer. The `77a4e02` changes were integrated with `04567e2`: the remote's customer accident-photo implementation was kept, and the surveyor code was adapted to it.

**Backend:**
- `services/surveyor_workflow.py` (new):
  - schedule from 00:00 IST on `Inspection_Date`;
  - step order; completeness; step locks;
  - correction mode; submission prerequisites;
  - finality for every role; the `submission_review` for historical reports.
- `services/workflow_state.py` (new): per-inspection correction state with an audit history, in JSON. Atomic writes; an in-process lock; corrupt files fail closed and are never overwritten.
- `services/evidence_capture.py` (new): write-once capture records for surveyor camera photos, accepted only when well-formed, matching their row and still matching the photo's hash and size.
- `services/evidence_upload.py`:
  - camera capture only (`capture_evidence_for_surveyor`);
  - four evidence types and per-photo evidence date;
  - the legacy file-upload function removed;
  - `EVIDENCE_SOURCE_VALUES` removed (see Section 4).
- `services/survey_report.py`, `survey_report_pdf.py` (new): one report dict for the JSON view and the PDF, holding surveyor captures only.
- `services/surveyor_documents.py` (new): the Claim Documents list and content.
- `services/inspection_creation.py` uses the IST date; `vehicle_damage_creation.py` enforces the workflow locks.
- `routers/surveyor.py`:
  - active and submitted lists; report and PDF endpoints;
  - capture and image endpoints; correction endpoints;
  - the documents endpoints;
  - `POST /surveyor/evidence` answers 410.
- `routers/documents.py`:
  - surveyors cannot list, read or analyze "Accident Photos" documents;
  - documents on inaccessible claims answer 404 like missing ones;
  - surveyor completeness doesn't reveal accident photos.

**Frontend:**
- Surveyor pages rewritten: Claim Details (with the Claim Documents panel), Inspection, Vehicle Damage, Evidence (camera only, multiple photos, per-photo type and date), Survey Report, Survey Report view, history.
- The Repair Estimate page was removed.
- New components: `ClaimStepNav`, `ClaimTabs`, `WorkflowNotices`, `SurveyReportContent`, `SurveyReportActions`, `EvidenceThumbnail`, `ClaimDocumentsPanel`, `components/camera/CameraView.jsx`.
- `navConfig.js` gives the surveyor dock Home, Inspections and Survey Reports.
- `Modal.jsx` gained a size option; `DataTable.jsx` gained column alignment.

**Tests and docs:**
- `tests/test_survey_report_rules.py` (database-free), `test_survey_report_pdf.py`, and a new `surveyor_records.py` fixture helper.
- Updates to the database-backed suites (`test_evidence.py`, `test_document_upload.py`, `test_document_analysis.py`, `test_survey_report.py`, `test_surveyor_inspection.py`, `test_vehicle_damage.py`, `test_repair_estimate_checks.py`, `test_evidence_duplication.py`, `test_evidence_quality.py`, `test_live_signal_integration.py`).
- Many frontend tests.
- A section in `SURVEYOR_INSPECTION_WORKFLOW.md`.

**Tests reported at commit time** (earlier session report, not re-run as a figure here):
- Frontend: 301/301, lint 0 errors, build OK.
- Backend, database-free: 402 passed, 2 skipped.
- Database-backed: not run.

**Impact:** no schema, migration, seed, `.env` or Docker change. It adds JSON files under `EVIDENCE_STORAGE_ROOT` at run time (capture records and correction state).

---

## 3. Major implementation milestones (verified in code on `master`)

- **Navigation:** floating dock for every role (`7f52886`).
- **Customer documents** (`04567e2`):
  - RC, licence and policy copies are required and **not stored**;
  - camera-only accident photos in the portal;
  - an updated FAQ;
  - photo checks over customer and surveyor photos.
- **Officer verification:**
  - OCR improvements (`b1da341`);
  - FIR variants and policy cover (`3f50131`);
  - seven outcomes and accident-date validity (`c7c7261`);
  - officer panel labels (`ea69899`).
- **Surveyor workflow** (`665a256`):
  - server-enforced schedule (IST), step order and correction mode;
  - submission prerequisites and finality;
  - camera-only evidence with verified capture records;
  - customer and surveyor evidence separation;
  - report, PDF and history;
  - historical submission warnings;
  - the secure Claim Documents viewer.
- **Security:** startup security and API docs restricted to development (`a55bb53`); uniform 404 for inaccessible documents (`665a256`).

---

## 4. Outstanding work found during this period

The full backlog, with acceptance criteria, is in `docs/CI_MICOP_PROJECT_HANDOFF.md`, Section 12.

**Deferred on purpose:**
- **AI fraud detection.** The user's friend will take it on after 31 October 2026. `ai_pipeline.py` reports `fraud_screening_rule_score` as unavailable.
- **Storage in the database.** Capture records, correction state, an audit table, inspection links and a report snapshot all need an approved schema change (handoff B1–B3, B6).

**Incomplete:**
- **Customer camera-only rule is frontend-only.** Evidence: `document_upload.py` accepts any JPEG or PNG; the `04567e2` message says the API accepts it. Next: handoff A1.
- **Assignment can't set a future date.** It always records today, and the server's local date (`surveyor_assignment.py`). Next: A3 and A4.
- **Surveyor repair-estimate endpoint** is live without a UI and outside the workflow locks (`repair_estimate_creation.py`). Next: A5.
- **Dataset no longer loads.** It imports a name `665a256` removed (`scenario_seed/checks.py` line 38). Next: A2, in a separate approved dataset task.

**Testing not performed:**
- The database-backed suites (526 tests).
- A live end-to-end run.
- Real-device camera and GPS.
- Multi-worker behaviour.

**Blocked:**
- An isolated test database (needs approval).
- Insurer reference data, licence records and registry APIs (schema, plus external services).

**Optional recommendations:**
- Complete `backend/.env.example`.
- Refresh `README.md`, whose status section stops at Step 3.
- Code-split the frontend build.

---

## 5. Current Git state (27 October 2026)

- **Branch and HEAD:** `master` at `665a256`, equal to `origin/master`.
- **Local-only branches (not pushed):**
  - `delivery/claim-verification-corrections` (tip `304d824`): differently-hashed versions of the verification and customer commits, plus two dataset commits (`9110873`, `304d824`) and 26 October revisions of the two assessment documents. Compared with `master`, its non-dataset code is older (for example the officer dashboard), not additional.
  - `delivery/ocr-and-customer-portal` (tip `bfc8200`): an older customer-portal and theme revision.
- **Uncommitted changes (all from before this documentation task):**
  - `.gitignore`: 4 lines ignoring `backend/scenario_seed/generated/` and `credentials.local.csv`. Dataset-related.
  - `frontend/src/pages/customer/SupportPage.jsx` and `__tests__/SupportPage.test.jsx`: an **older** FAQ draft that reverses part of `04567e2`. It drops the required RC, licence and policy copies and the camera-only and verification explanations. Not to be published.
- **Untracked files (from before this task):**
  - `backend/scenario_seed/` and `backend/tests/test_scenario_seed_dataset.py`: the 24 October dataset work. A 26 October version is on `delivery/claim-verification-corrections`; which one is canonical **needs a decision**.
  - `docs/CI_MICOP_CORRECTIVE_IMPLEMENTATION_PROMPT.md` and `docs/CI_MICOP_DATASET_AND_VERIFICATION_ASSESSMENT.md`: 24 October versions, stale against `master`.
- **Created by this task:** `docs/CI_MICOP_PROJECT_HANDOFF.md` and this file.

---

## 6. Verification gaps

**Run on 27 October 2026 while writing this document:**

| Check | Result |
|---|---|
| `npm test` | 300/300. This is the working tree, which includes the older FAQ draft's 2-test file |
| `npm run lint` | 0 errors, 3 warnings |
| `npm run build` | Succeeds |
| Backend `pytest --noconftest` with a database-connection guard | 402 passed, 2 skipped, 0 failed, 0 connection attempts; 526 not run (database fixtures) |
| `tests/test_scenario_seed_dataset.py` | Collection error (`ImportError` for `EVIDENCE_SOURCE_VALUES`) |

**Not run (none of these failed; they were simply not run):**
- the 526 database-backed tests;
- `alembic upgrade`, the seeders and `scenario_seed apply` / `verify`;
- a live API or browser session;
- real-device camera and GPS;
- multi-worker tests.

**Why:** no isolated test database is approved, and the configured database must not be written to.

---

## 7. Summary and next steps

**What changed:** between 18 and 27 October 2026, `master` gained:
- security hardening;
- OCR and verification improvements, with seven distinct outcomes and accident-date validity shown to officers;
- the customer document rules: required copies, non-retained identity copies and camera-only photos in the portal;
- the floating dock;
- the complete server-enforced Surveyor workflow, with the secure Claim Documents viewer.

**What is incomplete:** see Section 4 and the handoff's Section 12. Of these, the most important are:
- the server-side camera rule for customers;
- IST and assignment dates;
- running the database-backed tests on an isolated database;
- the deferred database storage for capture and correction records.

**Recommended next steps:**
1. Get approval for an isolated test database and run the database-backed suite.
2. Close handoff items A1, A3 and A5.
3. Decide which dataset copy is canonical before any dataset work.

**What this document does not claim:** that any uncommitted change listed in Section 5 was committed or pushed.
