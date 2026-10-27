# CI-MICOP — Project Handoff

**Repository state described:** `master` at `665a256` ("feat(surveyor): secure claim document viewing"). `origin/master` is the same commit (0 ahead, 0 behind on 27 October 2026).

**How this document was prepared:**
- **Sources:** the code, Git history and existing documentation on `master`. Each claim below cites a file, endpoint or commit.
- **Test results:** the tests in Section 10 were run while this document was written. Results from earlier reports are labelled as such.
- **No database access:** nothing was queried, and no migration, seeder or database-backed test was run to prepare this document.
- **Working tree differs from `master`:** it contains uncommitted work, which is listed in Section 14. Wherever the two differ, this document describes committed `master`.

**Status words used here:**
- **Implemented:** the code exists on `master` and database-free tests exercise it.
- **Implemented, not verified end to end:** the same, but never run against a real database, browser or device.
- **Partially implemented / Not started / Blocked / Deferred / Needs verification:** these mean what they say. The blocker or the missing evidence is named each time.

---

## 1. Project overview

**Purpose.** CI-MICOP ("Cloud-Native Intelligent Motor Insurance Claims Operations Platform") is a final-year project. It is a web portal for motor insurance claims. The workflow it supports:
1. A customer files a claim and submits documents and accident photos.
2. A claims officer reviews the claim, sees deterministic verification checks, assigns a surveyor and records the final decision.
3. A surveyor inspects the vehicle, records damage and camera-captured evidence, and submits a survey report.

AI/ML research code exists in `ai_ml/`. AI fraud detection is **deferred** (Section 12, item E1).

**Roles** (from `backend/app/api/v1/deps.py` and the routers):

| Role | What it can do (backend-enforced) |
|---|---|
| Customer | Create claims for own vehicles and policies (`POST /claims`); upload documents to own claims (`POST /documents`); read own customer, vehicle, policy, claim and document records |
| Surveyor | Work only on claims with a `surveyor_inspections` row for their Employee_ID (`crud_claim.surveyor_is_assigned`). Record the inspection, damage records and camera evidence; submit the survey report; view permitted claim documents |
| Claims Officer | Read every claim; run the analysis and verification endpoints under `/officer/claims/{id}/...`; assign a surveyor; record the final decision (`POST /officer/claims/{id}/decision`, officer only) |
| Admin | Read every claim; list users (`GET /admin/users`); assign surveyors. Cannot record a decision (`require_claims_officer_employee_id`) or submit a survey report |

**Technology stack.**

| Layer | Technology (versions from `frontend/package.json` and `backend/requirements.txt`) |
|---|---|
| Frontend | React 19, React Router 7, Vite 8, Tailwind CSS 3, Axios, lucide-react; tests with Vitest 3 and Testing Library; lint with oxlint |
| Backend | Python 3.11, FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, psycopg2 |
| Database | PostgreSQL (the README uses version 18 locally) |
| Documents and images | PyMuPDF (PDF text and rendering, and the survey-report PDF), Pillow (image validation), pytesseract with a local Tesseract install (OCR) |
| Auth | JWT (PyJWT) with bcrypt password hashing; login throttling (`services/login_throttle.py`) |

**Architecture.**
- A React single-page app (`frontend/`) talks to a FastAPI REST API (`backend/`, routes under `/api/v1`).
- The API uses PostgreSQL through SQLAlchemy.
- Uploaded files are stored on the local filesystem under `infra/storage/`, never in the database.
- `infra/docker/docker-compose.yml` is an empty placeholder: there is no committed Docker setup for the app.

**Current state, in short:**
- **Implemented:**
  - Customer, surveyor and officer workflows exist and are tested with database-free tests.
  - Server-side enforcement exists for the surveyor workflow (schedule, step order, corrections, final submission, evidence separation and document viewing).
- **Not verified:**
  - Nothing has been run end to end against a real database or a real device camera in this period (Section 10).

---

## 2. Repository structure

```
backend/
  app/main.py                  FastAPI app; mounts api_router at settings.API_V1_PREFIX
  app/core/config.py           Settings (names in Section 3)
  app/api/v1/api.py            Router registration
  app/api/v1/deps.py           get_db, get_current_user, require_roles, require_customer_id,
                               require_surveyor_employee_id, require_claims_officer_employee_id
  app/api/v1/routers/          admin, auth, claims, customers, documents, health, officer,
                               policies, surveyor, vehicles
  app/db_models/               SQLAlchemy models (15 tables; see Section 9)
  app/crud/                    Per-table queries
  app/schemas/                 Pydantic request/response schemas
  app/services/                Business rules (one module per concern; see below)
  alembic/versions/            One migration: 0eb88898ddd4_create_15_table_ci_micop_schema.py
  tests/                       pytest suites (Section 10)
  seed_dev_data.py             Development seed (writes to the configured database)
  scenario_seed/               Dataset work: UNCOMMITTED on master (Section 14)
frontend/
  src/routes/AppRoutes.jsx     All routes, per role
  src/routes/navConfig.js      Dock / account-menu items per role
  src/layouts/AppShell.jsx     Header + floating dock (components/common/FloatingDock.jsx)
  src/pages/{customer,surveyor,officer,admin}/
  src/components/{common,customer,surveyor,officer,camera}/
  src/services/*.js            API clients (apiClient.js adds the bearer token)
database/schema.sql            Raw SQL equivalent of the 15-table schema
database/seed_data/            Seed material
ai_ml/                         Standalone research code (separate venv; not imported by the API)
infra/storage/documents/       Stored customer documents (git-ignored)
infra/storage/evidence/        Surveyor photos, capture records, correction state (git-ignored)
docs/project_documentation/    Per-feature reports (for example SURVEYOR_INSPECTION_WORKFLOW.md)
```

**Key backend services:**

| Concern | Module(s) |
|---|---|
| Claim access (RBAC) | `claim_access.py` (`get_claim_or_403`, `get_claim_assigned_to_surveyor_or_403`) |
| Claim creation | `claim_creation.py` |
| Customer documents | `document_upload.py`, `document_storage.py`, `claim_copy_retention.py` |
| OCR, extraction and completeness | `document_analysis.py`, `entity_extraction.py`, `document_fields.py` |
| Verification checks | `document_consistency.py`, `accident_consistency.py`, `document_validity.py`, `policy_cover.py`, `verification_outcome.py`, `semantic_consistency.py` |
| Photo checks | `claim_photos.py`, `evidence_duplication.py`, `evidence_quality.py` |
| Surveyor workflow | `surveyor_assignment.py`, `inspection_creation.py`, `surveyor_workflow.py`, `workflow_state.py`, `vehicle_damage_creation.py`, `evidence_upload.py`, `evidence_capture.py`, `evidence_storage.py` |
| Survey report | `survey_report.py`, `survey_report_pdf.py` |
| Surveyor document viewer | `surveyor_documents.py` |
| Officer decision | `claim_decision.py`; AI read-outs in `ai_analysis.py`, `ai_pipeline.py`, `risk_fusion_artifacts.py` |
| Repair estimates | `repair_estimate_creation.py`, `repair_estimate_checks.py` |

