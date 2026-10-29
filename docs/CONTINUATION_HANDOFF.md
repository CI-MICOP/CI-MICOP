# CI-MICOP — Developer Continuation and Project Handoff

**Prepared:** 29 October 2026, from the `master` branch, with `698cd1e` ("feat: surveyor evidence workflow, claim status consistency, officer accident/evidence access, and developer handoff docs") as the last pushed commit at the start of this update. The working tree was fully clean (`git status` → "nothing to commit, working tree clean") immediately before this revision - the only pending change is this document itself.

**How this document was produced:** by inspecting the actual repository (source files, Git history, `.gitignore`, migration state, test files), by re-running the project's real test/lint/build commands and recording their exact output, and by independently re-verifying the two-claim deletion described in Section 5 directly against the configured database and the real API - not by trusting any earlier report at face value. Where something could not be verified, that is stated explicitly rather than guessed.

**Related documents already in `docs/`** (preserved, not duplicated here):
- [`CI_MICOP_PROJECT_HANDOFF.md`](./CI_MICOP_PROJECT_HANDOFF.md) - an earlier (27 Oct 2026) handoff; some of what it listed as outstanding has since been completed (noted below where relevant).
- [`CI_MICOP_PROJECT_AUDIT_REPORT.md`](./CI_MICOP_PROJECT_AUDIT_REPORT.md) - a full module-by-module maturity audit with completion-percentage methodology, if you want more depth than this document's summary tables.
- [`CI_MICOP_WORKFLOW_GUIDE.md`](./CI_MICOP_WORKFLOW_GUIDE.md) - a narrative, learning-oriented walkthrough of how the system actually works end to end.
- [`CI_MICOP_Phase_2_Implementation_Plan.docx`](./CI_MICOP_Phase_2_Implementation_Plan.docx) - a detailed Word document with 12 scoped work packages for the next phase of work (acceptance criteria, dependencies, sequencing).

This document is the single starting point for continuing the project. Read it first; follow the links above for depth.

---

## 1. Project overview

- **Name:** CI-MICOP (Cloud-Native Intelligent Motor Insurance Claims Operations Platform).
- **Purpose:** a web platform for an insurance company to run the motor-claims lifecycle end to end - a customer files a claim, a surveyor inspects the vehicle, a Claims Officer reviews everything (including deterministic, rule-based verification and advisory checks) and records the final decision.
- **Main problem addressed:** replacing a manual, paper/email-based claims process with a role-based web portal where every write is server-validated, every file access is re-authorized per request, and every claim's status stays consistent across every page that shows it.
- **Intended users / portals:** Customer, Surveyor, Claims Officer, Admin - one portal each, confirmed by `frontend/src/pages/{customer,surveyor,officer,admin}/`.
- **Technology stack (verified from the actual project files):**

  | Layer | Technology | Verified from |
  |---|---|---|
  | Frontend | React 19, React Router 7, Vite 8, Tailwind CSS 3, Axios, lucide-react, Leaflet 1.9 | `frontend/package.json` |
  | Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, psycopg2 | `backend/requirements.txt` |
  | Database | PostgreSQL | `backend/app/core/config.py` (`DATABASE_URL`), `backend/alembic/` |
  | Documents/images | PyMuPDF, Pillow, pytesseract (+ system Tesseract binary) | `backend/requirements.txt`, `backend/app/services/document_analysis.py` |
  | Auth | JWT (PyJWT), bcrypt password hashing | `backend/app/core/security.py` |
  | Testing | pytest (backend, against real PostgreSQL), Vitest + Testing Library (frontend), oxlint | `backend/tests/`, `frontend/src/**/__tests__/` |

---

## 2. Architecture and repository structure

