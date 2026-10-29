# CI-MICOP — Complete Project Audit Report

**What this document is:** A full, evidence-based audit of the CI-MICOP motor insurance claims platform — what's actually built, what's tested, what's missing, and what's left before this is demo/production ready. It was produced by inspecting the real code, running the real test suites, and querying the real (development) database read-only — not by guessing from filenames or counting UI screens.

**Who this is for:** Written so a friend with general software background — but no prior exposure to this specific codebase — can understand what the project does, how mature each part is, and where the interesting engineering decisions are. If a term isn't obvious, it's explained inline.

**Project path:** `C:\Users\Admin\Downloads\Final year project\ci-micop`
**Audit date:** 2026-10-28 · **Branch:** `master` (substantial uncommitted work in progress)

---

## 0. What is CI-MICOP?

A motor insurance claims platform with four user roles, each with its own portal:

- **Customer** — files a claim after an accident, uploads documents/photos, tracks status.
- **Surveyor** — a field inspector assigned to a claim, who visits the vehicle, takes photos with location data, records damage, and submits a survey report.
- **Claims Officer** — reviews everything (documents, evidence, AI-generated advisory signals) and records the final Approve/Reject/Partially-Approve decision.
- **Admin** — intended for user/account oversight (turns out to be mostly read-only, see below).

Stack: **FastAPI** (Python) backend + **PostgreSQL** database + **React/Vite** frontend. There's also an `ai_ml/` research folder with offline-trained models and analysis scripts, separate from the live backend.

---

## 1. Executive Summary

**Current state:** This is a substantially built, unusually *honest* codebase — instead of faking functionality, it labels its own limitations directly in the UI (examples actually found in the code: *"no dedicated escalations endpoint exists yet,"* *"no SLA target is configured,"* *"research prototype, not NLI"*). The core pipeline — customer submits → surveyor inspects → AI runs advisory checks → officer decides → status becomes consistent everywhere — works in code and is backed by real automated tests.

The two biggest gaps: (1) the **Admin Portal** is almost entirely read-only dressing over other roles' data, and (2) **nothing in this audit was verified by actually clicking through the running app in a browser** — every "verified working" claim below comes from reading code and running automated tests, not from watching the UI behave.

- **Functional implementation: ~82%**
- **Verification/readiness: ~60%**

(see Section 8 for how these numbers were calculated — they are not the same thing: a feature can be fully built but barely tested, or thinly built but well tested.)

### Top 5 blockers

1. **No manual/browser end-to-end verification has ever been performed.** Every "it works" claim is from code + automated tests.
2. **RFI (Request for Information) / Escalations have no backend at all** — the pages exist and explicitly say so.
3. **Admin Portal cannot actually manage anything** — no create/edit/disable user, no role change, no config. It's a dashboard over other roles' read endpoints.
4. **AI/ML is entirely rule-based/deterministic in the live path.** Two real trained models exist as files on disk but the backend never loads them.
5. **No CI pipeline, no backup/recovery docs**, and the local dev secret key is weaker than the app's own security policy requires (harmless in development, must be fixed before any real deployment).

### Is it demo-ready?

**Yes**, for a guided walkthrough on the developer's own machine with the existing demo data — the core claim lifecycle is real and tested. **Not yet** ready for unattended or production deployment.

---

## 2. Module Completion Table

