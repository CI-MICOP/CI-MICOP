# Regression and Security Review (Step 5.8.23)

## 1. Objective

Roadmap item 11: "Full backend/frontend/security regression tests."

This step ran every automated test in the project, reviewed the backend and
frontend for security weaknesses, and added tests for the security cases that
had none.

It changed **no application code**: no router, service, schema, migration,
dependency or frontend file. The only new files are one test module and
this report. The improvements to do later are listed in Section 5 with a recommended
fix each. Two of them (5.1 and 5.3) were applied afterwards in Step 5.8.24;
the others are still open.

## 2. Files

| File | Change |
|---|---|
| `backend/tests/test_security_regression.py` | New - 109 tests |
| `docs/project_documentation/SECURITY_AND_REGRESSION_REVIEW.md` | New - this report |

## 3. Regression Results

Run on 2026-10-08, Windows 11, Python 3.13.3, real PostgreSQL database.

| Suite | Result | Notes |
|---|---|---|
| Backend (`backend/tests`) | 629 / 629 passing | 520 before this step + 109 new |
| Frontend (`npx vitest run --maxWorkers=1`) | 160 / 160 passing | 26 test files |
| Frontend build (`npx vite build`) | Succeeds | One warning: a bundle chunk is larger than 500 kB |
| Frontend lint (`npx oxlint src`) | 0 errors, 3 warnings | `AuthContext.jsx` (2), `InspectionWorkspacePage.jsx` (1); React style warnings, not security |
| AI/ML research (`ai_ml/tests`) | 101 / 101 passing | First run on this machine; needs `ai_ml/requirements.txt` and the dataset |

## 4. What Was Reviewed and Found Sound

| Area | Finding |
|---|---|
| Access check on every route | 38 routes. 3 are public on purpose (`/`, `/health`, `/auth/login`). The other 35 all return 401 without a token. |
| Role checks | Customer and Surveyor get 403 on all 12 officer routes; Customer, Surveyor and Officer get 403 on both admin routes; Customer and Officer get 403 on all 7 surveyor routes. |
| Role source | The role is read from the database on every request. A correctly signed token that claims "Admin" for a Customer account still gets Customer rights. |
| Token checks | Expired, wrong-key, unsigned (`alg: none`), unknown-user and empty-subject tokens are all rejected. |
| Suspended accounts | Cannot log in, and a token issued before the suspension is refused at once. |
| Claim ownership | One central check (`services/claim_access.py`): a Customer only reaches their own claims, a Surveyor only assigned claims. Already covered by earlier tests. |
| Identity in writes | Customer_ID, Surveyor_ID and Claims_Officer_ID always come from the token, never from the request body. |
| Passwords | bcrypt hashes. No hash appears in any API response. |
| Login error | Wrong password and unknown username return the same response. |
| SQL | All database access goes through the SQLAlchemy ORM. No raw SQL, `eval`, `exec`, `pickle`, `subprocess` or shell call in `backend/app`. SQL-looking usernames and claim IDs behave as ordinary wrong values. |
| File upload | Extension allow-list, content signature check, 10 MB limit read in chunks, server-generated file name, path-traversal guard. Already covered by earlier tests. |
| CORS | Only the configured origin is allowed; a request from another origin gets no allow header. |
| Secrets | No `.env`, key or password file is tracked in git. The local JWT secret is 64 characters and is not the default. |
| Frontend | No `dangerouslySetInnerHTML`, `innerHTML` or `eval`. Every role area is behind a role guard. Production packages: `npm audit --omit=dev` reports 0 vulnerabilities. |
| Final decision | Only `services/claim_decision.py` writes `Final_Decision`, `Approved_Amount` or `claim_decision_audit`, and only from the officer's request. No analysis service writes them. |
| Wording | The word "fraud" does not appear in any user-facing text of the consistency, evidence or repair-estimate checks. |
| Schema and dependencies | One migration (the original 15 tables). No transformer, NLI or other heavy ML package in either requirements file. |

## 5. Improvements To Do Later

None of these was fixed during the review itself. Two were done afterwards
in Step 5.8.24 and are marked **Done** below. Ordered by how much they matter.

### 5.1 Backend packages with published security advisories

`pip-audit` on `backend/requirements.txt` reports advisories for five
pinned or resolved packages:

| Package | Version now | Advisories fixed by |
|---|---|---|
| PyJWT | 2.10.1 | 2.15.0 |
| python-multipart | 0.0.20 | 0.0.31 |
| starlette (installed by fastapi 0.116.1) | 0.47.3 | 1.3.1 |
| python-dotenv | 1.0.1 | 1.2.2 |
| pytest (test tool only) | 8.3.4 | 9.0.3 |

The individual advisories were not read in this step, so their real impact
on this project is not assessed. PyJWT (login tokens), python-multipart
(file uploads) and starlette (every request) are all on the request path.

A trial was run in a separate throwaway environment with
`fastapi 0.142.4`, `starlette 1.7.0`, `PyJWT 2.15.0`,
`python-multipart 0.0.31`, `python-dotenv 1.2.2` and `pytest 9.0.3`, all
other pins unchanged: `pip-audit` reports no known vulnerabilities and all
629 backend tests pass. The project's own environment and
`requirements.txt` were not changed.

**Done (Step 5.8.24).** `backend/requirements.txt` now pins
`fastapi==0.142.4`, `starlette==1.7.0`, `PyJWT==2.15.0`,
`python-multipart==0.0.31`, `python-dotenv==1.2.2` and `pytest==9.0.3`.
`starlette` is pinned by name because upgrading `fastapi` alone leaves an
already-installed older `starlette` in place. After installing: `pip-audit`
reports no known vulnerabilities, the backend suite is 627 passed and 2
skipped (the two Tesseract-absent tests), and the real server starts and
answers health and login requests. Each developer must run
`pip install -r backend/requirements.txt` once to get the new versions.

