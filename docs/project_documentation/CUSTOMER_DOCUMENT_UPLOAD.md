# Customer Document Upload

Makes the existing Step 3 ("Upload Documents") of the Customer FNOL wizard real. Before this change, `DocumentUploadGrid` only kept a browser-selected `File` in local React state - nothing was ever sent anywhere, because the backend had no upload endpoint (only `GET /documents`). This document describes the architecture added to make that real, and its honest limitations.

## 1. Architecture

```
Browser (multipart/form-data: claim_id, document_type, file)
        |
        v
POST /api/v1/documents  (JWT auth, Customer role required)
        |
        v
1. Ownership check (claim must belong to the authenticated customer)
2. document_type checked against a controlled allow-list
3. File validated: extension -> bounded read -> non-empty -> magic-byte signature
4. Document_ID generated server-side
5. Safe, server-controlled storage path generated
6. File written to local disk
7. Document metadata row written to PostgreSQL (one transaction)
        |
        v
Response: document metadata only (never a filesystem path)
```

PostgreSQL continues to store **metadata only** (`documents` table, unchanged - no new table, no new column). The physical file lives on the local filesystem under `infra/storage/documents/`. No binary content is ever stored in PostgreSQL.

## 2. Storage convention

```
infra/storage/documents/<Claim_ID>/<Document_ID>_<safe_filename>
```

Example:

```
infra/storage/documents/
└── DEV-CLM-001/
    ├── DOC-20260910-41A7DF_fir.pdf
    ├── DOC-20260910-2F0BD7_rc.pdf
    └── DOC-20260910-E91474_accident.jpg
```

Implemented in `backend/app/services/document_storage.py`:

