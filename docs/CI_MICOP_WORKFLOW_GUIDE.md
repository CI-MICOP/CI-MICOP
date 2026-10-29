# CI-MICOP — How The Whole System Actually Works (A Learning Guide)

**What this document is:** A guided walkthrough of CI-MICOP's architecture and its complete claim lifecycle, written so someone who has never seen this codebase can learn *how a real full-stack claims system is put together* — not just what buttons exist, but which frontend component calls which backend endpoint, which database tables get touched, and why the project made the design choices it did.

**How to read it:** Start with Section 1 (the big picture), then follow Section 3 (the full story of one claim, start to finish) — that's the part that teaches the most. Sections 4–5 are reference material to come back to.

This is a companion to [`CI_MICOP_PROJECT_AUDIT_REPORT.md`](./CI_MICOP_PROJECT_AUDIT_REPORT.md) (which grades *how complete and tested* everything is). This document instead explains *how it works*.

---

## 1. The Big Picture

```
 ┌─────────────────────┐        HTTPS (JSON over REST)        ┌──────────────────────┐
 │   React / Vite       │ ───────────────────────────────────▶ │   FastAPI (Python)   │
 │   frontend            │ ◀─────────────────────────────────── │   backend             │
 │   (runs in browser)   │         JWT in Authorization header  │   (runs on a server)  │
 └─────────────────────┘                                       └───────────┬──────────┘
                                                                            │
                                                     ┌──────────────────────┼──────────────────────┐
                                                     ▼                      ▼                      ▼
                                           ┌──────────────────┐  ┌──────────────────┐   ┌──────────────────┐
                                           │   PostgreSQL      │  │  Local disk       │   │  ai_ml/ research  │
                                           │   (claims, users,  │  │  storage           │   │  code (offline,   │
                                           │   documents rows,  │  │  (actual document   │   │  not called by    │
                                           │   evidence rows…)  │  │  & photo files)     │   │  the live app)    │
                                           └──────────────────┘  └──────────────────┘   └──────────────────┘
```

**Three layers, and a rule worth remembering:** the database only ever stores *metadata* (who, what, when, status) — the actual document and photo *files* live on disk, referenced by a server-generated path. The browser never sees a raw file path; every file is served through an authenticated API endpoint that re-checks permission on every single request. This is why "can user X see user Y's photo by guessing a URL" is a *no* throughout this project — there is no public URL for a private file at all.

### How a request proves who you are (authentication)

1. You log in with a username/password on the **Login page**.
2. The backend checks your password (hashed, never stored in plain text) and, if correct, hands back a **JWT** — a signed, tamper-proof token that says "this is user X, with role Y, valid until time Z."
3. The frontend stores that token and attaches it to every later request (`Authorization: Bearer <token>`).
4. Every protected backend endpoint runs the token through the same check: decode it, confirm it hasn't expired, look up the user, confirm their account is still active. Only then does it ask "and does *this* role have permission to do *this specific thing*?"
5. That last question is answered by small, reusable "dependency" functions like `require_roles("Claims Officer", "Admin")` or `require_surveyor_employee_id` — every router in the backend declares which of these it needs, and the authorization logic itself lives in exactly one place (`backend/app/api/v1/deps.py`), not copy-pasted everywhere.

### How a request proves you're allowed to touch *this specific claim*