| Module | Status | Est. completion | Main evidence | Main gaps |
|---|---|---:|---|---|
| Customer Portal | Implemented & verified | 90% | Claim/document routers; identity-document linkage confirmed live in the database | No self-registration (accounts are pre-provisioned/seeded, by design) |
| Surveyor Portal | Implemented & verified | 95% | Evidence capture, GPS+map location picker, vehicle damage editing, photo keep/delete — 50+ passing tests added this engagement | Nothing significant found |
| Claims Officer Portal | Implemented & verified | 85% | Decision recording, locking, status consistency — 31 passing tests | RFI/Escalations missing; fraud/AI pages are thin |
| Admin Portal | Partially implemented | 25% | Exactly 2 real backend endpoints, both read-only (`GET /admin/users`, `GET /admin/users/{id}`) | No user/role/config management backend exists |
| Database & relationships | Implemented & verified | 95% | 16 tables, 2 migrations, live schema confirmed to match the code, zero orphaned records found | Database is near-empty — only one fully real demo claim exists right now |
| Document/Evidence storage | Implemented & verified | 95% | Filenames are sanitized and paths are checked to never escape the storage folder, in both the document and evidence storage code | None found |
| AI/ML modules | Partially implemented | 55% | Real OCR (actual text-recognition engine); real statistical "risk fusion" math ported from research code | One of the project's own 7 documented risk signals is permanently unavailable live; two real trained models sit unused on disk |
| Authentication & security | Implemented & verified | 90% | Industry-standard password hashing + signed tokens; role checks spot-checked across routers | The local development secret key is weaker than the app's own policy requires outside development mode |
| Testing | Extensive, mostly passing | — | 1022 backend tests (1017 pass), 401 frontend tests (401 pass) | No automated browser/end-to-end test suite |
| Deployment & documentation | Implemented, dev-only | 60% | Thorough setup README, example environment file covers everything needed | No automated build/test pipeline, no backup/recovery instructions |

---

## 3. End-to-End Workflow — Did We Actually Trace It?

The task description lists 23 steps from "a customer exists in the database" through "the claim is closed and the customer sees the correct result." Every one of them was traced through real code and, where possible, confirmed by an automated test. The three steps worth calling out specifically:

- **Steps 20–22 (status becomes consistent, claim leaves the queue, customer sees the right result)** were actually **broken** until a fix made earlier in this engagement: a rejected claim used to stay stuck showing "Under Review" forever, even though the officer had already decided it. This has been fixed and is now covered by new tests.
- **Step 17 (officer requests more information)** is the one real missing link — the page exists, but it openly states there's no backend behind it yet.
- **Step 15 (AI analysis)** works, but only in the "advisory checklist" sense described in Section 4 below — never as a model making a decision on its own.

Every other step (claim creation, document upload, surveyor assignment, evidence capture with GPS/map fallback, vehicle damage recording, photo keep/delete, submission locking, survey report generation, decision locking, audit logging) was confirmed present and backed by passing tests.

---

## 4. AI/ML — What's Really "AI" Here?

This is the section worth reading slowly if you're trying to learn how to evaluate an "AI-powered" claims system honestly — because the honest answer is: **almost none of it is a trained machine-learning model making predictions in the live app.**

| Module | Is it a trained ML model? | What it actually is |
|---|---|---|
| Document OCR | No model, but a real OCR *engine* (PyMuPDF + Tesseract) | Genuine text extraction from scanned documents |
| "Risk fusion" scoring (fraud/claim-pattern signals) | **No** — it's deterministic statistics ported from the research code, not a trained classifier | 6 of the project's own 7 documented signal types can be computed from live data; the 7th (a rule-based fraud score) is permanently marked "unavailable" rather than faked |
| Two trained models that *do* exist (`random_forest_fraud_label.pkl`, `logistic_regression_fraud_label.pkl`) | **Yes, genuinely trained** | **Never loaded by the live backend** — they exist only as offline research artifacts |
| Document/accident "consistency" checks | No | Keyword and regex matching, explicitly documented in the code as "not NLI, not a confidence score" |
| "Semantic consistency" check | No | The code itself calls this a "research prototype" with no NLP/embedding library involved |
| Evidence duplicate-photo detection | No | Exact file hashing + a classic perceptual-hashing algorithm — not fraud detection |
| Evidence photo-quality check | No | Basic image statistics (brightness/contrast) via a standard image library |
| Repair-estimate sanity checks | No | Plain arithmetic comparisons between numbers already in the database |

**The one thing that's consistently true and worth praising:** nothing here can *decide* a claim. Every AI/ML-flavored module is read-only and advisory — the Claims Officer is always the one who actually approves or rejects, and the code structurally cannot let an AI output silently become the final decision. This "human stays in the loop" rule is enforced in the code, not just promised in a comment.

---

## 5. Security Review Summary

