# CI-MICOP Progress Report

**Date:** 8 October 2026
**Covers:** work done on 7 and 8 October 2026, continuing from the project handoff.

## 1. Summary

- Steps 1 to 11 of the handoff roadmap are now done.
- Steps 12 (Docker) and 13 (final report) are not started.
- A new Admin area was built in the frontend.
- The app can now read scanned documents on the development laptop.
- All automated tests pass, including a full retest on a fresh copy
  (Section 7).
- Several decisions are waiting for the team. They are listed in Section 9.

## 2. Where the Roadmap Stands

| # | Roadmap step | Status |
|---|---|---|
| 1 | Save the semantic consistency prototype | Done |
| 2 | Test it on a controlled set of documents | Done |
| 3 | Officer screen for consistency findings | Done |
| 4 | Detect copied or reused evidence photos | Done |
| 5 | Information quality and document mismatch | Done |
| 6 | Stronger date, time, location and FIR checks | Done |
| 7 | Decide whether a real NLI model is needed | Done (decision: not now) |
| 8 | Feed tested checks into the risk score | Done |
| 9 | Decide whether to run the fraud model live | Done (decision: not now) |
| 10 | Repair-estimate checks | Done, with 3 decisions open |
| 11 | Full testing and security review | Done; 3 of 6 improvements done, 3 to do later |
| 12 | Docker and deployment | Not started |
| 13 | Final documentation and report | Not started |

## 3. Step 10: Repair-Estimate Checks

**What it is.** A new "Check Estimates" button on the Claims Officer's
Estimate Analysis screen. It compares each repair bill with the other
records of the same claim and says "Review" when something looks unusual.
It never decides anything and never uses the word "fraud".

**The six checks.** The tool says "Review" when:

1. The bill is dated before the accident.
2. The bill is much larger than the amount claimed (more than 2.97 times).
3. The bill replaces parts, but the surveyor wrote "repair only".
4. The final repair cost is more than 15.4% above the bill.
5. The bill is more than 5.34 times the surveyor's damage cost.
6. The repair took more than 12 days longer than planned.

If a claim has two bills, the tool also shows the gap between them.

**Where the limits come from.** The limits in checks 2, 4, 5 and 6 are not
guesses. They were measured from the 654 practice claims: each limit is the
value that 9 out of 10 practice claims stay under.

**What the practice data showed.**

- When the six checks are run on the practice claims themselves, 62% of
  claims get at least one "Review". That is too many to be useful.
- Most of this comes from check 3, which alone points at 41% of claims.
- Checks 5 and 6 are weak. In the practice data the numbers they compare
  have no link to each other, so their limits only show what is common in
  made-up data.
- Check 4 is solid: the cost and the bill move closely together.

The practice data is computer-generated, which probably explains this. Real
claims may behave differently.

Full details: `REPAIR_ESTIMATE_CHECKS.md`.

## 4. Step 11: Testing and Security Review

**Test results.**

| Tests | Result |
|---|---|
| Backend | 634 tests: 632 pass, 2 skip themselves on purpose (see Section 5) |
| Frontend | 169 of 169 pass; the build works |
| AI/ML research code | 101 of 101 pass |

114 of the backend tests are new security tests: 109 from the review and 5
for the wrong-password limit added afterwards.

**What was checked and is safe.**

- All 35 private parts of the API refuse anyone who is not logged in.
- Each role is kept out of the other roles' areas.
- Fake, expired or changed login tokens are refused.
- A suspended account is blocked at once.
- Passwords are stored scrambled and are never sent back.
- Uploaded files are checked for type, size and unsafe names.
- Only the Claims Officer's own action can save a final decision. No AI or
  checking code can.
- No password or secret file is stored in git.

**Improvements (6).** Three are done; three are to do later. None of these stops the app from working
today. They should be done before the app goes online.

1. **Old packages with known security holes (done).** Five backend packages
   were out of date, including the ones that handle login and file uploads.
   They are now updated: all tests pass and no known holes remain. Most of
   the holes were in features this project does not use. The ones that
   mattered could let someone slow down or overload the login and upload
   pages; none let anyone read data. Each teammate must run
   `pip install -r backend/requirements.txt` once to get the new versions.
2. **No limit on wrong passwords (done).** Someone could keep guessing
   passwords forever. Now, after 5 wrong passwords in a row, that person
   must wait 15 minutes before trying again. Both numbers are easy to
   change. The count is kept in memory, so it is forgotten if the server
   restarts.
3. **Uploaded files could end up on GitHub (done).** The folders that hold
   customer documents and photos were not excluded from git. They are now.
4. **Two weak login settings.** If the secret key were missing from the
   settings file, the app would quietly use the word "changeme". It also
   accepts a login token that has no expiry date.
5. **The API's help pages are open to everyone.** Fine during development,
   not once the app is online.
6. **Some frontend developer tools have known holes.** These are only used
   to build and test the app, not in what users see.

**What was not checked.** Nobody attacked a running copy of the app; this
was code reading plus automated tests. The screens were later opened in an automated
browser.

Full details: `SECURITY_AND_REGRESSION_REVIEW.md`.

## 5. Reading Scanned Documents

Before, the app could read normal PDFs but had never been tried on scans or
photos, because the program it needs (Tesseract OCR) was not installed.

- Tesseract 5.4.0 is now installed on the development laptop.
- Five test files were read: a PNG picture, a JPG picture, a picture-only
  PDF, and a tilted, blurry version of the picture and of the PDF.
