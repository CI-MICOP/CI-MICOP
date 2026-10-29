"""Development data-import workflow: attach an existing RC, Driving
Licence or Insurance Policy file to an existing customer record, ahead of
and independent of any claim (see services/document_upload.py, which
handles the customer's own claim-time upload - this module is the
separate, Admin-operated import path requested for development/testing
until a real insurer integration exists).

Deliberately separate from the customer-facing upload service: nothing
here is reachable from a customer-authenticated request, and every write
this module performs is driven by a local manifest + files an operator
with direct backend/filesystem access supplies - never by browser input.

Reuses the existing architecture rather than inventing a new one:
  - the same three identity document types and the same reduced-text /
    neutral-filename handling as document_upload._record_identity_copy
    (via claim_copy_retention and document_analysis);
  - the same file validation (extension allow-list, magic-byte sniff,
    size limit) as document_upload;
  - the same local filesystem storage (document_storage), under the
    customer's own ID instead of a claim's;
  - the existing Customer/Vehicle/Policy CRUD lookups, never a new table.

Every row is validated and (outside dry-run) saved independently: a bad
row is skipped and reported, never guessed at, and never blocks any other
row in the same manifest. Running the same manifest again is a no-op for
rows already imported (crud_document.find_identity_document) - this
module never overwrites or deletes an existing document row or file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import customer as crud_customer
from app.crud import document as crud_document
from app.crud import policy as crud_policy
from app.crud import vehicle as crud_vehicle
from app.db_models.document import Document
from app.services import claim_copy_retention, document_analysis, document_storage, document_upload

# The only document types this import workflow handles - the same
# identity-document set already defined in claim_copy_retention, not a
# new vocabulary.
IDENTITY_DOCUMENT_TYPES = claim_copy_retention.NOT_RETAINED_DOCUMENT_TYPES

# Row outcomes, reported back to the operator - never silent.
IMPORTED = "imported"
WOULD_IMPORT = "would_import"
SKIPPED_DUPLICATE = "skipped_duplicate"
INVALID = "invalid"


@dataclass
class ImportRow:
    """One manifest line, after light normalization. Optional fields are
    "" in the CSV; normalized to None here."""

    line_number: int
    customer_id: str
    document_type: str
    filename: str
    vehicle_id: str | None = None
    policy_id: str | None = None
    expiry_date: str | None = None
    issuer_reference: str | None = None


@dataclass
class ImportRowResult:
    row: ImportRow
    outcome: str
    message: str
    document_id: str | None = None


@dataclass
class ImportReport:
    dry_run: bool
    results: list[ImportRowResult] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counts = {IMPORTED: 0, WOULD_IMPORT: 0, SKIPPED_DUPLICATE: 0, INVALID: 0}
        for result in self.results:
            counts[result.outcome] += 1
        return counts


def _parse_expiry(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value.strip())


def _validate_relationships(db: Session, row: ImportRow) -> tuple[object, object | None, object | None] | str:
    """Confirms the customer exists and, for RC / Insurance Policy, that
    the referenced vehicle/policy exists and genuinely belongs to that
    customer (and, for a policy, to that vehicle too when both are given).
    Returns (customer, vehicle, policy) - vehicle/policy are None when not
    applicable to this document_type - or an error message string. Never
    guesses a relationship that the manifest did not state explicitly."""
    customer = crud_customer.get(db, row.customer_id)
    if customer is None:
        return f"Customer {row.customer_id!r} does not exist"

    vehicle = None
    policy = None

    if row.document_type == "RC":
        if not row.vehicle_id:
            return "RC import requires vehicle_id"
        vehicle = crud_vehicle.get(db, row.vehicle_id)
        if vehicle is None:
            return f"Vehicle {row.vehicle_id!r} does not exist"
        if vehicle.Customer_ID != row.customer_id:
            return f"Vehicle {row.vehicle_id!r} does not belong to customer {row.customer_id!r}"

    elif row.document_type == "Insurance Policy":
        if not row.policy_id:
            return "Insurance Policy import requires policy_id"
        policy = crud_policy.get(db, row.policy_id)
        if policy is None:
            return f"Policy {row.policy_id!r} does not exist"
        if policy.Customer_ID != row.customer_id:
            return f"Policy {row.policy_id!r} does not belong to customer {row.customer_id!r}"
        if row.vehicle_id and policy.Vehicle_ID != row.vehicle_id:
            return f"Policy {row.policy_id!r} is not linked to vehicle {row.vehicle_id!r}"

    elif row.document_type == "Driving Licence":
        pass  # customer-only; vehicle_id/policy_id are ignored if given.

    else:
        return f"Unsupported document_type {row.document_type!r}; allowed: {sorted(IDENTITY_DOCUMENT_TYPES)}"

    return customer, vehicle, policy


def _read_and_validate_file(documents_dir: Path, filename: str) -> bytes | str:
    """The file's bytes, validated exactly like a customer's own upload
    (document_upload's extension allow-list, size limit and magic-byte
    check) - or an error message string. Never follows a path outside
    documents_dir: only the basename of `filename` is ever opened."""
    safe_name = Path(filename).name
    path = (documents_dir / safe_name).resolve()
    if documents_dir.resolve() not in path.parents and path != documents_dir.resolve():
        return f"{filename!r} resolves outside the documents directory"
    if not path.is_file():
        return f"File {filename!r} was not found in the documents directory"

    try:
        ext = document_upload._validate_extension(safe_name)
    except Exception:
        return f"{filename!r} has an unsupported file extension"

    content = path.read_bytes()
    if len(content) == 0:
        return f"{filename!r} is empty"
    if len(content) > settings.DOCUMENT_MAX_UPLOAD_BYTES:
        return f"{filename!r} exceeds the maximum allowed size"
    try:
        document_upload._validate_signature(ext, content)
    except Exception:
        return f"{filename!r}'s content does not match its extension"

    return content


def _store_identity_document(
    db: Session,
    *,
    row: ImportRow,
    content: bytes,
    customer_id: str,
    vehicle_id: str | None,
    policy_id: str | None,
    imported_by: str | None,
) -> Document:
    """Saves one identity document exactly like document_upload's own
    RC/licence/policy path (_record_identity_copy): reduced verification
    text, neutral stored filename, file written before the database row,
    rollback-and-delete-file on any failure. Run from a standalone script
    (never inside a request), so - unlike document_upload, which offloads
    this same call to a thread pool to avoid blocking the event loop -
    this calls document_analysis.extract_document_bytes directly."""
    ext = Path(row.filename).suffix.lower()
    extraction = document_analysis.extract_document_bytes(content, ext)

    document_id = crud_document.generate_document_id(db)
    neutral_name = document_upload._COPY_NAMES[row.document_type] + ext
    stored_path = document_storage.storage_path_for(customer_id, document_id, neutral_name)

    document = Document(
        Document_ID=document_id,
        Claim_ID=None,
        Customer_ID=customer_id,
        Vehicle_ID=vehicle_id,
        Policy_ID=policy_id,
        Document_Type=row.document_type,
        Document_Name=neutral_name,
        Document_Submitted_Date=date.today(),
        Document_Status="Submitted",
        OCR_Confidence_Score=Decimal(str(round(extraction.confidence, 4))),
        Extracted_Text=claim_copy_retention.verification_record(extraction.text),
        Document_Completeness=Decimal("0.0000"),
        Document_Mismatch_Indicator=False,
        Verification_Status="Pending",
        Document_Expiry_Date=_parse_expiry(row.expiry_date),
        Issuer_Reference=(row.issuer_reference or None),
        Uploaded_By=imported_by,
    )

    document_storage.save_file(stored_path, content)
    try:
        crud_document.create(db, document)
        db.commit()
    except Exception:
        db.rollback()
        document_storage.delete_file(stored_path)
        raise
    db.refresh(document)
    return document


def import_one(
    db: Session, row: ImportRow, documents_dir: Path, imported_by: str | None, dry_run: bool
) -> ImportRowResult:
    relationships = _validate_relationships(db, row)
    if isinstance(relationships, str):
        return ImportRowResult(row, INVALID, relationships)
    _customer, vehicle, policy = relationships
    vehicle_id = vehicle.Vehicle_ID if vehicle else None
    policy_id = policy.Policy_ID if policy else None

    existing = crud_document.find_identity_document(db, row.document_type, row.customer_id, vehicle_id, policy_id)
    if existing is not None:
        return ImportRowResult(row, SKIPPED_DUPLICATE, "Already imported", existing.Document_ID)

    content = _read_and_validate_file(documents_dir, row.filename)
    if isinstance(content, str):
        return ImportRowResult(row, INVALID, content)

    try:
        _parse_expiry(row.expiry_date)
    except ValueError:
        return ImportRowResult(row, INVALID, f"Invalid expiry_date {row.expiry_date!r}; expected YYYY-MM-DD")

    if dry_run:
        return ImportRowResult(row, WOULD_IMPORT, "Valid - would be imported")

    document = _store_identity_document(
        db,
        row=row,
        content=content,
        customer_id=row.customer_id,
        vehicle_id=vehicle_id,
        policy_id=policy_id,
        imported_by=imported_by,
    )
    return ImportRowResult(row, IMPORTED, "Imported", document.Document_ID)


def run_import(
    db: Session, rows: list[ImportRow], documents_dir: Path, imported_by: str | None, dry_run: bool
) -> ImportReport:
    report = ImportReport(dry_run=dry_run)
    for row in rows:
        report.results.append(import_one(db, row, documents_dir, imported_by, dry_run))
    return report


def parse_manifest_rows(csv_rows: list[dict[str, str]]) -> list[ImportRow]:
    """Normalizes raw csv.DictReader rows into ImportRow - blank optional
    fields become None, never an empty-string placeholder that would
    silently pass a relationship check."""
    rows: list[ImportRow] = []
    for line_number, raw in enumerate(csv_rows, start=2):  # header is line 1
        rows.append(
            ImportRow(
                line_number=line_number,
                customer_id=(raw.get("customer_id") or "").strip(),
                document_type=(raw.get("document_type") or "").strip(),
                filename=(raw.get("filename") or "").strip(),
                vehicle_id=(raw.get("vehicle_id") or "").strip() or None,
                policy_id=(raw.get("policy_id") or "").strip() or None,
                expiry_date=(raw.get("expiry_date") or "").strip() or None,
                issuer_reference=(raw.get("issuer_reference") or "").strip() or None,
            )
        )
    return rows