- `sanitize_filename()` strips any directory component (`Path(name).name`, which alone defeats `../`, `..\`, and absolute paths) and then replaces every character that isn't a letter, digit, `.`, `_` or `-` with `_`. The browser's filename is never trusted as a path - only the sanitized basename is used, and even then only as a *suffix* appended to the server-generated `Document_ID`.
- `storage_path_for()` builds the final path from the (already-validated, already-existing) `Claim_ID`, the server-generated `Document_ID`, and the sanitized filename, then resolves it and asserts the result is still inside the configured storage root - defense in depth in case a future change to the sanitizer regresses.
- The storage directory is created automatically (`mkdir(parents=True, exist_ok=True)`) on first write - no manual setup needed.
- The root is configurable via `DOCUMENT_STORAGE_ROOT` in `.env` (defaults to `<repo root>/infra/storage/documents`, see `app/core/config.py`).

This is intentionally the *only* module that knows about the local filesystem. Swapping in S3/Azure Blob/MinIO later means replacing `save_file()`/`delete_file()`/`storage_path_for()` in this one file - no router, schema, or database change required.

## 3. Endpoint

`POST /api/v1/documents` (multipart/form-data), added to the existing `documents` router alongside the pre-existing `GET /documents` and `GET /documents/{document_id}`.

Form fields: `claim_id`, `document_type`, `file`. Customer_ID is never a field - it is resolved exclusively from the JWT via the existing `require_customer_id` dependency, exactly as the claim-creation endpoint does.

## 4. Authentication / RBAC

- No token -> `401` (via the existing OAuth2 bearer scheme).
- Token valid but role isn't `Customer` -> `403` (via `require_customer_id`).
- Claim doesn't exist -> `404`.
- Claim exists but belongs to a different customer -> `403`.

This mirrors the ownership-check pattern already established for claim creation (`services/claim_creation.py`) rather than reusing `services/claim_access.get_claim_or_403` directly - that helper's job is broader read-access RBAC (Admin/Officer see everything, Surveyor sees assigned claims), which is the wrong policy for a customer-only *write* endpoint. `GET /documents` and `GET /documents/{id}` are untouched and still use `get_claim_or_403` exactly as before.

## 5. Document type allow-list

`ALLOWED_DOCUMENT_TYPES` in `backend/app/services/document_upload.py` maps the *existing* frontend category keys (`frontend/src/components/customer/documentCategories.js`) to the `Document_Type` value stored in the database - a controlled allow-list, not free text from the client:

| Frontend key (`document_type` field) | Stored `Document_Type` |
|---|---|
| `fir_copy` | `FIR` |
| `driving_licence` | `Driving Licence` |
| `rc_book` | `RC` |
| `insurance_policy` | `Insurance Policy` |
| `repair_estimate` | `Repair Estimate` |
| `accident_photos` | `Accident Photos` |
| `survey_report` | `Survey Report` |

No new category was invented - these are exactly the seven categories `DocumentUploadGrid` already offered. The short DB-side labels (`FIR`, `RC`) match the convention already used by `seed_dev_data.py`.

## 6. File validation

All server-side, in `document_upload.py`:

1. **Extension allow-list**: `.pdf`, `.jpg`, `.jpeg`, `.png` - anything else is rejected with `400`.
2. **Bounded read**: the file is read in 1 MB chunks up to `DOCUMENT_MAX_UPLOAD_BYTES` (10 MB, configured once in `app/core/config.py`, not scattered through the code); exceeding it aborts with `400` without ever buffering the full oversized payload into memory.
3. **Non-empty**: a zero-byte file is rejected with `400`.
4. **Magic-byte signature check**: the actual file bytes must start with the real signature for the claimed extension (`%PDF` for PDF, `\xff\xd8\xff` for JPEG, the PNG header for PNG). The browser-supplied `Content-Type` header is never trusted or even inspected - content is sniffed from the bytes themselves.

## 7. Document_ID generation

`crud/document.py`'s `generate_document_id()` produces `DOC-YYYYMMDD-XXXXXX` (today's date + 6 random hex characters) and checks it against the `documents` primary key before use - never accepted from the client, following the same pattern as `Claim_ID`/`Claim_Number` generation from the claim-creation task.

## 8. Metadata written on a successful upload

No process has actually inspected the file's content, so nothing about it is fabricated:

| Column | Value | Why |
|---|---|---|
| `Document_Status` | `"Submitted"` | Just received, nothing processed yet. |
| `Verification_Status` | `"Pending"` | No verification has run. |
| `Document_Submitted_Date` | today | Real submission date. |
| `OCR_Confidence_Score` | `0.0000` | The column is non-nullable (no NULL allowed by the approved schema) - `0` is the honest "no OCR has run" value, never a fabricated confidence number. |
| `Extracted_Text` | `""` (empty string) | Same reasoning - non-nullable, and no OCR has run in this task. |
| `Document_Completeness` | `0.0000` | Nothing has assessed completeness yet. |
| `Document_Mismatch_Indicator` | `False` | No comparison has run; `False` here means "not flagged", not "verified consistent". |

## 9. Transaction / failure handling

Order (`upload_document_for_customer` in `document_upload.py`):

1. Authenticate (router dependency) -> 2. Ownership -> 3. Document type -> 4. File validation -> 5. Generate `Document_ID` -> 6. Generate storage path -> 7. Save physical file -> 8. Create DB row -> 9. Commit.

- If the **file write fails** (step 7), no database row is ever created.
- If the **database commit fails** (step 9) after the file was already written, the transaction is rolled back **and the just-written physical file is deleted** (`document_storage.delete_file()`), then a `500` is returned. Verified by `test_failed_database_transaction_removes_physical_file`, which forces the database write to fail and asserts both that no row exists and that the file was never left on disk.

Neither an orphaned database row (pointing at a missing file) nor an orphaned physical file (with no database record) can result from a partial failure.

## 10. Response shape

The existing `DocumentOut` schema is reused unchanged: `Document_ID`, `Claim_ID`, `Document_Type`, `Document_Name`, `Document_Submitted_Date`, `Document_Status`, `OCR_Confidence_Score`, `Extracted_Text`, `Document_Completeness`, `Document_Mismatch_Indicator`, `Verification_Status`. It never contains a filesystem path.

## 11. Frontend

- `frontend/src/services/documentService.js`: added `uploadDocument(claimId, documentType, file)`, building a `FormData` and posting through the existing `apiClient` - no second Axios instance, and `Content-Type`/the multipart boundary is left for Axios to set automatically (never set manually).
- `frontend/src/pages/customer/NewClaimPage.jsx`: the four-step wizard is unchanged in structure. On "Submit Claim", the claim is created first; only once a real `Claim_ID` comes back does the page upload each selected file sequentially, tracking per-file state (`uploading` / `uploaded` / `failed`). The success screen shows the claim number/status plus a per-document progress list, a failed document's error message and a **Retry** button (re-uploads just that one file), and an honest aggregate line - `"All N documents uploaded."` or `"X of N documents uploaded. Y document(s) failed and need(s) retry."` - never claiming success for a file that didn't upload.
- `frontend/src/pages/customer/ClaimDetailsPage.jsx`: the existing documents list (already wired to `GET /documents?claim_id=...`) now also shows `Document_Name` and `Verification_Status`, not just type/status. No filesystem path is ever displayed, and no download link was added (out of scope).

## 12. Security considerations

- Path traversal (`../`, `..\`, absolute paths) in a client-supplied filename cannot escape the storage root - verified by `test_filename_path_traversal_is_prevented`, which uploads a file named `../../../evil.pdf` and asserts the stored file lands inside the claim's own subdirectory.
- Claim ownership is re-validated against the database on every upload - a customer cannot upload to a claim they don't own, and cannot discover another claim's existence through this endpoint beyond the same 404-vs-403 distinction the rest of the API already makes for claim access.
- File type is validated by content (magic bytes), not by trusting the browser's extension or MIME type claim.
- Upload size is bounded server-side, not only in the frontend.

## 13. Limitations

- **Local filesystem storage only.** This is a college prototype; there is no redundancy, replication, or backup of `infra/storage/documents/`. It is explicitly designed to be swappable - see below.
- **No OCR / text extraction.** `Extracted_Text` and `OCR_Confidence_Score` are placeholder "nothing has run yet" values, not real OCR output. Implementing OCR is a later, separate task.
- **No fraud detection, consistency checking, or AI analysis** of uploaded documents in this task.
- **No automatic document verification.** `Verification_Status` stays `"Pending"` until a human (Claims Officer, in a later step) or a future automated process changes it.
- **No download endpoint.** Only metadata is exposed; retrieving the actual file content was explicitly out of scope for this task.
- **No virus/malware scanning** of uploaded files.

## 14. Future cloud storage migration

`document_storage.py` is the single seam for this: replace `save_file()` (write to S3/Azure Blob/MinIO instead of the local disk) and `delete_file()` (equivalent remote delete), and change what `storage_path_for()` returns (an object key / blob path instead of a local `Path`). No change would be needed to the `documents` table, the router, or `document_upload.py`'s validation/ownership/transaction logic - they only ever call these three functions and never touch the filesystem directly.