- All five were read correctly, with about 95% reading confidence. The
  registration number, policy number, FIR number, date and place all came
  back exact.

**Limits.** The test files were made by the computer from clean printed
text. Real phone photos, handwriting and stamps are harder and were not
tested. Only English is installed.

**Note for the team.** Each person who wants this to work on their own
laptop must install Tesseract too. Two backend tests cover the "Tesseract
is not installed" case, so they skip themselves on a laptop where it is
installed.

## 6. New Admin Area

Before, the Admin role had only a placeholder page. It now has these
working pages:

| Page | What it shows |
|---|---|
| Dashboard | Number of accounts, active and not active, number of claims, users by role, claims by status, and quick links |
| Users | Every account, with search, a role filter and 25 per page |
| User details | All the details of one account |
| Roles & Permissions | What each of the four roles can and cannot do, and how many accounts each role has |
| System Reports | Users by role and status; claims by status, decision and type; total amount claimed |
| Audit Logs | The decision history of a chosen claim |
| Profile | The admin's own account details |

**Things to know.**

- Everything is read-only. The admin can look, but cannot create, change or
  disable an account, because the backend has no feature for that yet.
- Every number is counted from real data. Nothing is invented.
- Claim numbers cover at most 200 claims, because that is the most the
  backend sends at once. The page says so when the limit is reached.
- The "Roles & Permissions" text was written by hand from the rules in the
  backend code. If those rules change, the page must be updated.
- No backend code was changed for the Admin area.
- The pages were checked by 9 new automated tests, not by hand in a browser.

## 7. Full Retest on a Fresh Copy

To be sure the next person can start without trouble, everything was
tested again on 8 October from a new download of the project from GitHub,
with newly installed packages and a brand-new empty database.

| What was tested | Result |
|---|---|
| Fresh download from GitHub | Complete; nothing missing |
| Install of all packages | Works, no conflicts |
| Building the 15 tables on an empty database | Works |
| Backend tests | 627 pass, 2 skip on purpose |
| Frontend tests | 169 of 169 pass; the build works |
| AI/ML tests | 101 of 101 pass |
| Loading the development data | Works |
| Live test of the real server | 37 of 37 checks pass |
| Screens opened in a real browser (Edge) | 41 of 41 pages open with no error |

The live test started the real server and tried the main actions of each
role: Customer, Surveyor, Claims Officer and Admin. A scanned picture was
uploaded and read through the real API. Each role was refused in the other
roles' areas. After every analysis run, the claim's decision and audit
history were unchanged.

The browser check logged in as each of the four roles in a hidden Edge
window and opened every main page: 10 Customer, 10 Surveyor, 15 Claims
Officer and 6 Admin pages. No page showed an error, no request failed,
and the "Check Estimates" button returned its result. It was run on both
the development server and the built (production) version. The retest
was repeated after the wrong-password limit was added, using a settings
file made from `.env.example` and no Tesseract setting: 634 backend tests
pass with none skipped.

One gap was found: the setup guide (`README.md`) did not explain how to
load the development data and logins. Sections were added to it for the
development data, Tesseract, the frontend tests and the AI/ML code.

## 8. Other Work

- The missing dataset and saved model results arrived from the team and
  were added to the local project. One test that used to fail because of
  the missing files now passes.
- All 13 roadmap steps were checked one by one against the real code.
- All of this work was saved and pushed to GitHub (see Section 10).

## 9. Decisions Waiting for the Team

**Repair-estimate checks (Step 10)**

1. Check 3 (replaced parts) points at 41% of practice claims. Keep it,
   make it stricter, or show it as information only?
2. Checks 5 and 6 rest on weak limits. Keep them as "Review" checks, or
   show them as information only?
3. Add a check for a bill dated very long after the accident?

**Security (Step 11)**

4. The limit on wrong passwords is set to 5 tries and 15 minutes. Keep
   these numbers or change them?
5. Should customers see the MATCH / MISMATCH result on their documents?

## 10. Saved to GitHub

All the work in this report is on GitHub (branch `master`). To get it, run
`git pull origin master`, then `pip install -r backend/requirements.txt`
once, because the backend packages changed.

- Steps 7, 9 and 10: commits `98aa693` and `ab2b479`.
- Step 11 security tests and report: commit `041cfa6`.
- The Admin area: commit `3f34730`.
- Package update and upload folders excluded from git: commit `e1651ca`.
- Setup guide additions and the retest results: commit `9a62169`.
- Limit on wrong passwords: commit `f535068`.
- Browser check recorded in the reports: commit `482d4ca`.

## 11. What Is To Do Later

**Roadmap steps not started**

- **Step 12: Docker and deployment.** The three Docker files are still
  empty placeholders, and Docker is not installed on the laptop. Docker
  packs the app, its packages and the database into boxes that run the
  same way on any computer.
- **Step 13: Final documentation and report.**

**Security improvements**

- Tighten two login settings: refuse to start with the default secret key,
  and refuse login tokens that have no expiry date.
- Close the API's help pages when the app goes online.
- Update the frontend developer tools.

**Frontend gaps**

- Some sidebar links for Customer, Surveyor and Officer still open a
  "Coming soon" page.
- Notifications, Escalations and RFI show "not available", because the
  backend has no such feature yet.
- The Admin area is read-only.

**Checks not done yet**

- The screens were opened by an automated browser, not by a person. Forms
  were not filled in by hand, except one button ("Check Estimates").
- Scanned-document reading was tested on computer-made images only.
- Everything was run on one Windows laptop.
