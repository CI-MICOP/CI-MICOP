"""Tests for services/document_import.py - the development data-import
workflow that attaches an existing RC / Driving Licence / Insurance
Policy file to an existing customer (and, where applicable, vehicle or
policy) record, independent of any claim.

Per project rules these run against the real PostgreSQL database and the
real local filesystem storage (see tests/conftest.py); every document row
and physical file created here is removed afterward regardless of outcome.
"""

from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.db_models.document import Document
from app.services import document_import, document_storage
from tests.conftest import IDS

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n%%EOF"


@pytest.fixture()
def created_document_ids():
    ids: list[str] = []
    yield ids
    if not ids:
        return
    db = SessionLocal()
    try:
        rows = db.query(Document).filter(Document.Document_ID.in_(ids)).all()
        for row in rows:
            path = document_storage.storage_path_for(row.Customer_ID, row.Document_ID, row.Document_Name)
            document_storage.delete_file(path)
        db.query(Document).filter(Document.Document_ID.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def documents_dir(tmp_path: Path) -> Path:
    (tmp_path / "rc.pdf").write_bytes(PDF_BYTES)
    (tmp_path / "dl.pdf").write_bytes(PDF_BYTES)
    (tmp_path / "policy.pdf").write_bytes(PDF_BYTES)
    return tmp_path


def _row(**overrides) -> document_import.ImportRow:
    defaults = dict(line_number=2, customer_id=IDS["customer1"], document_type="RC", filename="rc.pdf")
    defaults.update(overrides)
    return document_import.ImportRow(**defaults)


# `db` and `seed_data` are session-scoped fixtures from tests/conftest.py.

# ---------------------------------------------------------------- 1/2/3: valid imports


def test_imports_an_rc_for_an_existing_customers_vehicle(db, seed_data, documents_dir, created_document_ids):
    row = _row(document_type="RC", filename="rc.pdf", vehicle_id=IDS["vehicle1"])
    result = document_import.import_one(db, row, documents_dir, "TEST-USER-ADMIN1", dry_run=False)
    created_document_ids.append(result.document_id)

    assert result.outcome == document_import.IMPORTED, result.message
    document = db.query(Document).filter(Document.Document_ID == result.document_id).first()
    assert document.Document_Type == "RC"
    assert document.Customer_ID == IDS["customer1"]
    assert document.Vehicle_ID == IDS["vehicle1"]
    assert document.Claim_ID is None
    assert document.Uploaded_By == "TEST-USER-ADMIN1"
    path = document_storage.storage_path_for(document.Customer_ID, document.Document_ID, document.Document_Name)
    assert path.exists()


def test_imports_a_driving_licence_for_an_existing_customer(db, seed_data, documents_dir, created_document_ids):
    row = _row(document_type="Driving Licence", filename="dl.pdf")
    result = document_import.import_one(db, row, documents_dir, "TEST-USER-ADMIN1", dry_run=False)
    created_document_ids.append(result.document_id)

    assert result.outcome == document_import.IMPORTED, result.message
    document = db.query(Document).filter(Document.Document_ID == result.document_id).first()
    assert document.Document_Type == "Driving Licence"
    assert document.Customer_ID == IDS["customer1"]
    assert document.Vehicle_ID is None
    assert document.Policy_ID is None


def test_imports_a_policy_document_linked_to_customer_vehicle_and_policy(
    db, seed_data, documents_dir, created_document_ids
):
    row = _row(
        document_type="Insurance Policy",
        filename="policy.pdf",
        vehicle_id=IDS["vehicle1"],
        policy_id=IDS["policy1"],
    )
    result = document_import.import_one(db, row, documents_dir, "TEST-USER-ADMIN1", dry_run=False)
    created_document_ids.append(result.document_id)

    assert result.outcome == document_import.IMPORTED, result.message
    document = db.query(Document).filter(Document.Document_ID == result.document_id).first()
    assert document.Policy_ID == IDS["policy1"]
    assert document.Customer_ID == IDS["customer1"]


# ---------------------------------------------------------------- 4: nonexistent IDs


def test_rejects_a_nonexistent_customer_id(db, seed_data, documents_dir):
    row = _row(customer_id="NO-SUCH-CUSTOMER", document_type="Driving Licence", filename="dl.pdf")
    result = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "does not exist" in result.message


def test_rejects_a_nonexistent_vehicle_id(db, seed_data, documents_dir):
    row = _row(document_type="RC", filename="rc.pdf", vehicle_id="NO-SUCH-VEHICLE")
    result = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "does not exist" in result.message


def test_rejects_a_nonexistent_policy_id(db, seed_data, documents_dir):
    row = _row(document_type="Insurance Policy", filename="policy.pdf", policy_id="NO-SUCH-POLICY")
    result = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "does not exist" in result.message


# ---------------------------------------------------------------- 5: wrong customer/vehicle


def test_rejects_a_vehicle_that_belongs_to_a_different_customer(db, seed_data, documents_dir):
    row = _row(customer_id=IDS["customer2"], document_type="RC", filename="rc.pdf", vehicle_id=IDS["vehicle1"])
    result = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "does not belong to customer" in result.message


def test_rejects_a_policy_that_belongs_to_a_different_customer(db, seed_data, documents_dir):
    row = _row(customer_id=IDS["customer2"], document_type="Insurance Policy", filename="policy.pdf", policy_id=IDS["policy1"])
    result = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "does not belong to customer" in result.message


def test_rejects_a_policy_linked_to_a_different_vehicle_than_stated(db, seed_data, documents_dir):
    row = _row(
        document_type="Insurance Policy",
        filename="policy.pdf",
        policy_id=IDS["policy1"],
        vehicle_id="SOME-OTHER-VEHICLE-ID",
    )
    result = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "not linked to vehicle" in result.message


# ---------------------------------------------------------------- 6: duplicate prevention


def test_running_the_same_import_twice_does_not_create_a_duplicate(
    db, seed_data, documents_dir, created_document_ids
):
    row = _row(document_type="Driving Licence", filename="dl.pdf")
    first = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    created_document_ids.append(first.document_id)
    assert first.outcome == document_import.IMPORTED

    second = document_import.import_one(db, row, documents_dir, None, dry_run=False)
    assert second.outcome == document_import.SKIPPED_DUPLICATE
    assert second.document_id == first.document_id

    count = (
        db.query(Document)
        .filter(Document.Customer_ID == IDS["customer1"], Document.Document_Type == "Driving Licence")
        .count()
    )
    assert count == 1


# ---------------------------------------------------------------- 7: dry run makes no changes


def test_dry_run_reports_without_changing_the_database_or_storage(db, seed_data, documents_dir):
    row = _row(document_type="RC", filename="rc.pdf", vehicle_id=IDS["vehicle1"])
    result = document_import.import_one(db, row, documents_dir, None, dry_run=True)

    assert result.outcome == document_import.WOULD_IMPORT
    assert result.document_id is None
    count = (
        db.query(Document)
        .filter(Document.Customer_ID == IDS["customer1"], Document.Document_Type == "RC")
        .count()
    )
    assert count == 0


def test_dry_run_also_reports_invalid_rows_without_raising(db, seed_data, documents_dir):
    row = _row(customer_id="NO-SUCH-CUSTOMER")
    result = document_import.import_one(db, row, documents_dir, None, dry_run=True)
    assert result.outcome == document_import.INVALID


# ---------------------------------------------------------------- file validation


def test_rejects_a_file_with_a_mismatched_signature(db, seed_data, tmp_path):
    (tmp_path / "fake.pdf").write_bytes(b"not actually a pdf")
    row = _row(document_type="Driving Licence", filename="fake.pdf")
    result = document_import.import_one(db, row, tmp_path, None, dry_run=False)
    assert result.outcome == document_import.INVALID


def test_rejects_a_missing_file(db, seed_data, tmp_path):
    row = _row(document_type="Driving Licence", filename="does-not-exist.pdf")
    result = document_import.import_one(db, row, tmp_path, None, dry_run=False)
    assert result.outcome == document_import.INVALID
    assert "not found" in result.message


def test_run_import_processes_every_row_independently(db, seed_data, documents_dir, created_document_ids):
    rows = [
        _row(document_type="Driving Licence", filename="dl.pdf"),
        _row(customer_id="NO-SUCH-CUSTOMER", document_type="Driving Licence", filename="dl.pdf"),
    ]
    report = document_import.run_import(db, rows, documents_dir, None, dry_run=False)
    created_document_ids += [r.document_id for r in report.results if r.document_id]

    assert report.counts[document_import.IMPORTED] == 1
    assert report.counts[document_import.INVALID] == 1
