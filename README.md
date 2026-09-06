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

**Step 1 — Project Foundation (current)**

- [x] Frontend scaffolded with Vite + React, Tailwind CSS configured
- [x] Backend scaffolded with FastAPI, versioned API structure (`/api/v1`)
- [x] Health check endpoint: `GET /api/v1/health`
- [x] Alembic initialized (no models/migrations yet)
- [x] Environment variable templates for frontend, backend, and root
- [x] `.gitignore` covering both stacks

Not yet implemented (planned for later steps): database schema/models,
authentication (JWT/RBAC), claim management APIs and dashboards, and all
AI/ML modules (fraud detection, OCR, risk fusion, etc.).

## Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The app runs at `http://localhost:5173` by default.

## Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000` by default.
Verify it is working:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{ "status": "ok", "service": "CI-MICOP API" }
```

Interactive API docs are available at `http://localhost:8000/docs`.