Knowing your role isn't enough — a Customer needs to be blocked from even their *own* role's generic claim-list endpoint showing someone else's claim. The project solves this with **ownership checks** that run on every request, not just once at login:
- Customer → can only see claims where `Claim.Customer_ID` matches their own ID.
- Surveyor → can only act on a claim if a `surveyor_inspections` row exists assigning *them* to it.
- Claims Officer / Admin → can see everything (they're the claim-processing roles).

---

## 2. The Four Portals, in One Sentence Each

| Role | What they do | Where their code lives |
|---|---|---|
| **Customer** | Files a claim, uploads documents/photos, tracks status | `frontend/src/pages/customer/`, backend `claims.py` + `documents.py` |
| **Surveyor** | Physically inspects the vehicle, photographs evidence with location, records damage, submits a survey report | `frontend/src/pages/surveyor/`, backend `surveyor.py` |
| **Claims Officer** | Reviews everything (documents, evidence, AI advisory checks) and makes the final Approve/Reject call | `frontend/src/pages/officer/`, backend `officer.py` |
| **Admin** | (Mostly) views aggregated data across all claims and users — see the audit report for why it can't actually *manage* much yet | `frontend/src/pages/admin/`, backend `admin.py` |

---

## 3. The Full Story of One Claim, Start to Finish

This is the part worth reading slowly — it's the same story the audit report's "workflow matrix" tells, but explained like a narrative instead of a table, so you can actually follow *why* each step exists.

### Step 1 — Before anything happens: the customer already exists

There's no public "sign up" page in this project — customer accounts, their vehicles, and their insurance policies are set up ahead of time (by a seed script, in real life this would be done when someone buys a policy). This is a deliberate scope decision, not a bug: the project is about the *claims* workflow, not insurance sales.

### Step 2 — Customer logs in

`LoginPage.jsx` → `POST /auth/login` → backend checks the password hash → returns a JWT → frontend stores it and redirects to the Customer Dashboard.

### Step 3 — Customer files a new claim

`NewClaimPage.jsx` collects accident details (date, place, description, which vehicle) and calls `POST /claims`. The backend (`claim_creation.py`) does something worth noting: **it never trusts the customer's own ID from the request body** — it always re-derives "who is making this claim" from the JWT itself. So even if the browser's JavaScript were tampered with, you still couldn't file a claim pretending to be someone else. A new row is written to the `claims` table, and a matching `accidents` row records the accident details.

### Step 4 — Customer uploads documents and photos

`UploadDocumentsPage.jsx` sends each file to `document_upload.py`. The backend doesn't trust the file's claimed type (e.g. "this is a JPEG") — it reads the actual bytes and checks the real file signature. This stops someone from renaming a dangerous file to `photo.jpg` and having the server believe it.

There's a second, separate category of document worth knowing about: **identity documents** (RC, Driving Licence, Insurance Policy copy). These belong to the *customer*, not to any one claim — so the `documents` table has a `Claim_ID` column that's allowed to be empty (`nullable`). A document with no `Claim_ID` is a permanent identity record the customer can view any time; a document *with* a `Claim_ID` belongs to that one claim only. This two-in-one design avoids needing a second table.

### Step 5 — The claim shows up for the Claims Officer

The Officer's **Work Queue** page asks the backend for claims where `Claim_Status = "Under Review"`. Nothing special happens here yet — it's just a filtered list.

### Step 6 — A Surveyor gets assigned

An officer assigns a surveyor to the claim. This creates a `surveyor_inspections` row linking (claim, surveyor, scheduled date). **This one row is the entire basis of "is this surveyor allowed to touch this claim"** for every later surveyor action — there's no separate "assignment" table to keep in sync.

### Step 7 — The surveyor opens the claim

The Surveyor Portal re-checks the assignment and the scheduled date on *every single request*, not just when the page first loads — so even if a surveyor kept an old browser tab open, they couldn't act on a claim before its scheduled inspection date, or after being reassigned away from it.

A nice detail here: the surveyor can see the customer's RC/Driving Licence/Policy documents for context, but **only those three types** — a document allow-list in `surveyor_documents.py` means even a direct, hand-crafted request for some other document type gets refused.

### Step 8 — The surveyor photographs evidence (and here's an interesting bug-fix story)

The surveyor uses the in-app camera (never a gallery upload — this matters, see below) to take photos. For each photo, the browser also tries to get a GPS location. Here's the problem this project ran into, and how it solved it:

> **The problem:** GPS often doesn't work well *indoors* — a surveyor inspecting a car in a garage might get a location reading that's off by hundreds of metres, or no reading at all. The original version of this feature simply *refused* to save the photo if GPS accuracy wasn't good enough, which meant indoor inspections could get stuck.
>
> **The fix:** the surveyor can now tap "Choose location on map" and manually pick the spot on an interactive map (built with the free Leaflet/OpenStreetMap libraries, with address search). But — and this is the important design principle — **a manually-picked location is never allowed to pretend it's a GPS reading.** It's stored and labelled "Map-selected — GPS not verified," permanently and visibly distinct from "GPS verified," everywhere it's shown, including to the Claims Officer later. The system gained flexibility without being allowed to lie about how confident it actually is.

The photo itself and its GPS/map metadata are stored in two places for two different reasons: the *photo file* goes on disk, and a small *JSON metadata record* sits right next to it (not in the database — the database table for evidence never had columns for "who/where/how was this captured," so the project added a sidecar file instead of changing the database). That metadata record is written once and checksummed against the photo — if someone tampered with the photo file afterward, the mismatch would be detected and the record would simply stop being trusted.

### Step 9 — The surveyor reviews their photos before finishing

Before the survey report is submitted, the surveyor can review each photo: explicitly mark it "Kept" (a review decision, not proof the photo is genuine), or delete it entirely with a confirmation dialog. Deleting is permanent-but-safe: the database row is removed *first*, and only once that genuinely succeeds does the actual photo file get cleaned up from disk — so a crash partway through can never leave a "ghost" database row pointing at a missing file, or vice versa.

### Step 10 — The surveyor records vehicle damage, then submits

Damage observations get their own database rows, editable until submission. Once the surveyor submits the survey report, the backend flips one flag (`Survey_Report_Submitted = true`) — and from that exact moment, *every* write-path for that inspection (editing damage, keeping/deleting photos, changing findings) checks that flag first and refuses with an error if it's already true. This lock is enforced in the backend, which matters: a clever user poking the API directly (not just the pretty frontend buttons) still can't bypass it.

### Step 11 — The AI modules run their checks (advisory only — this is the key idea)

The Claims Officer can trigger several automated checks on the claim: do the uploaded documents' details match each other (registration number, policy number)? Do two photos look suspiciously identical? Is the repair estimate's cost ratio unusual? **None of these are a trained machine-learning model deciding anything** — they're deterministic rule-based checks (pattern matching, basic image statistics, simple arithmetic), and the project is refreshingly upfront about this in its own code comments rather than dressing it up. More importantly: **not one of these checks has any way to write to the claim's final decision.** They only ever produce information for a human to read. This "human stays in charge" rule is a structural guarantee in the code, not just a policy someone promised to follow.

### Step 12 — The Claims Officer makes the decision

The officer picks Approved / Rejected / Partially Approved, writes a reason, and (if approving) an amount. The backend:
- Locks the specific claim row for the duration of the request, so two officers racing to decide the same claim at the same moment can't both succeed (one wins, one gets a clear "already decided" error).
- Writes the decision permanently — there is no "undo" or "re-decide" button anywhere, by design. Once decided, it's final.
- Creates an audit record (who decided, when, with what AI information available at the time, if any).

### Step 13 — The claim's status finally agrees with its decision (this was a real bug, now fixed)

> **The bug this project actually had, and fixed during this engagement:** the claim's visible status ("Under Review" / "Completed") used to only update correctly for *Approved* decisions. A *Rejected* claim's `Final_Decision` field correctly said "Rejected," but its `Claim_Status` field stayed stuck at "Under Review" forever — so the customer's own claim page showed the contradictory combination of "Status: Under Review" next to "Final Decision: Rejected."
>
> **The lesson here:** a claims system has more than one field describing "how far along is this," and it's easy for them to drift apart if only one of them gets updated in the fix for the original feature. The real fix was recognising that *any* final decision — approve, reject, or partial — means the officer is *done* with this claim, so the status should always become "Completed," while the *outcome* (approved vs rejected) stays recorded separately in `Final_Decision`. Status answers "is this still being worked on?"; decision answers "what was decided?" They're two different questions and shouldn't be merged into one field.

Because the Customer Portal, the Officer's "Work Queue," and the "All Claims" list all read the exact same `Claim_Status` field from the same database row — fixing it in one place (the decision-recording code) fixed all three screens at once. That's a sign of a well-structured backend: there was exactly one place that needed to change.

### Step 14 — The customer sees the final result

The customer refreshes (or logs back in later) and their Claim Details page shows: Claim Status = Completed, Current Stage = Completed, Final Decision = Rejected (or Approved, with the approved amount) — all consistent, because there's no caching anywhere pretending the old value is still current. Every page re-fetches from the same source of truth every time.

---

## 4. A Few Design Patterns Worth Learning From

- **Never trust the client for identity.** Every "who is doing this" value (customer ID, surveyor ID, officer ID) comes from the verified JWT or from a database relationship — never from a field the browser could edit.
- **Derive status, don't let the client set it.** A surveyor's photo location status ("GPS verified" vs "Map-selected") is computed by the *server* from the raw coordinates/accuracy it receives — the client has no "status" field to submit directly, so it's structurally impossible to fake a verified reading.
- **Honest placeholders instead of fake confidence.** Throughout the codebase, when real information genuinely isn't available yet, the system stores an explicit, clearly-labelled placeholder ("Pending," "Not Escalated," "Not analysed yet") instead of inventing a plausible-looking fake value.
- **Lock state changes with a database-level lock, not just a frontend disabled button.** The decision-finalization step and the evidence-submission lock are both enforced with real database row locks and server-side checks — a disabled button in the UI is just a courtesy; the actual safety net is in the backend.
- **Delete order matters for safety.** When deleting something that has both a database row and a file on disk, delete the database row first (and only clean up the file after that genuinely succeeds) — that way a failure partway through never leaves a database record pointing at nothing.
- **One ownership check, reused everywhere**, rather than re-implementing "does this user own this claim" logic separately on every page's backend endpoint.

---

## 5. Where To Go Digging Yourself

If you want to trace any of the above yourself:
- Backend entry point: `backend/app/main.py`
- All backend routes grouped by role: `backend/app/api/v1/routers/` (`claims.py`, `surveyor.py`, `officer.py`, `admin.py`, `documents.py`)
- Business logic (the interesting part): `backend/app/services/`
- Database table definitions: `backend/app/db_models/`
- Frontend pages grouped by role: `frontend/src/pages/`
- Frontend API calls grouped by role: `frontend/src/services/`
- Automated tests (a great way to see exactly what behaviour is guaranteed): `backend/tests/`, `frontend/src/**/__tests__/`

For the "how complete and tested is each part" scorecard, see [`CI_MICOP_PROJECT_AUDIT_REPORT.md`](./CI_MICOP_PROJECT_AUDIT_REPORT.md) in this same folder.