**File storage:**
- **Customer documents:** `DOCUMENT_STORAGE_ROOT/<Claim_ID>/<Document_ID>_<safe_name>` (`document_storage.storage_path_for`).
- **Surveyor photos:** `EVIDENCE_STORAGE_ROOT/<Claim_ID>/<Evidence_ID>_<safe_name>`.
- **Capture records:** each surveyor photo has one next to it, `<photo>.capture.json` (`evidence_capture.metadata_path_for`).
- **Correction state:** per inspection, at `EVIDENCE_STORAGE_ROOT/<Claim_ID>/<Inspection_ID>.workflow.json` (`workflow_state._path_for`).
- **Defaults:** both roots default to `infra/storage/documents` and `infra/storage/evidence`. Both are git-ignored.

---

## 3. Setup and local development

The setup steps are in `README.md`, sections "Frontend Setup" and "Backend Setup". The table below says which steps were verified while preparing this document.

| Step | Command | Verified in this task? |
|---|---|---|
| Backend virtual environment | `cd backend`, `python -m venv venv`, `venv\Scripts\activate`, `pip install -r requirements.txt` | The existing `backend/venv` (Python 3.11.9) was used; installation was not re-run |
| Migrations | `alembic upgrade head` | **Not run.** It changes the configured database |
| Start the API | `uvicorn app.main:app --reload` (port 8000) | Not run. `import app.main` succeeds as part of the test runs |
| Health check | `GET /api/v1/health` | Not run (only `tests/test_health.py`, database-free, passed) |
| Frontend install and dev server | `cd frontend`, `npm install`, `npm run dev` (port 5173) | Not run; the dev server was not started |
| Frontend tests, lint and build | `npm test`, `npm run lint`, `npm run build` | **Run** (Section 10) |
| Development data | `python seed_dev_data.py` | **Not run.** It writes to the database. Its dev accounts are listed in `README.md`; never use them outside development |

**Environment variables.** Names only; never commit or print the values.
- **`backend/.env`** (template `backend/.env.example`). The full set read by `backend/app/core/config.py`:
  - `PROJECT_NAME`, `ENVIRONMENT`, `API_V1_PREFIX`, `BACKEND_CORS_ORIGINS`
  - `DATABASE_URL`
  - `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
  - `LOGIN_MAX_FAILED_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`
  - `DOCUMENT_STORAGE_ROOT`, `DOCUMENT_MAX_UPLOAD_BYTES`, `EVIDENCE_STORAGE_ROOT`, `EVIDENCE_MAX_UPLOAD_BYTES`
  - `TESSERACT_CMD`
  - `RISK_FUSION_ARTIFACTS_ROOT`
  - The template lists only six of them: `ENVIRONMENT`, `BACKEND_CORS_ORIGINS`, `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **`frontend/.env`** (template `frontend/.env.example`): `VITE_API_BASE_URL`.