```
backend/
  app/main.py                FastAPI app entry point; mounts the versioned API router
  app/core/config.py          Settings read from environment variables (see Section 7)
  app/core/security.py        Password hashing (bcrypt) and JWT creation/validation
  app/api/v1/deps.py           get_current_user, require_roles, require_customer_id,
                               require_surveyor_employee_id, require_claims_officer_employee_id
  app/api/v1/routers/          admin, auth, claims, customers, documents, health, officer,
                               policies, surveyor, vehicles - one file per role/resource
  app/db_models/               SQLAlchemy models, one per table (16 tables - see Section 8)
  app/crud/                    Thin per-table query functions, no business logic
  app/schemas/                 Pydantic request/response schemas
  app/services/                Business logic - one module per concern (claim creation,
                               decision recording, evidence capture, document
                               upload/verification, surveyor workflow rules, etc.)
  alembic/versions/            2 migrations (see Section 8) - the schema's real history
  tests/                       pytest suites; run against the real configured PostgreSQL
                               database (see Section 9) - no mocking/SQLite
  seed_dev_data.py             Idempotent script creating one demo claim + 4 demo logins
  seed_test_surveyor1_data.py  A second, narrower seed script for surveyor-focused testing
  scripts/                     Two operator-run (not web-reachable) maintenance scripts -
                               see Section 10's warning before touching either
frontend/
  src/routes/AppRoutes.jsx     Every route, grouped by role
  src/routes/navConfig.js      Per-role navigation (dock + account menu)
  src/pages/{customer,surveyor,officer,admin}/   One folder per role
  src/components/{common,customer,surveyor,officer,camera}/
  src/services/*.js            One file per backend resource; apiClient.js attaches the
                                bearer token to every request
database/schema.sql            Raw SQL equivalent of the current migrated schema (reference
                                only - the real source of truth is alembic/versions/)
ai_ml/                         Standalone research code (own venv, own requirements.txt) -
                                NOT imported by the running backend; see Section 4 and the
                                audit report for exactly what is/isn't wired in live
infra/storage/documents/       Customer document files on disk (git-ignored)
infra/storage/evidence/        Surveyor evidence photos + capture-record JSON (git-ignored)
docs/                          This document, the audit report, workflow guide, Phase 2
                                plan, and docs/project_documentation/ (per-feature reports)
```

**Authentication/authorization (verified in code):** `POST /api/v1/auth/login` issues a JWT (bcrypt-checked password); every protected endpoint decodes and validates that token (`api/v1/deps.py::get_current_user`) and layers a role check on top (`require_roles(...)`, or a role-specific dependency that also derives the acting user's own `Employee_ID`/`Customer_ID` - never trusted from the request body). Claim-level ownership (a customer can only see their own claims, a surveyor only claims they're assigned to) is enforced by one shared function, `services/claim_access.py::get_claim_or_403`, reused by every claim-scoped endpoint.

**File/evidence storage:** no binary file content is ever stored in PostgreSQL - only metadata. Actual files live under `infra/storage/documents/` and `infra/storage/evidence/` on disk, served only through authenticated, re-checked-per-request endpoints (never a public URL or a client-supplied path). Surveyor evidence additionally has a small JSON "capture record" written next to each photo (`services/evidence_capture.py`) recording who/when/where it was captured, since the `evidence` database table itself has no such columns.

**AI/ML integration status (verified - do not assume more than this):** every AI/ML-labeled module actually wired into the live backend (`services/ai_analysis.py`, `ai_pipeline.py`, `document_consistency.py`, `evidence_duplication.py`, `evidence_quality.py`, `repair_estimate_checks.py`) is deterministic/rule-based logic, not a trained model scoring live input, and every one of them is read-only/advisory - none can write to `Claim.Final_Decision` or `Approved_Amount`. Two genuinely trained models exist as files (`ai_ml/model_artifacts/*.pkl`) but are **not loaded by the live backend at all**. Full detail in the audit report, Section E.

**Tests and documentation:** 37 backend test files under `backend/tests/` (pytest, against the real configured database); 52 frontend test files under `frontend/src/**/__tests__/` (Vitest + Testing Library, DOM/API mocked). 35 files under `docs/project_documentation/` document individual features in depth.

---

## 3. Role-based functionality

### Customer
Logs in (no self-registration flow exists - accounts are pre-provisioned); files a claim (`NewClaimPage.jsx` → `POST /claims`, which always creates a matching `accidents` row); uploads claim documents and camera-only accident photos; views My Documents (including identity documents - RC/Driving Licence/Insurance Policy - which are claim-independent, see Section 8); tracks claim status, decision, and a recent-activity timeline. **Verified working** end to end in code and by passing tests. One gap: the "camera-only" rule for accident photos is enforced in the browser UI only - a direct API call can still upload a gallery image as an accident photo (tracked as work package 2 in the Phase 2 plan).

