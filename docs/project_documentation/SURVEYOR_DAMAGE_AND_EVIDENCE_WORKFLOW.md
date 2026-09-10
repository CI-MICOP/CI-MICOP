# Surveyor Vehicle Damage + Evidence Capture

Makes Vehicle Damage and Evidence genuinely persisted for the Surveyor portal. Before this task, `VehicleDamagePage` and `EvidencePage` were explicitly read-only ("There is no existing backend endpoint for a surveyor to create or edit..."). Both are now real, backed by two new Surveyor-only endpoints.

## 1. Vehicle Damage workflow

`POST /api/v1/surveyor/vehicle-damage` (JSON body). A surveyor submits `Claim_ID` plus the fields they actually observed; the backend derives `Vehicle_ID` from the claim and generates `Damage_ID`, then persists one `vehicle_damage` row. `vehicle_damage` is one-to-many with claims (unchanged) - the surveyor can call this endpoint repeatedly to record multiple damaged parts (e.g. Bumper, then Headlight, then Bonnet), each becoming its own row. No update/delete endpoint was added - see Section 14.

## 2. Evidence workflow

`POST /api/v1/surveyor/evidence` (multipart/form-data: `claim_id`, `evidence_type`, `evidence_date`, `evidence_source`, `file`). Mirrors the Customer Document Upload workflow exactly: the file is saved to local disk, PostgreSQL stores only metadata, and the response never exposes a filesystem path.

## 3. RBAC