- **Root `.env.example`:** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`. Nothing in the committed code reads these; they are a template only.

**Tesseract OCR.**
- **Which documents need it:** scanned or photographed documents. Text-based PDFs are read with PyMuPDF and don't need it.
- **Configuration:** set `TESSERACT_CMD` in `backend/.env`.
- **Current machine:** the two backend tests for the "Tesseract missing" case skip themselves, so Tesseract is available here.
- **Without Tesseract:** scanned pages are reported as unavailable instead of failing.

**Troubleshooting:**
- **Database tests error with `fixture 'client' not found`.** This is expected under `--noconftest` (Section 10). Don't "fix" it by pointing the tests at a database.
- **`test_scenario_seed_dataset.py` fails to import.** This is a known issue with the uncommitted dataset work (Section 11, L12). It is not an application failure.
- **Login refused after several bad passwords.** The lockout is held in memory (`login_throttle.py`). It clears when the API restarts or after `LOGIN_LOCKOUT_MINUTES`.
- **A Surveyor step is locked.** Check the inspection date first: steps open at 00:00 IST on `Inspection_Date` (Section 6).

---

## 4. System architecture and workflows

**End-to-end flow, as implemented:**
1. **Claim creation (customer).** `POST /claims` (`claim_creation.py`):
   - The vehicle and policy must belong to the customer.
   - The claim is created with `Claim_Status="Under Review"`, `Final_Decision="Pending"`, and an accident row.
2. **Document submission (customer).** `POST /documents` (`document_upload.py`). The allow-listed types are `fir_copy`, `driving_licence`, `rc_book`, `insurance_policy`, `repair_estimate`, `accident_photos` and `survey_report`.
   - **Content checks:** the content type is detected from the bytes (PDF/JPEG/PNG), with a 10 MB default limit. Accident photos must be JPEG or PNG.
   - **RC, licence and policy copies are not stored** (`claim_copy_retention.NOT_RETAINED_DOCUMENT_TYPES`). They are read in memory; only a reduced verification record, the label-and-value spans, is kept in `Document.Extracted_Text`, and the row has a neutral name such as `rc-copy.pdf`.
   - **Other types are stored as files.**
3. **Verification (officer).** These are read-time checks under `/officer/claims/{id}/...` (Section 7). They compare values extracted from the customer's copies with **structured insurer records**: the `vehicles`, `policies` and `accidents` tables. No insurer-held document copies exist to compare against.
4. **Surveyor assignment (officer or admin).** `POST /officer/claims/{id}/assign-surveyor` creates the claim's first `surveyor_inspections` row (`surveyor_assignment.py`).
   - That row **is** the assignment; there is no separate assignment table.
   - Any active (unsubmitted) inspection on the claim blocks a second assignment with 409.
5. **Inspection, damage and evidence (surveyor).** The Section 6 workflow. Every write is checked by `surveyor_workflow.py`.
6. **Survey report.** Submitting it is `PATCH /surveyor/inspections/{id}` with `Survey_Report_Submitted=true`. After that the inspection, damage records and evidence can no longer change.
7. **Decision (officer).** `POST /officer/claims/{id}/decision` (`claim_decision.py`) writes `claim_decision_audit` and the claim's decision fields. It is the only code that records a decision; no check or AI output decides anything.

**Customer documents vs insurer reference data:**
- **Customer documents:** customer-provided documents are `documents` rows.
- **Insurer data:** insurer-held data exists only as structured columns, such as `vehicles.Registration_Number` and `policies.Policy_Number` and their dates.
- **No reference-document store:** there is no insurer licence record. So a licence-number comparison always returns `REFERENCE_UNAVAILABLE` (`document_validity.py`).
- **Not a document comparison:** an identifier match proves that the number printed on the copy equals the insurer's structured value. It does not prove that the copy is genuine or matches an insurer-held copy.

**Authentication and RBAC.**
- **Tokens:** `POST /auth/login` issues a JWT. `get_current_user` validates it on every request, and `require_roles` / `require_*_id` restrict endpoints by role.
- **Claim-scoped data:** goes through `claim_access.get_claim_or_403`. Customers see only their own claims, surveyors only assigned claims, and officers and admins all claims.
- **Not-found answers:** for document reads, a document on an inaccessible claim gets the same 404 as a missing one (`routers/documents.py`, `_get_visible_document_or_404`).

---

## 5. Customer portal

- **Navigation (`navConfig.js`):**
  - Dock: Home, Claims, Docs, Policies.
  - Account menu: Profile, Support.
  - Hidden but routed: Notifications. Settings is hidden too and falls through to `ComingSoonPage`.
- **Claim creation (`pages/customer/NewClaimPage.jsx`):**
  - A four-step form: incident, vehicle and policy, documents, review.
  - Documents upload one by one after the claim is created, with per-file retry.
- **Document groups (`components/customer/documentCategories.js`, published in `04567e2`):**
  - "Required with every claim": the driving licence of whoever was driving, the RC and the insurance policy (`REQUIRED_COPY_KEYS`). The page explains that each copy is read for the check and not kept.
  - "Accident photos": camera only, up to `MAX_ACCIDENT_PHOTOS` = 10. Photos are scaled to at most 1920 px and saved as JPEG at quality 0.85 (`AccidentPhotoCapture.jsx`).
  - "Other claim evidence": FIR, repair estimate and survey report.
- **Validation:**
  - Frontend: required copies are checked before submit (`missingRequiredCopies`), and the accepted files are `.pdf,.jpg,.jpeg,.png` up to 10 MB.
  - Backend: it re-checks type, size and content. **It does not require** the RC, licence and policy copies at claim creation. Completeness is computed afterwards: `document_analysis._BASE_REQUIRED_DOCUMENT_TYPES` = RC, Driving Licence and Insurance Policy, plus extra types per claim type.
- **Camera-only accident photos.** `AccidentPhotoCapture.jsx` has no file input, gallery or drag-and-drop.
  - **Backend gap:** the server only checks that an accident photo is a JPEG or PNG. **Camera-only is enforced in the browser, not on the server**, so a direct API call can upload a gallery image (Section 11, L2).
- **Verification status:**
  - Customers see `Document_Status` and `Verification_Status` on the claim details and timeline pages, and `Document_Status` on the Documents page.
  - Uploading never sets "Verified". `Verification_Status` stays `Pending` until it is changed by a process that does not exist yet (Section 12, D2).
- **Support FAQ (`pages/customer/SupportPage.jsx` as committed):** it covers filing a claim, checking claim status, where to upload, what to submit, why to upload RC, licence and policy copies again, why photos can't come from the gallery, uploading not meaning verification, and missing or mismatched records.
  - **Working-tree draft is not current:** an older draft of this page is uncommitted in the working tree. It is **not** the current implementation and must not be published (Section 14).
- **Claim status:** set to "Under Review" at creation; the decision endpoint does not change `Claim_Status` (`claim_decision.py`). Customer-visible status therefore does not move with the officer's decision (Section 12, D3).

---

## 6. Surveyor portal

**Navigation:**
- **Dock:** Home (`/surveyor`), Inspections (`/surveyor/claims`, active inspections) and Survey Reports (`/surveyor/history`, submitted reports).
- **Account menu:** Profile and Support.
- **Hidden but routed:** Notifications; the header bell covers it.

**Workflow:** Claim Details → Inspection → Vehicle Damage → Evidence → Survey Report (`components/surveyor/claimSteps.js`).

**Server rules (`backend/app/services/surveyor_workflow.py`).** Each rule below is enforced on the server; the frontend only displays the server's `workflow` summary from `GET /surveyor/claims/{id}`.

| Rule | Backend enforcement | Frontend |
|---|---|---|
| Assignment | `surveyor_is_assigned` on every surveyor endpoint; 403 or 404 otherwise | Lists only `GET /surveyor/active-inspections` |
| Schedule | Writes are refused with 409 before 00:00 IST on `Inspection_Date` (`assert_inspection_writable`, `schedule_reached`), using an explicit UTC+05:30 clock, whatever the server's time zone | Next disabled, with the message "This inspection will become available on <date> (India Standard Time)"; unlocks on time without a reload (`useScheduleReached`, corrected by the server clock) |
| Claim Details is read-only | No write endpoint exists for it | No inputs |
| Step order | Damage needs the Inspection step complete; Evidence needs Inspection, plus a damage record when damage was observed (`require_writable_step`) | Later tabs locked |
| Inspection fields | Final values required for submission; "Pending" placeholders rejected (`incomplete_inspection_fields`) | Form validation |
| Correction mode | A completed step with later saved work is locked. Changing it needs `POST /surveyor/inspections/{id}/corrections` (own inspection, assigned, before submission, after the schedule), recorded in `workflow_state.py` with an audit history | "Correct this step" only opens after the server confirms |
| Submission | Re-checks the fields, a damage record (if damage was observed), at least one verified surveyor capture with a usable location, and no open correction; 409 or 503 otherwise | Confirmation dialog |
| Finality | Every write path refuses changes once `Survey_Report_Submitted` is set, for every role including Admin | Read-only views |

**Vehicle damage:**
- `POST /surveyor/vehicle-damage` adds a record per damaged part. `Vehicle_ID` is taken from the claim.
- Records belong to the **claim**: `vehicle_damage` has no `Inspection_ID` (Section 11, L6).

**Surveyor evidence (camera only):**
- **Capture:**
  - `POST /surveyor/evidence/capture` takes a photo from the in-app camera (`components/camera/CameraView.jsx`), its evidence type and evidence date, and the device's reported capture time and location.
  - The four evidence types are Vehicle Damage Close-up, Overall Vehicle Condition, Damage Location and Extent, and Accident Scene / Surroundings.
- **Retired upload:** the old file upload, `POST /surveyor/evidence`, answers 410; no server code behind it remains.
- **Image endpoint:** `GET /surveyor/evidence/{id}/image` serves only the surveyor's own verified captures.

**Capture records** (`evidence_capture.py`): a JSON file next to each photo.
- **Server-established fields:** role, surveyor, claim, inspection and evidence IDs, receipt time, image format, size, dimensions and SHA-256.
- **Client-reported fields:** capture time, latitude, longitude, accuracy, and any location error.
- **Checks:** whether the location was usable (`MAX_LOCATION_ACCURACY_M` = 100 m) and whether the device clock was plausible (within 10 minutes of receipt).
- **Fail closed:** a record is only accepted if it is well-formed, names the same claim and row, has `Evidence_Source="Surveyor"`, and its hash and size still match the photo. Anything else is treated as "not a verified capture".

**Customer and surveyor separation:**
- **Customer photos never count as surveyor evidence:** these are "Accident Photos" documents, plus dataset or legacy evidence rows marked `Customer`.
- **Not in surveyor views:** they never appear in the surveyor's evidence list, report or PDF.
- **Hidden from surveyors everywhere:** surveyors cannot list, read or analyze accident-photo documents (404).
- **Officer photo checks:** the duplicate and quality checks (`claim_photos.py`) read both kinds of photo and keep a source label on each.

**Survey report:**
- **Endpoints:**
  - `GET /surveyor/claims/{id}/report` and `/report.pdf`: a draft once the workflow is complete, or the submitted report.
  - `GET /surveyor/survey-reports/{inspection_id}/report` and `/report.pdf`: the history.
- **Single source:** the JSON and the PDF come from the same dict (`survey_report._build`), so they cannot disagree.
- **Built live:** reports are rebuilt from current data on every request. There is no stored snapshot (Section 11, L5).
- **Older submissions:** a submitted report whose saved records fail today's rules shows a `submission_review` notice in the workflow summary, report view, PDF and Evidence page. It is never rewritten.

**History:**
- `GET /surveyor/survey-reports` lists submitted inspections; `GET /surveyor/active-inspections` lists unsubmitted ones.
- The Survey Reports page offers View Document and Download Document (the PDF).

**Claim Documents viewer:** see Section 8.

---

## 7. Officer portal and verification

- **Pages (`frontend/src/pages/officer/`):**
  - Working: dashboard, work queue, all claims, search.
  - Per claim: details with surveyor assignment, document consistency, evidence checks, estimate analysis, fraud risk and AI insights (research read-outs), and the decision page.
  - Placeholders: several dock and menu entries (`assign-surveyor`, `track`, top-level `fraud-risk`, `ai-insights`, `document-consistency`, `estimate-analysis`, `decision`) have no top-level route and fall through to `ComingSoonPage`. The per-claim pages exist.
- **Analysis endpoints:** all are `POST` and run at read time.
  - `/officer/claims/{id}/documents/analyze`: OCR plus completeness, which is persisted to `Document_Completeness`.
  - `/documents/semantic-consistency`: identifier, accident-detail and validity checks, plus a narrative research prototype.
  - `/evidence/duplication-check`, `/evidence/quality-check`, `/repair-estimates/check`.
- **Outcomes** (`backend/app/services/verification_outcome.py`; labels from `components/officer/ConsistencyFindingsPanel.jsx`):

| Outcome code | Officer label | Meaning |
|---|---|---|
| `VERIFIED` | Verified | The check ran and the available evidence supports it |
| `MISMATCH` | Mismatch | A reliable comparison ran and the values conflict |
| `NOT_SUBMITTED` | Not submitted | The customer did not upload the document the check needs |
| `REFERENCE_UNAVAILABLE` | No insurer record | The insurer-held record to compare with does not exist |
| `INVALID_OR_EXPIRED` | Invalid / expired | The document fails a validity rule on the relevant date |
| `VERIFICATION_UNAVAILABLE` | Could not check | No text was extracted, OCR is unavailable, or the capability isn't implemented |
| `INCONCLUSIVE` | Inconclusive | The check ran, but the evidence supports no conclusion |

The older `status` values `MATCH`, `MISMATCH` and `UNAVAILABLE` are kept alongside these.

- **Accident-date validity (`document_validity.py`, `policy_cover.py`):**
  - Policy cover on the accident date comes from the policy record's single period.
  - RC validity comes from the date printed on the submitted copy. There is no insurer RC validity field or registry.
  - Licence validity, vehicle class (LMV or MCWG only) and number come from the submitted copy.
  - A missing date gives `INCONCLUSIVE` and an unreadable copy `VERIFICATION_UNAVAILABLE`; neither is ever reported as `VERIFIED`.
- **Not persisted:** outcomes are calculated per request and not saved (Section 12, B4).
- **Decision:** only the officer decides (`claim_decision.py`). AI signals are supporting information only.

---

## 8. Secure document viewing (Surveyor Claim Documents)

**Endpoints:**
- `GET /api/v1/surveyor/claims/{claim_id}/documents` gives the panel's list.
- `GET /api/v1/surveyor/claims/{claim_id}/documents/{document_id}/content` serves one document.
- The code is in `backend/app/services/surveyor_documents.py`, `routers/surveyor.py` and `frontend/src/components/surveyor/ClaimDocumentsPanel.jsx`.

**Checks on every request, all on the server:**
1. A valid JWT; otherwise 401.
2. The Surveyor role (`require_surveyor_employee_id`); Customer, Claims Officer and Admin get 403.
3. The claim exists **and** is assigned to this surveyor. Otherwise the answer is the same 404, "Claim not found", in both cases, so the existence of other claims isn't disclosed.
4. The scheduled date has been reached: 00:00 IST on the surveyor's `Inspection_Date`, using the same function as the workflow. Before that the answer is 409 with "Customer documents become available on the scheduled inspection date, <date> (India Standard Time)."
5. The document's `Claim_ID` equals the claim in the URL, re-checked even in the list. Its type must not be `Accident Photos`. Otherwise 404, "Document not found".
6. The file path is re-derived from the database row with `document_storage.storage_path_for`. That function cleans up the names and refuses paths outside the storage root, so no client-supplied path is ever used.
7. The file's first bytes must be a PDF, JPEG or PNG. Otherwise 415, "cannot be previewed"; the content is never sent.

**Response headers:**
- `Content-Disposition: inline; filename="claim-document.<ext>"`, a neutral name.
- `Cache-Control: no-store` and `Pragma: no-cache`.
- `X-Content-Type-Options: nosniff`.
- A restrictive `Content-Security-Policy` with `sandbox`.

There is no download button, and no public URL: the frontend fetches a Blob with the bearer token and shows it from memory.

**Statuses** (`availability`):

| Status | Meaning |
|---|---|
| Available | A file is retained and can be previewed |
| Not uploaded | No document of that type exists (shown for RC, Driving Licence, Insurance Policy, FIR and Repair Estimate) |
| Copy not kept | RC, licence or policy: only the verification record exists. There is no file **by design** (`claim_copy_retention.py`) |
| Unavailable | The row exists but the file is missing |
| Cannot be previewed | The stored bytes are not a PDF, JPEG or PNG |

**Viewing rules:**
- **Verification status:** shown as recorded. Opening a document **never** marks it verified.
- **Repeat viewing:** there is no view count or one-time link, and every request is re-authorized. A removed assignment stops access on the very next request.
- **After submission:** viewing stays allowed, read-only. Viewing never writes to documents, evidence or inspection records.
- **Audit:** each successful view logs `surveyor_document_view surveyor=… claim=… document=… at=…` to the `ci_micop.audit.document_access` logger, never the content. This is **application-log only**; no audit table exists for it (Section 11, L4).

**Practical consequence:** because the RC, licence and policy files are never stored, a surveyor can see that these copies exist and their verification status, but can never open them.

---

## 9. Database, persistence and data safety

- **Schema:**
  - There is one Alembic migration, `0eb88898ddd4`, for 15 tables, mirrored in `database/schema.sql`.
  - The tables: `accidents`, `authentication_users`, `claim_decision_audit`, `claims`, `cross_document_consistency`, `customers`, `documents`, `evidence`, `fraud_risk_analysis`, `policies`, `repair_estimates`, `surveyor_inspections`, `tp_claims`, `vehicle_damage`, `vehicles`.
  - No schema change was made during this period.
- **Relationships that matter:**
  - `claims` link to the customer, vehicle and policy.
  - `documents`, `evidence`, `vehicle_damage`, `repair_estimates` and `surveyor_inspections` link to `claims` only. None of them link to an inspection, and none has uploader or provenance columns.
  - Assignment is the existence of a `surveyor_inspections` row.
- **Kept on disk:**
  - Customer document files and surveyor photos.
  - The surveyor **capture records** (JSON).
  - The per-inspection **correction state** (JSON).
  - All of it lives under the storage roots: on the server's disk, with no database transaction around it (Section 11, L1).
- **Seed data:**
  - `seed_dev_data.py` creates the `DEV-*` development rows. It is idempotent, but it **writes to the configured database**.
  - The 20-scenario dataset (`backend/scenario_seed/`) is **uncommitted** and not part of `master`.
  - `README.md` warns that database tests use the configured database.
- **Safety rules for whoever continues:**
  - Do not run `alembic upgrade`, `seed_dev_data.py`, `scenario_seed apply` / `verify`, or the database-backed tests against the development database without explicit approval.
  - Do not create claims or customers, and do not edit existing records.
  - Treat submitted reports as immutable historical records.

---

## 10. Tests and verification

**Run while preparing this document (27 October 2026, working tree on `master` `665a256`):**

| Command | Result |
|---|---|
| `cd frontend && npm test` | **300 passed (39 files).** Note: the working tree contains the uncommitted older FAQ draft and its own 2-test file. The committed test file has 3 tests; 301 passed when `665a256` was made (earlier report, not re-run here) |
| `npm run lint` | 0 errors, 3 warnings (existing: `AuthContext.jsx` ×2, `InspectionWorkspacePage.jsx`) |
| `npm run build` | Succeeds (the existing chunk-size warning remains) |
| `pytest --noconftest` on `backend/tests` with a guard plugin that makes any database connection fail, excluding `test_scenario_seed_dataset.py` | **402 passed, 2 skipped, 0 failed, 0 database connection attempts.** 526 **not run**: they error at setup because the database fixtures (`client` 525, `seed_data` 1) aren't loaded under `--noconftest` |
| Same, for `tests/test_scenario_seed_dataset.py` (uncommitted) | **Collection error**: `ImportError: cannot import name 'EVIDENCE_SOURCE_VALUES' from 'app.services.evidence_upload'` (Section 11, L12) |

**Skipped tests:** the 2 skips are the "Tesseract not installed" cases, which skip because Tesseract is installed.

**Not run — needs a database:** all database-backed suites, including:
- surveyor and evidence: `test_evidence.py`, `test_survey_report.py`, `test_surveyor_inspection.py`, `test_vehicle_damage.py`, `test_surveyor_assignment.py`;
- documents and claims: `test_document_upload.py`, `test_document_analysis.py`, `test_claim_creation.py`, `test_claim_decision.py`;
- security: `test_rbac.py`, `test_auth.py`, `test_security_regression.py`;
- the database-dependent cases in `test_evidence_duplication.py`, `test_evidence_quality.py` and `test_live_signal_integration.py`.

**Why they weren't run:** `tests/conftest.py` uses `SessionLocal`, which connects to the configured `DATABASE_URL`, and the fixtures insert and delete `TEST-*` rows. No isolated test database has been approved.

**Updated but never run:** `665a256` changed several of these suites for the new rules: 404 answers, camera-capture fixtures, and evidence stored through the capture endpoint. They have **not been executed**.

**What tests mock:** the frontend tests mock the camera (`getUserMedia`), geolocation, canvas and video. Database-free backend tests replace the crud layer with an in-memory store. Neither proves real device behaviour or database persistence.

---

## 11. Known limitations and technical debt

Each item was checked against the current code.

- **L1 — Capture records and correction state are JSON files.**
  - *What exists:* writes are atomic (temp file plus rename), capture records are write-once, and a corrupt correction file is never overwritten and blocks corrections and submission (`workflow_state.py`, `evidence_capture.py`).
  - *The limitation:* there is no transaction shared with PostgreSQL, and anyone with access to the server's disk can change these files. Changes to photos and records are detected; changes to correction state are not.
- **L2 — Customer camera-only rule is frontend-only.** `document_upload.py` accepts any JPEG or PNG as `accident_photos`.
- **L3 — Concurrency.** The correction-state lock (`threading.RLock`) and the login throttle are per process. With several API workers, writes and lockout counts aren't coordinated.
- **L4 — Auditing.**
  - Document views go to the application log only (`ci_micop.audit.document_access`).
  - Correction events are in the JSON audit history only.
  - `claim_decision_audit` covers officer decisions only.
- **L5 — Reports are rebuilt live.** Submitted reports have no stored snapshot. If underlying rows change (for example damage records on the claim), the report view changes. Historical reports that predate the current rules (for example `DEV-INSP-001`, created as submitted by `seed_dev_data.py`) are flagged by `submission_review`, not re-verified.
- **L6 — No inspection link on damage and evidence.**
  - Damage records are per claim, so a re-inspection sees and counts earlier inspections' damage records.
  - Evidence carries its inspection only in the capture record.
- **L7 — Date-only scheduling.**
  - The schedule opens at 00:00 IST on the date; there are no appointment times.
  - Assignment always sets `Inspection_Date` to the assignment day (`surveyor_assignment.py`, `date.today()`), so no future date can be scheduled through the app.
  - That `date.today()` uses the server's local date, while the workflow uses IST (`today_ist`). `claim_creation.py`, `document_upload.py` and `claim_decision.py` also use the server's local date.
- **L8 — Copies are not retained.** RC, licence and policy files are never stored, so they can't be viewed or re-OCR'd later.
- **L9 — Device authenticity.**
  - Browser camera access, GPS, accuracy and timestamps are reported by the client and can be spoofed.
  - A capture proves only that the photo came through the capture endpoint; it does not prove where or when it was taken.
  - No real-device testing has been recorded.
- **L10 — Insurer references are limited.**
  - There is no reference-document store and no licence records, and only one policy period is recorded.
  - Several checks can only use the customer's copy, or return `REFERENCE_UNAVAILABLE`.
- **L11 — No isolated test database.** The database-backed suites can only run against the configured database, which has not been approved.
- **L12 — The uncommitted dataset doesn't load.** `backend/scenario_seed/checks.py` imports `EVIDENCE_SOURCE_VALUES`, which `665a256` removed from `app/services/evidence_upload.py`. `test_scenario_seed_dataset.py` therefore fails at import.
- **L13 — Customers can upload a "Survey Report".** The narrative check in `semantic_consistency.py` compares the FIR with a document of type "Survey Report", and customers can upload that type (`ALLOWED_DOCUMENT_TYPES`). The surveyor's own submitted report (`survey_report.py`) is not a document row, so the check doesn't use it. This is flagged in `docs/CI_MICOP_CORRECTIVE_IMPLEMENTATION_PROMPT.md` (item 2.9).
- **L14 — Placeholder pages.** Several officer and customer menu entries open `ComingSoonPage` (Section 7). Customer support requests and notifications have no backend.
- **L15 — Surveyor repair-estimate endpoint without a UI.** `POST /surveyor/repair-estimates` still exists, but the surveyor Repair Estimate page was removed in `665a256`.
- **L16 — `.env.example` is incomplete.** The template lists 6 of the 16 settings.

---

## 12. Future implementations and outstanding work

Priorities: **Critical** means a security or data-integrity risk; **High** means needed for a correct workflow; **Medium** improves quality or completeness; **Low** is optional.

**Approval:** every item that may change the schema or data needs explicit approval first. None of these items is approved yet.

### A. Required follow-up work

**A1 — Enforce customer camera-only capture on the server**
- **Status:** Partially implemented.
- **Exists:** the camera-only UI (`AccidentPhotoCapture.jsx`); the backend checks JPEG/PNG only (`document_upload.py`).
- **Missing:** a server-side signal that a photo came from the in-app capture flow. Today a direct `POST /documents` call can upload any image.
- **Why it matters:** "camera-only" is a stated requirement; today it is only a UI convention.
- **Next steps:**
  1. Agree what the server can realistically enforce. It can prove "this came through the capture endpoint", not authenticity.
  2. Add a capture endpoint, or capture metadata, for customer photos, mirroring the surveyor's `evidence_capture.py`.
  3. Reject `accident_photos` on the generic upload.
  4. Update the customer client.
- **Dependencies:** product decision; frontend change.
- **Schema:** not required if records stay on disk; provenance columns would be (see B1).
- **Relevant:** `services/document_upload.py`, `routers/documents.py`, `components/customer/AccidentPhotoCapture.jsx`, `tests/test_document_upload.py`, `tests/test_claim_photos.py`.
- **Acceptance:** a direct API upload of `accident_photos` without the capture flow is refused (tested); camera captures still work; existing photos stay readable.
- **Priority:** High.
- **Precautions:** never relabel or delete existing customer photos.

**A2 — Fix the dataset's import of a removed application name**
- **Status:** Blocked (needs a separate, approved dataset task).
- **Exists:** `scenario_seed/checks.py` line 38 imports `EVIDENCE_SOURCE_VALUES`.
- **Missing:** a fix in the dataset code: define the allowed sources locally, or read them from a stable place. Do **not** restore the application symbol.
- **Why it matters:** the dataset's offline validation and its tests can't run.
- **Next steps:**
  1. Decide which dataset copy is canonical: the uncommitted working tree (24 Oct) or the `delivery/claim-verification-corrections` branch (26 Oct).
  2. Fix the import there and run `python -m scenario_seed check` and `pytest --noconftest tests/test_scenario_seed_dataset.py`.
- **Dependencies:** the user's decision.
- **Schema:** no.
- **Acceptance:** the dataset test collects and passes, and `backend/app` still never imports `scenario_seed`.
- **Priority:** Medium.
- **Precautions:** never run `scenario_seed apply` or `verify` against the development database.

**A3 — Make scheduling dates consistent (IST)**
- **Status:** Not started.
- **Exists:** IST in the workflow (`surveyor_workflow.today_ist`).
- **Missing:** `surveyor_assignment.py` (and claim creation, document submission and decisions) use `date.today()`.
- **Why it matters:** a server not on IST can set the date to the previous or next day, which shifts the inspection unlock.
- **Next steps:** use `surveyor_workflow.today_ist()` in assignment, and decide for the other three; add tests at the IST and UTC day boundary.
- **Dependencies:** none.
- **Schema:** no.
- **Acceptance:** an assignment made at 23:30 UTC records the next IST date (tested).
- **Priority:** Medium.
- **Precautions:** don't change the date-only scheduling model itself without approval.

**A4 — Let officers choose the scheduled inspection date**
- **Status:** Not started; needs a requirement decision.
- **Exists:** assignment always uses today's date; the schedule lock exists.
- **Missing:** an input for a future `Inspection_Date` on assignment, if the business wants scheduling.
- **Why it matters:** without it the schedule lock has no effect for new assignments.
- **Next steps:**
  1. Confirm the requirement.
  2. Add an optional date to `AssignSurveyorRequest`, validated as today or later in IST.
  3. Add it to the officer assignment UI.
- **Dependencies:** A3.
- **Schema:** no; it uses the existing date column. Adding a time would need approval.
- **Relevant:** `routers/officer.py` (`assign-surveyor`), `services/surveyor_assignment.py`, `pages/officer/ClaimDetailsPage.jsx`.
- **Acceptance:** an assigned future date locks the surveyor's steps until 00:00 IST that day (tested).
- **Priority:** Medium.

**A5 — Decide the fate of the surveyor repair-estimate endpoint**
- **Status:** Needs verification.
- **Exists:** `POST /surveyor/repair-estimates` is still live and tested; its page was removed.
- **Missing:** a decision to keep it (and give it a UI or document it) or retire it, as was done with the evidence upload (410).
- **Why it matters:** a live write path with no UI is easy to forget when the workflow rules change. It isn't subject to the schedule or submission locks.
- **Relevant:** `routers/surveyor.py`, `services/repair_estimate_creation.py`, `tests/test_repair_estimate.py`.
- **Acceptance:** the endpoint is either covered by the workflow locks or answers 410.
- **Priority:** Medium.

**A6 — Customer-uploaded "Survey Report" used as the surveyor's narrative**
- **Status:** Not started (flag only).
- **Exists:** customers can upload `survey_report`; the narrative check compares it with the FIR.
- **Missing:** a decision on whether customers may upload survey reports, and whether the check should use the surveyor's own submitted report instead.
- **Why it matters:** a customer-supplied file can be read as if it were the survey report.
- **Schema:** possibly (provenance).
- **Priority:** Medium.
- **Precautions:** existing documents stay unchanged.

### B. Deferred architecture improvements

These are proposals only. **Each needs explicit approval and a migration plan.**

**B1 — Move capture records and correction state into the database**
- **Status:** Deferred.
- **Exists:** JSON files with atomic, write-once handling and fail-closed checks (L1).
- **Missing:** for example a `evidence_captures` table (`Evidence_ID`, `Inspection_ID`, role, surveyor, received time, SHA-256, size, location fields and status, client time and status), and an `inspection_step_corrections` table (`Inspection_ID`, step, opened/closed by and time, reason).
- **Why it matters:** transactional integrity, multi-process safety, and auditability.
- **Next steps:**
  1. Write the schema proposal.
  2. Plan a backfill that reads existing `.capture.json` and `.workflow.json` files without modifying them.
  3. Dual-read during the switch.
- **Dependencies:** approval; isolated test database (C1).
- **Schema:** yes.
- **Relevant:** `evidence_capture.py`, `workflow_state.py`, `surveyor_workflow.py`.
- **Acceptance:** every capture and correction is a row written in the same transaction as its evidence or inspection change; file-only records are still honoured or migrated; no record is lost (verified count before and after).
- **Priority:** High.
- **Precautions:** back up the storage folders first; never delete the JSON files during migration.

**B2 — Link damage records and evidence to an inspection**
- **Status:** Deferred.
- **Missing:** `Inspection_ID` on `vehicle_damage` and `evidence`.
- **Why it matters:** re-inspections currently share the claim's damage records (L6).
- **Schema:** yes.
- **Acceptance:** a second inspection on the same claim starts with no damage records and its report lists only its own.
- **Priority:** Medium.
- **Precautions:** existing rows stay unlinked (nullable column); historical reports are unchanged.

**B3 — Dedicated audit table**
- **Status:** Deferred.
- **Missing:** a table for document views, corrections and submissions.
- **Why it matters:** log-only auditing can be lost and is hard to query (L4).
- **Schema:** yes.
- **Acceptance:** each document view writes one audit row without slowing or blocking the view, and never stores document content.
- **Priority:** Medium.

**B4 — Persist verification outcomes**
- **Status:** Deferred.
- **Exists:** the outcomes are calculated per request (`verification_outcome.py`).
- **Missing:** persisted results with time and inputs, for audit and trend views.
- **Schema:** yes (or reuse `cross_document_consistency`, which needs a design review).
- **Priority:** Low.

**B5 — Insurer reference data**
- **Status:** Blocked: no data and no schema.
- **Missing:**
  - an insurer reference-document store;
  - licence records (number, validity, classes);
  - an RC validity field;
  - separate own-damage and third-party policy periods.
- **Why it matters:** several checks stay `REFERENCE_UNAVAILABLE` or copy-only (L10).
- **Schema:** yes.
- **Relevant:** `document_validity.py`, `policy_cover.py`, `document_consistency.py`.
- **Priority:** Medium.

**B6 — Submitted-report snapshot**
- **Status:** Deferred.
- **Missing:** a stored copy (JSON or PDF) of the report at submission time.
- **Why it matters:** reports are rebuilt live (L5).
- **Schema:** probably (or a write-once file).
- **Acceptance:** after submission, a later change to related rows does not change the submitted report's content.
- **Priority:** Medium.
- **Precautions:** don't backfill a snapshot for old submissions as if it were original; label any such snapshot as reconstructed.

### C. Testing, integration and security verification

**C1 — Isolated test database and a database-backed run**
- **Status:** Blocked (needs approval).
- **Exists:** 526 database-backed tests, several updated in `665a256` but never run.
- **Missing:** a disposable database, confirmed empty and separate from the development data.
- **Next steps:**
  1. With approval, create it.
  2. Point `DATABASE_URL` at it for the test process only.
  3. Run `alembic upgrade head` there.
  4. Run `pytest tests/` and record the results.
- **Schema:** no change (only migrations applied to the new database).
- **Acceptance:** the whole backend suite has run, with recorded pass/fail counts and no change to the development database.
- **Priority:** Critical (it is the only way to verify persistence, cleanup fixtures and real SQL).
- **Precautions:** never point at the development database; confirm the database name before running.

**C2 — Real-device camera and GPS testing**
- **Status:** Not started.
- **Missing:** testing customer capture and surveyor capture on real phones (Android Chrome, iOS Safari), covering permissions, HTTPS, location accuracy, retake/remove and photo limits.
- **Acceptance:** a recorded test sheet per device.
- **Priority:** High.

**C3 — End-to-end run against a running API**
- **Status:** Not started.
- **Missing:** a recorded walk-through, on the isolated database, of login, claim creation, uploads, assignment, the surveyor workflow, document viewing, submission, the PDF and the officer decision.
- **Dependencies:** C1.
- **Priority:** High.

**C4 — Security review of file serving and authorization**
- **Status:** Partially implemented (unit-tested).
- **Exists:** database-free tests for the 404 answers, path traversal, content sniffing, headers and roles.
- **Missing:** a browser check that PDFs render with the CSP sandbox in the target browsers; a review of `GET /documents` list access for surveyors and admins; a check that no endpoint returns storage paths.
- **Priority:** High.

**C5 — Multi-worker behaviour**
- **Status:** Not started.
- **Missing:** a test with several workers for corrections and login throttling (L3).
- **Dependencies:** B1.
- **Priority:** Medium.

### D. Business workflow enhancements

**D1 — Same-damage comparison of customer and surveyor photos**
- **Status:** Not started.
- **Exists:** only reuse fingerprints and quality checks.
- **Missing:** an approved method. It needs a model; the related AI work is deferred, see E1.
- **Priority:** Low (for now).

**D2 — Document verification workflow**
- **Status:** Not started.
- **Exists:** `Verification_Status` stays `Pending`; no code sets it to `Verified` after a human check.
- **Missing:** an officer action that records "verified by whom and when", without inferring it from viewing or from an automated check.
- **Schema:** possibly.
- **Priority:** Medium.

**D3 — Claim status after a decision**
- **Status:** Needs verification (requirement).
- **Exists:** `claim_decision.py` deliberately leaves `Claim_Status` unchanged.
- **Missing:** an agreed mapping from decision to customer-visible status.
- **Priority:** Medium.

**D4 — Placeholder pages**
- **Status:** Not started.
- **Missing:** the officer menu entries that fall through to `ComingSoonPage`, customer support requests and notifications (L14). Remove them or implement them.
- **Priority:** Low.

**D5 — Registry and licensing services (Vahan, Sarathi, DigiLocker)**
- **Status:** Blocked (no authorised integration).
- **Precaution:** checks that need these must keep returning "Could not check" or "No insurer record", never "Verified".
- **Priority:** Low.

### E. Deferred AI work and optional recommendations

**E1 — AI fraud detection**
- **Status:** Deferred.
- **Who:** the user's friend is expected to take over the AI work after 31 October 2026.
- **Exists:**
  - research code in `ai_ml/`;
  - read-only officer views of the research results (`ai_analysis.py`, `risk_fusion_artifacts.py`);
  - a live pipeline (`ai_pipeline.py`) that never computes the fraud score: `fraud_screening_rule_score` is reported as unavailable.
- **Don't implement it as part of other tasks.** AI output must stay a signal for the officer, never a decision.

**E2 — Recommendation: complete `backend/.env.example`** with every setting name, placeholders only (L16). Low.

**E3 — Recommendation: refresh `README.md`.** Its "Current Implementation Status" section stops at Step 3 and calls Docker "added in a later step". Point it to this handoff. Low.

**E4 — Recommendation: code-split the frontend build.** The build warns that a chunk exceeds 500 kB. Low.

---

## 13. Recommended implementation order

1. **Safety and correctness:**
   - C1 (isolated test database, then run the database-backed suite);
   - A1 (server-side customer camera rule);
   - A5 (surveyor repair-estimate write path);
   - A6 (survey-report provenance).
2. **Workflow and data integrity:**
   - A3 (IST dates), then A4 (scheduled date on assignment);
   - D2 (human verification action);
   - D3 (claim status mapping).
3. **Integration verification:**
   - C3 (end to end), C2 (devices), C4 (file-serving review).
4. **Approved persistence improvements:**
   - B1 (capture and correction tables), then C5;
   - B6 (report snapshot), B2 (inspection links), B3 (audit table), B5 (reference data);
   - B4 last.
5. **Dataset task (separate approval):**
   - choose the canonical dataset copy, then A2.
6. **Deferred and optional:**
   - E1 (AI, after 31 October, by the AI owner);
   - D1, D4, D5;
   - E2–E4.

---

## 14. Handover checklist

**What works (database-free tests pass, Section 10):**
- Role-based API access.
- Customer claim and document flow.
- Officer verification outcomes and accident-date checks.
- Surveyor workflow, with server-enforced schedule, order, corrections and finality.
- Camera-only surveyor evidence with verified capture records.
- Survey report, PDF and history.
- Secure Claim Documents viewer.

**Not verified:**
- Any database persistence.
- Database-backed tests.
- A live end-to-end run.
- Real devices.
- Multi-worker behaviour.

**Known blockers:**
- No approved isolated test database (C1).
- No insurer reference data or registry access (B5, D5).
- The dataset import error (A2), pending a choice between the two dataset copies.

**Inspect first:**
- `backend/app/services/surveyor_workflow.py`
- `backend/app/services/surveyor_documents.py`
- `backend/app/services/document_upload.py`
- `backend/app/services/claim_copy_retention.py`
- `backend/app/services/verification_outcome.py`
- `tests/test_survey_report_rules.py`
- `docs/project_documentation/SURVEYOR_INSPECTION_WORKFLOW.md`

**Needs explicit approval:**
- Any schema change or migration.
- Running migrations, seeders or database-backed tests.
- Creating claims or customers, or editing database records.
- Changing the date-only scheduling model.
- Changing `.env`, Tesseract or Docker.
- Publishing the dataset work.

**Uncommitted work in the working tree on 27 October 2026.** Leave it alone unless the owner says otherwise:
- **Dataset:** `backend/scenario_seed/`, `backend/tests/test_scenario_seed_dataset.py`, and the dataset lines in `.gitignore`.
  - A 26 October version of the same work is committed only on the local branch `delivery/claim-verification-corrections`.
  - The original dataset commit `0a67c33` is not reachable from `master`; it is recoverable only through the local reflog.
- **Older customer Support FAQ draft:** `frontend/src/pages/customer/SupportPage.jsx` and its test. It is **older** than the published FAQ, contradicts the required-documents rule, and must not be published.
- **24 October versions of two docs:** `docs/CI_MICOP_CORRECTIVE_IMPLEMENTATION_PROMPT.md` and `docs/CI_MICOP_DATASET_AND_VERIFICATION_ASSESSMENT.md`. They are stale against `master`. Newer versions are on the delivery branch.

**Avoiding damage:**
- Never use `git add .` or `-A`.
- Never reset, clean, stash or force-push.
- Stage files by explicit path.
- Run backend tests with `--noconftest` (and a connection guard) unless an isolated database is approved.