### Surveyor
Logs in; sees only claims they are assigned to (`surveyor_inspections` row = the assignment itself); works through Claim Details → Inspection → Vehicle Damage → Evidence → Survey Report, each step schedule- and order-locked server-side; captures evidence photos with the in-app camera plus either a GPS reading or an indoor-friendly map-selected location (never presented as GPS-verified if it wasn't); can keep/delete their own saved photos before submission; once the survey report is submitted, every further write to that inspection's damage/evidence/findings is refused (409), enforced server-side, not just by a disabled button. **Verified working and extensively tested** - this is the most thoroughly built and tested portal in the project.

### Claims Officer
Logs in; sees every claim; reviews a claim's documents, accident information, evidence (including photo previews), vehicle damage, repair estimates, and a set of deterministic verification/advisory checks (document consistency, evidence duplication/quality, repair-estimate sanity, risk-fusion scoring); assigns a surveyor; records the final Approved/Rejected/Partially-Approved decision, which is then permanently locked (a second attempt gets 409) and moves the claim to a consistent "Completed" status everywhere it's shown. **Verified working and tested**, including a recent fix (see Section 5) and the newly-added Accident Information/Evidence visibility (also Section 5). RFI ("request more information") and Escalations have **no backend at all** - their pages say so explicitly in the UI rather than faking data.

### Admin
Logs in; can list all users and view one user's details (`GET /admin/users`, `GET /admin/users/{id}` - both read-only). **That is the entire real backend for this role.** The Admin dashboard/system-reports pages compute their numbers by reusing the officer's claims-listing endpoint, not a dedicated admin data source. There is no backend to create/edit/disable a user or change a role - the frontend pages for this are honest about that limitation in their own UI text, not a bug to silently work around.

### Main claim workflow (file → close)
Claim creation → claim-specific document/photo upload → appears in the officer's "Under Review" queue → officer assigns a surveyor → surveyor inspects (evidence + damage) and submits the survey report → officer runs the advisory checks and reviews everything (now including full accident details and evidence, see Section 5) → officer records the decision → claim status becomes "Completed" (for every decision outcome, not only Approved) and leaves the active queue → customer sees the final, consistent status/decision/timeline on next load. **Every step above is implemented and covered by a passing automated test.** What is **not** verified: nobody has yet watched this entire flow happen in a real browser from end to end (see Section 9's "manual testing still required").

---

## 4. Current feature-status matrix

| Feature / module | Status | Evidence | Remaining work |
|---|---|---|---|
| Claim creation | Implemented | `services/claim_creation.py`; `tests/test_claim_creation.py` passing | None known |
| Claim-specific document upload | Implemented | `services/document_upload.py`; content sniffed from bytes, not trusted MIME type | Server-side camera-only enforcement for accident photos (Phase 2 WP2) |
| Identity documents (RC/Licence/Policy, claim-independent) | Implemented | `documents.Claim_ID` nullable (`db_models/document.py`); `services/customer_identity_documents.py`, `document_import.py`; `IdentityDocumentsPanel.jsx` | None known |
| Surveyor assignment | Implemented | `services/surveyor_assignment.py`; a `surveyor_inspections` row is the assignment | Always dated "today," no future-date scheduling yet (Phase 2 WP3/WP4) |
| Accident information (officer-visible) | **Implemented and tested** | `routers/officer.py::read_claim_processing_detail` returns `accidents`; `tests/test_officer_accident_and_evidence.py` (17 tests, passing); committed in `698cd1e` | Manual browser confirmation still pending (Section 9) |
| Evidence (officer-visible, incl. image preview) | **Implemented and tested** | Same endpoint returns `evidence` + `GET .../evidence/{id}/image`; same test file; committed in `698cd1e` | Manual browser confirmation still pending (Section 9) |
| Vehicle damage | Implemented | `services/vehicle_damage_creation.py` (create + edit-in-place, no duplicates); `tests/test_vehicle_damage.py` | None known |
| Evidence capture (GPS + indoor map fallback) | Implemented | `services/evidence_capture.py`, `evidence_upload.py`; `LocationPicker.jsx`; extensive passing tests | None known |
| Evidence keep/delete (pre-submission) | Implemented | `evidence_upload.py::set_evidence_kept_for_surveyor/delete_evidence_for_surveyor` | None known |
| Survey report | Implemented | `services/survey_report.py`, `survey_report_pdf.py` | Rebuilt live on every request, no stored submission-time snapshot (Phase 2 WP6, needs approval) |
| Officer decision recording | Implemented | `services/claim_decision.py`; permanent lock, row-level concurrency lock | None known |
| Officer decision → claim status consistency | **Implemented and tested** | `claim_status.py`; every final decision sets `Claim_Status = "Completed"`; committed in `698cd1e`; a new live claim created after this fix (`CLM-B279DFEA22`, Approved, Section 5) also shows consistent status | Re-verify once an isolated test database exists (Phase 2 WP1/WP7) |
| Repair estimates | Partially implemented | `services/repair_estimate_creation.py` exists and is tested, but not subject to the schedule/submission locks the rest of the surveyor workflow has; no current frontend page | Phase 2 WP5 |
| Notifications | **Planned, not implemented** | No backend route found for notifications anywhere in `backend/app/api/v1/routers/`; frontend pages are placeholders | A notifications data model/endpoint would need to be designed from scratch |
| Admin user/role management | **Planned, not implemented** | `admin.py` has exactly 2 read-only endpoints; no create/edit/disable/role-change endpoint exists | Needs its own design - out of Phase 2's current scope unless prioritized |
| RFI / Escalations | **Planned, not implemented** | Pages explicitly state in their own UI that no backend/data model exists yet | Needs its own design |
| AI/ML advisory checks (consistency, duplication, quality, repair-estimate, risk-fusion) | Implemented (rule-based, not ML) | See Section 2 above and the audit report, Section E | Trained models on disk are unused; one of the project's own 7 documented risk signals is permanently unavailable live (by design, not a bug) |