No critical vulnerabilities were found. What was checked and confirmed correct:
- Passwords are hashed properly (never stored in plain text).
- Login tokens are signed and checked for expiry and required fields.
- Every role's permissions were spot-checked across multiple backend routers — a customer genuinely cannot see another customer's claims, a surveyor genuinely cannot touch another surveyor's evidence, etc.
- File uploads are checked by their actual content, not just their claimed file type, and storage paths are defended against path-traversal tricks.
- No passwords, tokens, or private document content were found leaking into log files.

What needs attention before any real deployment (not urgent for a local demo):
- **Medium:** the local development secret key is weaker than the app's own built-in security policy requires outside development mode. The code already refuses to start with a weak key in production — this just needs a real key generated when that day comes.
- **Medium:** there's no automated test pipeline and no documented backup/restore procedure.
- **Low:** a couple of minor configuration details (CORS settings, one missing test file for the Admin endpoints) are worth a quick look.

---

## 6. Test Results (exact numbers)

| Check | Command | Result |
|---|---|---|
| Backend tests | `pytest tests/ -q` | **1017 passed, 5 failed** (out of 1022) |
| Frontend tests | `npx vitest run` | **401 passed, 0 failed** (52 test files) |
| Lint | `npx oxlint` | Clean (3 long-standing minor warnings, unrelated to this audit) |
| Production build | `npx vite build` | Succeeds |
| Database migration check | `alembic current`/`heads` | Database is fully up to date with the code, no mismatch found |

The 5 backend test failures were independently re-confirmed as pre-existing (not caused by anything new) — two are about a feature that happens to assume "today" is earlier than it currently is on the calendar, and three are narrower edge cases in image-quality/consistency checks.

---

## 7. Completion Percentages — How They Were Calculated

Two separate numbers are reported, on purpose, because they answer different questions:

**A. Functional implementation (~82%)** — "how much of the required functionality actually exists and works?" This is a weighted average across every module (Customer/Surveyor/Officer/Admin portals, database, storage, AI/ML, security, deployment setup), weighting the Surveyor and Officer workflows highest since they're the heart of the product, and Admin lowest since it's the smallest, least-built piece.

**B. Verification/readiness (~60%)** — "how much of that has actually been proven to work, beyond just existing?" This weights automated test pass rates heavily, but is pulled down hard by one honest fact: **no one has yet clicked through the running app in a real browser as part of this audit.** Automated tests prove the backend logic works in isolation; they don't prove the actual user experience is smooth.

Both numbers are this auditor's best evidence-based estimate, not a certified score — and the single fastest way to improve the second number is described next.

---

## 8. What Should Happen Next (Priority Order)

**P0 — Fix before any real deployment**
1. Replace the local development secret key with a strong one before running outside development mode.
2. Double-check the CORS (cross-origin request) configuration isn't more permissive than intended.

**P1 — Needed for a complete demonstration**
3. Decide whether "Request for Information" and "Escalations" are in scope — if yes, they need a real backend built (currently zero).
4. Add a few more realistic demo claims to the database — right now there's essentially only one fully real claim to show.
5. **Actually walk through the whole app in a browser as every role, start to finish.** This is the single most valuable and cheapest next step — nothing in this audit replaces a human watching the real thing work.

**P2 — AI/ML improvements**
6. Either connect the two trained models that already exist into the live app, or clearly document that they're research-only so nobody is confused later.
7. Extend the risk-scoring lookup so it can say something about a brand-new claim, not only the original research dataset's claims.

**P3 — Polish**
8. Add an automated test/build pipeline that runs on every change.
9. Write a short backup/restore guide.
10. Fix the two tests that are tied to a specific calendar date.

---

## 9. Single Highest-Priority Recommendation

**Sit down and manually click through the entire customer → surveyor → officer flow in a real browser, start to finish, as one continuous session.** Everything else in this report — including every "verified working" row — comes from reading code and running automated tests, never from watching the actual app behave for a real person. That one afternoon of manual testing will tell you more about true demo-readiness than any further code auditing could.

---

*This report was produced by static code inspection, real (read-only) database queries, and actually running the existing automated test suites — not by assuming an earlier feature write-up still reflects the current code. Nothing in the project was modified, deleted, or reset to produce it.*
