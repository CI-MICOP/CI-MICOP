# CI-MICOP Progress Report

**Date:** 8 October 2026
**Covers:** work done on 7 and 8 October 2026, continuing from the project handoff.

## 1. Summary

- Steps 1 to 11 of the handoff roadmap are now done.
- Steps 12 (Docker) and 13 (final report) are not started.
- A new Admin area was built in the frontend.
- The app can now read scanned documents on the development laptop.
- All automated tests pass.
- Several decisions are waiting for the team. They are listed in Section 8.

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
| 11 | Full testing and security review | Done, with 6 improvements to do later |
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
| Backend | 629 tests: 627 pass, 2 skip themselves on purpose (see Section 5) |
| Frontend | 169 of 169 pass; the build works |
| AI/ML research code | 101 of 101 pass |

109 of the backend tests are new security tests written in this step.

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

**To do later (6 improvements).** None of these stops the app from working
today. They should be done before the app goes online.

1. **Old packages with known security holes.** Five backend packages are
   out of date, including the ones that handle login and file uploads. The
   newer versions were tried in a separate copy: all tests pass and no
   known holes remain. Most of the holes are in features this project does
   not use. The ones that matter could let someone slow down or overload
   the login and upload pages; none lets anyone read data.
2. **No limit on wrong passwords.** Someone could keep guessing passwords
   forever. The app counts wrong tries but does nothing with the count.
3. **Uploaded files could end up on GitHub.** The folders that hold
   customer documents and photos are not excluded from git.
4. **Two weak login settings.** If the secret key were missing from the
   settings file, the app would quietly use the word "changeme". It also
   accepts a login token that has no expiry date.
5. **The API's help pages are open to everyone.** Fine during development,
   not once the app is online.
6. **Some frontend developer tools have known holes.** These are only used
   to build and test the app, not in what users see.

**What was not checked.** Nobody attacked a running copy of the app; this
was code reading plus automated tests. No screen was checked by hand in a
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

## 7. Other Work

- The missing dataset and saved model results arrived from the team and
  were added to the local project. One test that used to fail because of
  the missing files now passes.
- All 13 roadmap steps were checked one by one against the real code.
- Steps 7, 9 and 10 were saved and pushed to GitHub.

## 8. Decisions Waiting for the Team

**Repair-estimate checks (Step 10)**

1. Check 3 (replaced parts) points at 41% of practice claims. Keep it,
   make it stricter, or show it as information only?
2. Checks 5 and 6 rest on weak limits. Keep them as "Review" checks, or
   show them as information only?
3. Add a check for a bill dated very long after the accident?

**Security (Step 11)**

4. Update the five old packages? (Tried separately: all tests pass.)
5. Exclude the upload folders from git?
6. Add a limit on wrong passwords, and how many tries?
7. Tighten the two login settings?

## 9. Not Yet Saved to GitHub

This work exists only on the development laptop for now:

- the Step 11 security tests and report;
- the Admin area;
- this report.

## 10. What Is Left

- **Step 12: Docker and deployment.** The three Docker files are still
  empty placeholders, and Docker is not installed on the laptop.
- **Step 13: Final documentation and report.**
- **A check by hand in a browser** of the new screens.
- **Smaller frontend gaps:** some sidebar links for Customer, Surveyor and
  Officer still open a "Coming soon" page.