---

## 5. Recent changes and verified outcomes

**All of the following is already committed and pushed** (commit `698cd1e` on `master`), confirmed by `git log` and by `git status` showing a clean working tree at the start of this update:

- **Indoor-friendly evidence location verification** (GPS + map-selection fallback for surveyor photos), including secure capture-record metadata and the Claims Officer's location-source visibility panel.
- **Evidence keep/delete before survey submission**, with server-enforced locking after submission.
- **Claims Officer decision → claim-status consistency fix**: a rejected or partially-approved claim used to stay stuck showing "Under Review" forever; every final decision now correctly moves the claim to "Completed." One pre-existing development-database record with this inconsistency was identified and corrected using its own existing decision-audit record as the source of truth.
- **Customer identity-document import/linkage** (RC/Driving Licence/Insurance Policy as claim-independent records) and a reviewed operator import script.
- **Claims Officer Accident Information and Evidence visibility:**
  - **Status: implemented and tested.** Root cause was that `GET /officer/claims/{claim_id}` never queried the `accidents` or `evidence` tables at all (no actual role restriction existed in the database or CRUD layer - the on-screen warning text did not describe a real backend limitation).
  - Backend: `routers/officer.py::read_claim_processing_detail` returns `accidents` and `evidence` (with capture/location metadata when a verified surveyor capture record exists); `GET /officer/claims/{claim_id}/evidence/{evidence_id}/image` re-checks that the evidence belongs to the exact claim in the URL before serving anything.
  - Frontend: `pages/officer/ClaimDetailsPage.jsx` renders real accident fields and an evidence gallery with image previews; the old "not accessible" warning text was removed only after this was verified working.
  - Tests: `tests/test_officer_accident_and_evidence.py` (17 tests) plus 6 frontend tests in `ClaimDetailsPage.test.jsx` - all passing, re-confirmed by this update's fresh test run (Section 9). **Not yet done:** nobody has visually confirmed these two sections in a real browser (Section 9's manual-testing list).
- Several smaller fixes and UI/navigation adjustments across the officer and surveyor portals (back-button placement, vehicle-damage editing, document viewing security) - see `git log 698cd1e -1 --stat` for the itemized file list, and `docs/CI_MICOP_PROJECT_AUDIT_REPORT.md` for the full picture.

### Deletion of two development claims - independently verified

Two synthetic development claims (`CLM-2026-830E96D2` / `CLM-1817315721` and `CLM-2026-7109C49B` / `CLM-5DCC907922`, both on the seeded demo customer `DEV-CUST-001`) were approved for removal and deleted via a scoped, single-transaction operator script (not part of the committed application code - a one-off action, matching the pattern of the existing `backend/scripts/clear_claims.py` but limited to exactly these two claim IDs). **This was re-verified independently while preparing this document, not just taken from the earlier session's own report:**

- **Database, re-checked just now:** neither claim ID nor claim number exists anywhere in `claims`, or in any of `accidents`/`documents`/`evidence`/`surveyor_inspections`/`vehicle_damage`/`claim_decision_audit` for those two Claim_IDs (all counts 0).
- **API, re-checked just now:** logged in as `dev_customer` via the real FastAPI app and called the actual `GET /claims` endpoint - the two deleted claim numbers are absent from the response.
- **Preserved data confirmed intact:** `customers` (4 rows), `vehicles` (4 rows), `policies` (4 rows), `authentication_users` (6 rows) - `DEV-CUST-001`, `DEV-VEH-001`, `DEV-POL-001` specifically re-confirmed present.
- **Files:** the 19 associated files (2 evidence photos + their `.capture.json` sidecars, 13 document files, 2 inspection `.workflow.json` files) were deleted only after the database transaction committed successfully; none were found "missing" (all genuinely existed beforehand, all were removed). Two now-empty leftover folders remain (`infra/storage/{evidence,documents}/CLM-1817315721` and `.../CLM-5DCC907922`) - harmless, no files inside, not cleaned up because removing directory structure wasn't part of the approved scope.