Both endpoints use `require_surveyor_employee_id` (added in Step 5.8.5) - JWT required, `Surveyor` role only (not Customer, not Claims Officer, not even Admin - this mirrors the existing inspection-creation endpoint's strictness, since these are surveyor field-observation actions, not general claim-processing actions). `Employee_ID` is resolved exclusively from the token.

## 4. Claim assignment requirement (reused, not reinvented)

Both endpoints call the same assignment check as inspection creation: a new `get_claim_assigned_to_surveyor_or_403(db, claim_id, employee_id)` helper added to `app/services/claim_access.py`, which wraps the existing `crud_claim.surveyor_is_assigned` (a `surveyor_inspections` row for (claim, surveyor) already establishes assignment - unchanged from Step 5.8.5). No new assignment table, column, or mechanism was created.

**This means the same limitation from Step 5.8.5 applies here unchanged: a brand-new customer-created claim has no surveyor assigned to it yet, so a surveyor cannot record damage or evidence for it until an inspection has been established for that (claim, surveyor) pair by some other means.** This was re-verified live in this task's manual test - the seeded, already-assigned `DEV-CLM-001` was used deliberately, per the task's own instruction not to attempt this against an unassigned claim.

## 5. Vehicle_ID derivation

`Vehicle_ID` is never accepted from the client. `create_vehicle_damage_for_surveyor` (in `app/services/vehicle_damage_creation.py`) reads it from the already-fetched, ownership-checked `Claim` row (`claim.Vehicle_ID`) and writes that value - any `Vehicle_ID` the client includes in the request body is a schema field pydantic doesn't even define, so it is silently ignored, not read. Verified by `test_supplied_vehicle_id_cannot_override_claim_vehicle_id`.

## 6. Damage_ID / Evidence_ID generation

Same convention as `Document_ID`/`Inspection_ID` from Steps 5.8.4/5.8.5: `DMG-YYYYMMDD-XXXXXX` / `EVD-YYYYMMDD-XXXXXX`, generated server-side (`crud/vehicle_damage.py::generate_damage_id`, `crud/evidence.py::generate_evidence_id`) and checked against the primary key before use.

## 7. File storage architecture (Evidence only - VehicleDamage has no file)

`app/services/evidence_storage.py` deliberately mirrors `app/services/document_storage.py`'s exact pattern and security properties as a **parallel module**, not a shared one:

- Same filename sanitization (`Path(name).name` to strip any directory component, then a whitelist regex `[^A-Za-z0-9._-]` to strip everything else) - defeats `../`, `..\`, and absolute-path traversal.
- Same server-controlled path shape: `infra/storage/evidence/<Claim_ID>/<Evidence_ID>_<sanitized_filename>`.
- Same belt-and-braces check that the resolved path never escapes the configured root.
- A separate config root, `EVIDENCE_STORAGE_ROOT` (defaults to `<repo root>/infra/storage/evidence`, next to `DOCUMENT_STORAGE_ROOT`), and a separate `EVIDENCE_MAX_UPLOAD_BYTES` (10 MB, same default as documents).

This is a deliberate, small duplication rather than refactoring `document_storage.py` into a shared module: it keeps the already-shipped, tested Customer Document Upload code untouched (per this task's "do not modify unrelated modules" instruction) while still using exactly the same conventions.

## 8. Validation

Inspected before writing any code - real values pulled directly from the approved dataset files:

| Table | Field | Real values (from `ai_ml/datasets/CI_MICOP_15_Tables_Complete/`) |
|---|---|---|
| `vehicle_damage` (654 rows) | `Damage_Type` | Side Damage, Rear Damage, Multiple Damage, Front Damage, Glass Damage, Engine Damage, Total Loss |
| | `Damage_Severity` | Minor, Moderate, Severe |
| | `Damage_Location` | Left, Right, Front, Rear, Multiple |
| | `Repair_or_Replace` | Repair, Replace |
| `evidence` (1301 rows) | `Evidence_Type` | Survey Photo, Damage Photo, Accident Photo |
| | `Evidence_Source` | Customer, Surveyor |
| | `Verification_Status` | Verified, Failed, **Pending** |

A `VehicleDamage` row records a *completed* observation (unlike an in-progress inspection) - every enum field must be a real value at creation time; there is no "Pending" placeholder option for damage fields, since the surveyor is asserting they actually observed this. `Damaged_Part` and `Damage_Description` are free text (required, non-blank after trimming, capped at 50/1000 characters respectively - the real dataset's longest values are 14/31 characters, so these caps are generous headroom, not a tight fit to historical data). `Estimated_Damage_Cost` is `Decimal`, validated `>= 0` (never `float`).

## 9. Database persistence: honest, non-fabricated defaults

No AI/OCR/image-analysis process exists yet, so nothing about these fields is invented:

| Field | Value | Why |
|---|---|---|
| `VehicleDamage.Vehicle_Damage_Mismatch_Indicator` | `False` | No automated cross-checking is connected. `False` means "not flagged," never "AI-verified consistent." |
| `Evidence.Image_Quality`, `Evidence.Evidence_Confidence_Score` | `0.0000` | Non-nullable columns; `0` is the "not yet analyzed" value, never a real quality/confidence score (same convention as `Document.OCR_Confidence_Score` in Step 5.8.4). |
| `Evidence.Vehicle_Damage_Detected`, `Evidence.Location_Match`, `Evidence.Duplicate_Evidence_Indicator` | `False` | "Not flagged," not "analyzed and confirmed absent." |
| `Evidence.Damage_Severity` | `"Pending"` | The dataset's own vocabulary for this field (Minor/Moderate/Severe) has no neutral value - `"Pending"` is the same documented sentinel convention already used for `SurveyorInspection` fields in Step 5.8.5, not a real dataset value. |
| `Evidence.Verification_Status` | `"Pending"` | This one **is** a real dataset value (415 of 1301 real rows already use it) - the honest, correct initial state, not a sentinel. |

## 10. Transaction safety (Evidence)

Same ordering as Customer Document Upload: validate -> generate `Evidence_ID` -> save the physical file -> create the database row -> commit. If the database commit fails after the file was written, the transaction rolls back and the just-written file is deleted (`evidence_storage.delete_file`) before returning `500`. If the file save fails, no database row is ever created. Verified by `test_failed_database_operation_removes_saved_file`. `VehicleDamage` has no file component, so it is a single `commit()` with no file-rollback concern.

## 11. Allowed evidence file types

`.jpg`, `.jpeg`, `.png` only - validated by both extension and magic-byte signature (never the browser-supplied MIME type). PDF is intentionally **not** accepted here: document-style evidence already has its own workflow (Customer Document Upload); this endpoint is for the photographic evidence the real dataset's `Evidence_Type` values describe. **No malware/virus scanning is implemented** - this is an explicit, honest limitation, not a claimed capability.

## 12. Database persistence / claim detail integration

No new aggregate endpoint was added. The existing `GET /surveyor/claims/{claim_id}` (unchanged) already returns `vehicle_damage` and `evidence` alongside `accidents` and `inspections` - newly created records appear there automatically once persisted, which is how the frontend's "refresh and confirm it persists" behavior works with zero endpoint changes.

## 13. AI fields that remain pending

Per the task's explicit instruction, **no AI was implemented in this step**: `Vehicle_Damage_Mismatch_Indicator`, `Image_Quality`, `Vehicle_Damage_Detected`, `Evidence.Damage_Severity`, `Location_Match`, `Duplicate_Evidence_Indicator`, and `Evidence_Confidence_Score` are all placeholder/"nothing has run yet" values. The frontend's Evidence cards explicitly separate "Human-Entered" fields from an "Automated Analysis" section, and show "AI analysis pending - this file has not been analyzed yet" instead of the raw placeholder values whenever `Verification_Status == "Pending"`.

## 14. Limitations

- **New customer-created claims still require a separate Surveyor assignment mechanism before a Surveyor can work on them.** (Restated from Step 5.8.5 - this task does not change that.)
- No update or delete endpoint for `VehicleDamage` or `Evidence` - per the task's explicit preference ("prefer CREATE + LIST first... do not add complexity merely for completeness"), only creation and listing (via the existing claim-detail endpoint) were implemented. A surveyor who makes a mistake currently has no way to correct or remove a damage/evidence record through the API; adding `PATCH`/`DELETE` with the same per-surveyor ownership check already used for inspections is a natural, low-risk future enhancement.
- No malware scanning of uploaded evidence files.
- No OCR, computer vision, fraud detection, or consistency analysis - all explicitly out of scope for this task.
- No Garage table, no Repair Estimate CRUD, no Claims Officer decision - untouched.

## 15. Future OCR/image-analysis integration

The placeholder fields listed in Section 13 are exactly where a future OCR/computer-vision step would write real results - e.g. a background job that reads a newly uploaded evidence file, runs damage detection, and updates `Vehicle_Damage_Detected`, `Image_Quality`, `Evidence_Confidence_Score`, and `Verification_Status` on the existing row (no schema change needed). Until that exists, the frontend's `Verification_Status == "Pending"` check is what keeps the UI honest about "nothing has analyzed this yet."