### 5.2 No limit on login attempts

`Failed_Login_Count` is increased on every wrong password and reset on a
correct one, but nothing reads it. There is no lockout, delay or rate limit,
so passwords can be guessed without restriction.

**Recommended:** refuse login after a set number of consecutive failures
(for example for a fixed time), or add request rate limiting on
`/auth/login`. The limit itself is a product decision.

### 5.3 Uploaded files are not excluded from git

`infra/storage/documents/` and `infra/storage/evidence/` hold customer
documents and surveyor photos. Neither is in `.gitignore`. Both folders are
empty now (the tests clean up after themselves), but after any real upload a
`git add .` would commit those files to GitHub.

**Done (Step 5.8.24).** `infra/storage/documents/` and
`infra/storage/evidence/` are now in `.gitignore`. `infra/storage/.gitkeep`
is still tracked.

### 5.4 Token settings that are safe now but fail open

- `JWT_SECRET_KEY` defaults to `"changeme"` in `core/config.py`. If the
  variable is missing from the environment the API starts normally with
  that known key, and anyone could then sign valid tokens.
- A correctly signed token with no expiry claim is accepted. The API always
  sets an expiry, so this only matters if the key leaks or a token is
  issued some other way.

**Recommended:** refuse to start outside development when the secret is the
default, and require the `exp` and `sub` claims when decoding.

### 5.5 API documentation pages are public

`/docs`, `/redoc` and `/openapi.json` are served without login. This is
normal in development. In a deployed system it gives the full endpoint list
to anyone.

**Recommended:** disable or protect them when `ENVIRONMENT` is not
`development`. Belongs with roadmap item 12.

### 5.6 Frontend development tools with advisories

`npm audit` reports 11 advisories (3 moderate, 6 high, 2 critical), all in
build and test tooling (for example `tinypool`, `braces`,
`source-map-js`). None is in the code shipped to the browser. Some fixes
need `npm audit fix --force`, which makes breaking version changes.

**Recommended:** run `npm audit fix` (non-breaking), re-run the frontend
tests, and review the forced upgrades separately.

### 5.7 Lower-priority observations

- **Token storage.** The login token is kept in `localStorage`, so a
  script-injection bug would expose it. No injection point was found.
  Tokens last 60 minutes; there is no refresh token and logout is
  client-side only (a copied token stays valid until it expires).
- **Login timing.** An unknown username returns faster than a wrong
  password, because no hash is checked. The response text is identical, but
  timing could still reveal which usernames exist.
- **Transport and headers.** No HTTPS, HSTS or other security headers. These
  are deployment concerns (roadmap item 12).
- **Customer access to analysis.** `POST /documents/{id}/analyze` is open to
  the customer who owns the claim, by design (documented in
  `DOCUMENT_COMPLETENESS_AND_OCR.md`). Its response includes the
  registration and policy MATCH / MISMATCH result. Whether customers should
  see that result is a product decision.
- **Admin can update any inspection** through
  `PATCH /surveyor/inspections/{id}`. By design; noted for completeness.

## 6. New Tests

`backend/tests/test_security_regression.py` (109 tests):

- **Every route.** The list of routes is read from the API's own OpenAPI
  description, so an endpoint added later without an access check fails
  these tests. Each of the 35 protected routes is called with no token and
  with a garbage token (70 tests); the officer, admin and surveyor routes
  are called with every role that must be refused (21 tests); one test
  pins the list of public routes.
- **Tokens.** Expired, wrong key, unsigned, unknown user, empty subject,
  role claim that disagrees with the database, and a control case (7 tests).
- **Accounts and input.** Suspended account login and token, identical
  login errors, failed-login counter reset, SQL-looking usernames and claim
  IDs (9 tests).
- **Password hashes.** Not present in any user-returning response (1 test).

These tests describe the current behaviour. They do not cover the items
in Section 5: no test was written that would fail until a fix is made.

## 7. Not Covered

- **No penetration test.** This was a code review plus automated tests, not
  an attack on a running deployment.
- **No browser check.** No screen was opened by hand in a browser in this
  step.
- **OCR of real scans.** Tesseract 5.4.0 was installed on the machine after
  the review, and the scanned-image path ran for the first time: five
  generated files (PNG, JPG, image-only PDF, and a tilted, blurred, noisy
  PNG and PDF) were each read with status `extracted_ocr`, confidence
  0.95, and all five expected values (registration, policy number, FIR
  number, date, location) exact. These were computer-made images of clean
  printed text, not real scans or phone photos, handwriting, stamps or
  other languages; only English is installed. With Tesseract present the
  backend suite is 627 passed, 2 skipped: the two skipped tests cover the
  "Tesseract not installed" path and skip themselves by design.
- **Load and concurrency.** No performance or parallel-request testing.
- **Docker / deployment.** The three files in `infra/docker/` are
  placeholders; nothing deployed exists to review.
- **AI/ML dependencies** (`ai_ml/requirements.txt`) were not audited. They
  are not part of the running API.
- **Line-by-line audit.** The checks in Section 4 were done by reading the
  access-control and upload code and by searching the whole backend for
  risky patterns. Not every line of every service was read.

## 8. Open Points for Review

1. ~~Apply the package updates in 5.1~~ Done in Step 5.8.24.
2. Choose a login-attempt limit (5.2).
3. ~~Add the two storage folders to `.gitignore` (5.3)~~ Done in Step 5.8.24.
4. Harden the token settings (5.4).
5. Decide whether customers should see the MATCH / MISMATCH result (5.7).