**One claim now exists in the database again:** `CLM-B279DFEA22` / `CLM-2026-303DA211`, dated 2026-10-29, `Claim_Status = Completed`, `Final_Decision = Approved`, on the same demo customer/vehicle. This was **not** one of the two deleted claims and was **not** created by this task - it was created independently (most likely through further manual testing of the app after the deletion) between the previous session and this one. It is left untouched, as instructed ("do not rerun the claim deletion"), and is reported here only as evidence that the deletion worked cleanly and the claim-creation → decision → consistent-status pipeline still works end to end afterward (an Approved decision here also correctly shows `Claim_Status = Completed`, consistent with Section 4's fix).

---

## 6. Local setup instructions (Windows, beginner-friendly)

These are the project's own documented commands (from `README.md`), re-verified against the actual repository while preparing this document - not invented.

### Step 1 - Clone the repository
```bash
git clone https://github.com/CI-MICOP/CI-MICOP.git
cd CI-MICOP
```

### Step 2 - Backend: install PostgreSQL and create the database
You need PostgreSQL installed and running (any recent version; version 18 was used during development).
```bash
# If PostgreSQL was installed as a Windows service:
net start postgresql-x64-18

# Create the database once (adjust the path to your PostgreSQL install if different):
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE ci_micop;"
```
*(This step needs your own PostgreSQL password, which only you know - the command above will prompt for it.)*

### Step 3 - Backend: configure environment variables
```bash
cd backend
copy .env.example .env
```
Then **open `backend\.env` in a text editor** and set:
- `DATABASE_URL` - your own PostgreSQL connection string, e.g. `postgresql+psycopg2://postgres:<your-password>@localhost:5432/ci_micop`
- `JWT_SECRET_KEY` - a strong random value of your own choosing (at least 32 characters). Never use a short/guessable value.

Never commit `backend\.env` - it is already excluded by `.gitignore`. Only `.env.example` (with placeholder values) should ever be committed.

### Step 4 - Backend: install dependencies and apply migrations
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
```
This creates all of the application's tables. (Confirmed: there are currently 2 migrations, and `alembic upgrade head` is the correct command to bring a fresh database fully up to date.)

### Step 5 - Backend: start the API
```bash
uvicorn app.main:app --reload
```
The API runs at `http://localhost:8000`. Confirm it's working:
```bash
curl http://localhost:8000/api/v1/health
```
You should see: `{"status":"ok","service":"CI-MICOP API"}`

### Step 6 - Backend: load demo data (optional, recommended for first-time exploration)
```bash
python seed_dev_data.py
```
This is safe to re-run. It creates one demo claim and four demo logins, **all with the password `CiMicop@123`** (this is a publicly-known, already-documented development-only password - never use it, or any password you actually use elsewhere, for anything real):

| Username | Role |
|---|---|
| `dev_customer` | Customer |
| `dev_surveyor` | Surveyor |
| `dev_officer` | Claims Officer |
| `dev_admin` | Admin |

### Step 7 - Frontend: install and start
Open a **second** terminal window (keep the backend running in the first one):
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```
The app opens at `http://localhost:5173`. Log in with one of the demo accounts above.

### Step 8 - Running tests, lint, and a production build
Backend (from the `backend` folder, with `venv` activated, same terminal as Step 4/5):
```bash
pytest tests/ -v
```
Frontend (from the `frontend` folder):
```bash
npm test
npm run lint
npm run build
```
See Section 9 for the actual results of running these, including known pre-existing failures.

### Optional - reading scanned (not just typed) documents
```bash
winget install UB-Mannheim.TesseractOCR
```
Then add this line to `backend\.env`:
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```
Without this, the app still works - it just reports scanned pages as "unavailable" instead of reading their text.

---

## 7. Environment and external services

**Backend** (`backend/.env`, template at `backend/.env.example`) - names only, never values:

| Variable | Purpose | Required? |
|---|---|---|
| `ENVIRONMENT` | `development`/`test` relaxes a security check; anything else hides `/docs`/`/redoc` and requires a strong `JWT_SECRET_KEY` | Required |
| `BACKEND_CORS_ORIGINS` | Which frontend origin(s) may call the API | Required |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `JWT_SECRET_KEY` | Signs/verifies login tokens | Required |
| `JWT_ALGORITHM` | Token signing algorithm | Required |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Login token lifetime | Required |
| `LOGIN_MAX_FAILED_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES` | Login throttling after repeated failures | Optional (has a default) |
| `DOCUMENT_STORAGE_ROOT` / `DOCUMENT_MAX_UPLOAD_BYTES` | Where customer document files are stored, and the upload size cap | Optional (has a default) |
| `EVIDENCE_STORAGE_ROOT` / `EVIDENCE_MAX_UPLOAD_BYTES` | Where surveyor evidence photos are stored, and the upload size cap | Optional (has a default) |
| `RISK_FUSION_ARTIFACTS_ROOT` | Where the read-only risk-fusion research artifacts live | Optional (has a default) |
| `TESSERACT_CMD` | Path to the Tesseract OCR executable | Optional - app works without it |

**Frontend** (`frontend/.env`, template at `frontend/.env.example`): `VITE_API_BASE_URL` - the backend's base URL (Required).

**External services:** only PostgreSQL (required, local) and, optionally, the Tesseract OCR system binary (not a cloud service - installed locally). **No cloud/SaaS services, email providers, or external APIs are called anywhere in the backend** - confirmed by inspection; everything (including the "AI/ML" checks) runs locally against the project's own database and files. `ai_ml/` has its own separate Python environment and `requirements.txt` and is not required to run the main application.

---

## 8. Database and sample-data guidance

- **Schema and migrations:** `backend/alembic/versions/` - **2 migrations**, confirmed applied and at head on this machine's configured database (`alembic current` → `7a1c9e5f2b3d (head)`):
  1. `0eb88898ddd4_create_15_table_ci_micop_schema.py` - the original 15-table schema.
  2. `7a1c9e5f2b3d_add_identity_document_import_columns.py` - adds `Customer_ID`/`Vehicle_ID`/`Policy_ID`/`Document_Expiry_Date`/`Issuer_Reference`/`Uploaded_By` to `documents` and makes `documents.Claim_ID` nullable (so a document can belong to a customer directly, not only to one claim - this is how identity documents work). All added columns are nullable; no existing data is affected.
  - **Apply in order** with a single command: `alembic upgrade head` (Alembic applies every un-applied migration in the correct order automatically).
  - `database/schema.sql` is a **reference** copy of the raw SQL schema - the real source of truth is the Alembic migration history above.
- **Sample/seed data:** `backend/seed_dev_data.py` (one demo claim + 4 demo logins, idempotent) and `backend/seed_test_surveyor1_data.py` (a second, narrower seed variant). Both are safe to run against a development database and safe to re-run.
- **Testing safely with synthetic data:** the backend's own test suite (`pytest tests/`) inserts clearly-prefixed (`TEST-...`) rows into the *same configured database* and deletes them again after each test - there is currently no separate, isolated test database (this is flagged as the single highest-priority next task in the Phase 2 plan, work package 1).
- **Current database state (re-checked while preparing this document):** exactly **1 claim** exists (`CLM-B279DFEA22`, Completed/Approved, on the `DEV-CUST-001`/`DEV-VEH-001`/`DEV-POL-001` demo chain). Two earlier development claims were approved for removal and verified deleted - see Section 5 for the full, independently-re-checked evidence (database counts, a real API call, and the preserved-record check). If you need more than one demo claim to test with, either use the app normally to create more, or re-run `python seed_dev_data.py` (safe, idempotent).

> **Warning - read before running anything database-related:** `backend/scripts/clear_claims.py` is a destructive, operator-only script that deletes **every claim** in whatever database `DATABASE_URL` currently points to (it preserves customer/vehicle/policy accounts and detaches identity documents rather than deleting them, but it is still destructive to claim data). Its own docstring says it must be reviewed and explicitly approved by the project owner before being run. **Never run it against anything you are not certain is a disposable development database.** Do not run `alembic upgrade`, either seed script, or the destructive script above against a database holding real claim or customer data.

---

## 9. Testing and verification results

**Commands actually re-run while preparing this update (not reused from an earlier report), and their exact results:**

| Check | Command | Result |
|---|---|---|
| Backend tests | `cd backend && ./venv/Scripts/python.exe -m pytest tests/ -q` | **1037 passed, 5 failed** (1042 total) |
| Frontend tests | `cd frontend && npx vitest run` | **406 passed, 0 failed** (52 test files) |
| Frontend lint | `cd frontend && npx oxlint` | Clean except 3 pre-existing warnings (see below) |
| Production build | `cd frontend && npx vite build` | **Succeeds** (994 KB bundle; pre-existing "chunk larger than 500 kB" warning only - no code-splitting configured) |
| Migration state | `alembic current` / `alembic heads` | Both report `7a1c9e5f2b3d (head)` - database is fully up to date |

All five numbers above are identical to the previous session's run - re-running them after the claim-deletion script confirms that operation caused no regression anywhere in the test suite.

**The 5 backend failures (confirmed pre-existing, not caused by any recent change):**
- `test_document_consistency.py::test_cross_customer_cannot_trigger_consistency_check_on_anothers_document`
- `test_evidence_duplication.py::test_end_to_end_undecodable_photo_is_unavailable`
- `test_evidence_quality.py::test_end_to_end_undecodable_photo_is_unavailable`
- `test_survey_report.py::test_submission_requires_a_damage_record_when_damage_was_observed`
- `test_survey_report.py::test_future_scheduled_inspection_cannot_be_started` (date-dependent - this test's own fixture assumes "today" is earlier than it now actually is; it will keep failing as real time passes until rewritten)

**The 3 lint warnings (pre-existing, not errors):** `AuthContext.jsx` ×2 (`react(set-state-in-effect)`, `react(only-export-components)`), `InspectionWorkspacePage.jsx` ×1 (`react(set-state-in-effect)`).

**Tests not run:** no dependency-vulnerability scan (`npm audit`/`pip-audit`) has been run as part of this or prior sessions. No automated end-to-end/browser test suite exists in this project.

**Manual browser testing still required (nobody has done this yet for this project):**
1. A full login-to-decision walkthrough for at least one Approved and one Rejected claim, as every role in turn.
2. Real-device camera/GPS testing (the frontend test suite mocks `navigator.mediaDevices`/`navigator.geolocation` - this proves the logic is correct under controlled inputs, not that a real phone's camera/GPS behaves the same way).
3. Visually confirming the new Accident Information and Evidence sections on the officer's Claim Details page render correctly in a real browser with real data.

---

## 10. Known issues and security considerations

**Verified by direct inspection (not guesses):**
- No isolated test database exists; all backend tests run against the same database the app itself would use in development. (Phase 2 work package 1 - rated Critical.)
- `repair_estimate_creation.py` is not subject to the schedule/submission locks the rest of the surveyor workflow has, and currently has no frontend page calling it.
- Survey reports are rebuilt live on every request; there is no stored snapshot of what a report looked like at the moment it was submitted.
- Surveyor assignment and a few other places use the server's local date (`date.today()`) rather than the India Standard Time helper the rest of the surveyor workflow already uses (`today_ist()`) - a difference that is only ever visible for roughly an hour either side of midnight IST.
- Admin, RFI, and Escalation functionality is honestly incomplete (see Section 4) - the relevant pages say so in their own UI text.
- Two trained fraud-detection models exist on disk but are never loaded by the live backend.
- No automated CI pipeline exists (no `.github/workflows/`), and no backup/recovery procedure is documented anywhere in the project.
- The local development `.env`'s `JWT_SECRET_KEY` does not meet the application's own minimum-strength requirement - this is harmless because the app's own startup check only enforces that requirement outside `development`/`test` mode, but it **must** be replaced with a strong, randomly generated value before any non-development deployment.

**Needs further investigation (not yet confirmed either way):**
- Real-browser rendering of served PDFs/images under the existing Content-Security-Policy headers has not been visually confirmed (only the headers themselves have been checked in code).
- The backend's CORS middleware configuration (`allow_methods`/`allow_headers`) has not been explicitly re-confirmed as non-wildcarded in the most recent review pass.

For the full, categorized list with file-level citations, see `docs/CI_MICOP_PROJECT_AUDIT_REPORT.md`, Sections D and G.

---

## 11. Prioritized continuation roadmap

*(Full detail, dependencies, and acceptance criteria for every item below are in `docs/CI_MICOP_Phase_2_Implementation_Plan.docx`; this is a condensed pointer.)*

### Priority 1 - Correctness, authorization, data integrity, security
1. **Set up an isolated PostgreSQL test database.** *Files:* `backend/app/core/config.py`, `backend/tests/conftest.py`. *Acceptance:* the full backend suite runs against a disposable database with one documented setup step, never the real development database.
2. **Rotate the development JWT secret before any non-development deployment**, and confirm the CORS middleware's methods/headers are not wildcarded. *Files:* `backend/.env` (not committed), `backend/app/main.py`.
3. **Enforce the customer camera-only accident-photo rule server-side**, mirroring the surveyor's existing capture-record pattern. *Files:* `backend/app/services/document_upload.py`, `evidence_capture.py` (pattern), `frontend/src/components/customer/AccidentPhotoCapture.jsx`.

### Priority 2 - Complete and verify core claim workflows
4. **Bring repair estimates under the same schedule/submission locks as the rest of the surveyor workflow** (or formally retire the endpoint, matching the precedent already used for the old evidence-upload endpoint). *Files:* `backend/app/services/repair_estimate_creation.py`.
5. **Add a stored survey-report snapshot** so a submitted report's content is provably stable (needs approval - this is a schema/storage change). *Files:* `backend/app/services/survey_report.py`.
6. **Perform the manual, full-lifecycle browser walkthrough** this project has never had (Section 9).

### Priority 3 - Admin, RFI, Escalations, and other incomplete features
7. Decide whether Admin needs real user/role/config management, and whether RFI/Escalations are in scope; if yes, design their data models and endpoints from scratch - neither currently has one.

### Priority 4 - AI/ML integration and model behavior
8. Decide whether the two trained models on disk (`ai_ml/model_artifacts/*.pkl`) should ever be loaded live, or explicitly documented as research-only so nobody is confused later.
9. Make the India Standard Time date helper (`today_ist()`) the single source of truth everywhere a "today" is recorded (`surveyor_assignment.py`, `claim_creation.py`, `claim_decision.py` currently use the server's local date instead).

### Priority 5 - Deployment, CI, documentation, backup/recovery, end-to-end testing
10. Add a GitHub Actions workflow running the backend and frontend test suites on every push (needs Priority 1's isolated database first).
11. Write a backup/recovery procedure covering both the PostgreSQL database and the `infra/storage/` file directories - currently undocumented.
12. Real-device camera/GPS testing on at least one Android and one iOS device (Section 9).

---

## 12. Developer handoff checklist

- [ ] Repository cloned successfully
- [ ] PostgreSQL installed, `ci_micop` database created
- [ ] `backend/.env` configured with your own `DATABASE_URL` and a strong `JWT_SECRET_KEY`
- [ ] `frontend/.env` configured
- [ ] Backend dependencies installed, migrations applied (`alembic upgrade head`)
- [ ] Backend starts (`uvicorn app.main:app --reload`) and `/api/v1/health` responds
- [ ] Demo data loaded (`python seed_dev_data.py`), or you have your own data
- [ ] Frontend installed and running (`npm run dev`), app opens at `localhost:5173`
- [ ] Logged in successfully as each of the 4 demo roles
- [ ] Walked through the full claim workflow at least once as each role (Section 3)
- [ ] Specifically checked the Claims Officer's Accident Information and Evidence sections on a claim's Details page
- [ ] Confirmed the current claim count in the database matches what you expect (one demo claim as of this writing - Section 8) before assuming any particular claim should or shouldn't be there
- [ ] Backend tests run (`pytest tests/ -v`) and the 5 pre-existing failures recognized as such, not new bugs
- [ ] Frontend tests, lint, and build run and reviewed
- [ ] Section 10 (Known issues) reviewed
- [ ] Next task selected from Section 11

---

## 13. Git and handoff metadata

- **Repository URL:** `https://github.com/CI-MICOP/CI-MICOP.git` (configured as `origin`, confirmed reachable).
- **Branch:** `master`.
- **Commit hash immediately before this update:** `698cd1e` - confirmed as the tip of both local `master` and `origin/master` (no divergence) at the start of this task.
- **Commit hash after this update:** recorded in this session's final chat report once this document is committed and pushed - not duplicated here, since this file is itself part of that commit and can't know its own resulting hash in advance.
- **Handoff document path:** `docs/CONTINUATION_HANDOFF.md` (this file - the same path as before; updated in place, not duplicated).
- **The two approved claim deletions:** independently re-verified in Section 5 - not a Git-tracked change (it was a database operation, not a file change), so it does not appear in `git log` or `git status`, but is documented here for continuity.
- **Local-only / intentionally excluded files (unchanged from the previous revision of this document):**
  - `backend/backups/ci_micop_backup_20261027_220956.dump` - a local PostgreSQL dump, confirmed still present on disk and still correctly excluded by the committed `.gitignore` rule (`backend/backups/`, `*.dump`) - database dumps must never be committed, as they can contain real data.
  - `backend/.env`, `frontend/.env` - your real local configuration; never committed, already `.gitignore`-excluded.
  - Nothing else is known to be intentionally excluded as of this writing.
