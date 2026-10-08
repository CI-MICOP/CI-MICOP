# CI-MICOP

**Cloud-Native Intelligent Motor Insurance Claims Operations Platform**

## Purpose

CI-MICOP is a final year project platform for managing motor insurance
claims end-to-end, with AI/ML-assisted fraud detection, document
consistency checks, and risk analysis planned for future stages.

## Technology Stack

| Layer          | Technology                                   |
|----------------|-----------------------------------------------|
| Frontend       | React.js, Vite, JavaScript, Tailwind CSS      |
| Backend        | Python, FastAPI, SQLAlchemy, Alembic          |
| Database       | PostgreSQL                                    |
| AI/ML          | Python (modules added in a later step)        |
| Authentication | JWT with Role-Based Access Control (RBAC)     |
| API            | REST (JSON)                                   |
| Development    | VS Code, Git/GitHub                           |
| Deployment     | Docker (added in a later step)                |

### Roles

- Customer
- Surveyor
- Claims Officer
- Admin

## High-Level Architecture

```
frontend/   React + Vite + Tailwind CSS SPA, talks to the backend over REST
backend/    FastAPI REST API (versioned under /api/v1), SQLAlchemy + Alembic
            for PostgreSQL access and migrations
ai_ml/      Standalone Python modules for fraud detection, document
            consistency checks, OCR, risk fusion, etc. (added later)
database/   PostgreSQL schema and seed data
infra/      Docker and deployment configuration (added later)
docs/       Project documentation and diagrams
```

The frontend and backend are independent services that communicate only
through the versioned REST API, so either can be developed, run, or
deployed without the other.

## Current Implementation Status

**Step 1 — Project Foundation**

- [x] Frontend scaffolded with Vite + React, Tailwind CSS configured
- [x] Backend scaffolded with FastAPI, versioned API structure (`/api/v1`)
- [x] Health check endpoint: `GET /api/v1/health`
- [x] Alembic initialized
- [x] Environment variable templates for frontend, backend, and root
- [x] `.gitignore` covering both stacks

**Step 2 — Database**

- [x] Final 15-table PostgreSQL schema (`database/schema.sql`)
- [x] SQLAlchemy models for all 15 tables (`backend/app/db_models/`)
- [x] Initial Alembic migration, applied to a local `ci_micop` database

**Step 3 — Backend API Layer (current)**

- [x] JWT authentication (`POST /api/v1/auth/login`) with bcrypt password hashing
- [x] Role-based access control (Customer, Surveyor, Claims Officer, Admin)
- [x] Read APIs for customers, vehicles, policies, claims, and documents,
      scoped by role (a customer only ever sees their own data)
- [x] Surveyor endpoints (assigned inspections, claim detail, inspection updates)
- [x] Claims Officer endpoints (claim list/detail for processing)
- [x] Admin endpoints (user listing)
- [x] Pydantic request/response schemas for every endpoint
- [x] Automated tests covering login, JWT, and RBAC for all four roles

Not yet implemented (planned for later steps): claim/document write APIs
beyond inspection updates, automated decisions, the React frontend, and
all AI/ML modules (fraud detection, OCR, risk fusion, etc.).

## Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The app runs at `http://localhost:5173` by default.

## Backend Setup

### 1. Start PostgreSQL

CI-MICOP requires a running PostgreSQL server (18 was used during
development, any recent version works) and a `ci_micop` database.

```bash
# Windows, if installed as a service:
net start postgresql-x64-18

# Then create the database once (any client works, e.g. psql):
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE ci_micop;"
```

### 2. Configure `backend/.env`

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL` to your own PostgreSQL
credentials, e.g.:

```
DATABASE_URL=postgresql+psycopg2://postgres:<your-password>@localhost:5432/ci_micop
```

Also set `JWT_SECRET_KEY` to a strong random value. Never commit `.env`
(it's already git-ignored) - only `.env.example` with placeholders is
tracked.

### 3. Install dependencies and run migrations

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
```

`alembic upgrade head` creates all 15 application tables (see
`database/schema.sql` for the equivalent raw SQL).

### 4. Start the API

```bash
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000` by default. Verify it is working:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{ "status": "ok", "service": "CI-MICOP API" }
```

### 5. Run tests

Tests run against the same PostgreSQL database configured in
`backend/.env` (no mocking/SQLite - see project rules). They insert a
small set of clearly-prefixed (`TEST-...`) rows before running and
delete them afterward.

```bash
pytest tests/ -v
```

### 6. Load development data (optional)

`alembic upgrade head` creates empty tables. To get one example claim and
four logins to try the app with, run once from `backend/`:

```bash
python seed_dev_data.py
```

It can be run again safely. It creates claim `DEV-CLM-001` and these
accounts, all with the password `CiMicop@123`:

| Username | Role |
|---|---|
| `dev_customer` | Customer |
| `dev_surveyor` | Surveyor |
| `dev_officer` | Claims Officer |
| `dev_admin` | Admin |

Development only - never use these as production credentials.

### 7. Reading scanned documents (optional)

Normal PDFs are read without any extra software. Scanned or photographed
documents need the Tesseract OCR program, which `pip` does not install:

```bash
# Windows
winget install UB-Mannheim.TesseractOCR
```

Then add to `backend/.env`:

```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Without Tesseract the API still works and reports scanned pages as
unavailable. With it installed, two backend tests that cover the
"Tesseract not installed" case skip themselves.

### API documentation

Interactive Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`
Raw OpenAPI schema: `http://localhost:8000/openapi.json`

To authenticate in Swagger UI: call `POST /api/v1/auth/login` with a
valid username/password (form fields), then click **Authorize** and
paste the returned `access_token`.

## Frontend Tests

```bash
cd frontend
npx vitest run --maxWorkers=1   # all tests
npx oxlint src                  # lint
npx vite build                  # production build
```

## AI/ML Research Code

`ai_ml/` is separate from the running API and has its own packages. The
dataset and saved model results it needs are in the repository
(`ai_ml/datasets/`, `ai_ml/model_artifacts/`). From the repository root:

```bash
python -m venv ai_ml/venv
ai_ml\venv\Scripts\activate          # Windows
pip install -r ai_ml/requirements.txt pytest
python -m pytest ai_ml/tests
```

## Where the Project Stands

The "Current Implementation Status" list above describes the early steps
only. For the current state, the work done since, and what is left, see
`docs/project_documentation/PROGRESS_REPORT_2026-10-08.md`. Each feature
has its own report in the same folder.
