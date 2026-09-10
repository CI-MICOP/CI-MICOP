"""Tests for POST /api/v1/documents - the customer document-upload endpoint.

Per project rules these run against the real PostgreSQL database and the
real local filesystem storage (see tests/conftest.py); every document row
and physical file created here is removed afterward regardless of outcome.
"""

import re
from pathlib import Path

import pytest

import app.services.document_upload as document_upload_module
from app.db.session import SessionLocal
from app.db_models.document import Document
from app.services import document_storage
from tests.conftest import auth_headers

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n%%EOF"
JPG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

DOCUMENT_ID_PATTERN = re.compile(r"^DOC-\d{8}-[0-9A-F]{6}$")


@pytest.fixture()
def created_document_ids():
    """Document_IDs created by a test - their DB row and physical file
    are removed afterward regardless of pass/fail, so the parent claim's
    own teardown (in conftest.py) never hits a dangling foreign key."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    db = SessionLocal()
    try:
        rows = db.query(Document).filter(Document.Document_ID.in_(ids)).all()
        for row in rows:
            path = document_storage.storage_path_for(row.Claim_ID, row.Document_ID, row.Document_Name)
            document_storage.delete_file(path)
        db.query(Document).filter(Document.Document_ID.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _upload(client, token, claim_id, document_type, filename, content, content_type="application/pdf"):
    headers = auth_headers(token) if token else {}
    return client.post(
        "/api/v1/documents",
        headers=headers,
        data={"claim_id": claim_id, "document_type": document_type},
        files={"file": (filename, content, content_type)},
    )


# ---------------------------------------------------------------- 1/2: valid uploads


def test_authenticated_customer_can_upload_a_valid_pdf(client, customer1_token, seed_data, created_document_ids):
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    assert response.status_code == 201, response.text
    body = response.json()
    created_document_ids.append(body["Document_ID"])

    assert body["Claim_ID"] == seed_data["claim1"]
    assert body["Document_Type"] == "FIR"
    assert body["Document_Status"] == "Submitted"
    assert body["Verification_Status"] == "Pending"


def test_authenticated_customer_can_upload_valid_jpg_and_png(client, customer1_token, seed_data, created_document_ids):
    r1 = _upload(client, customer1_token, seed_data["claim1"], "accident_photos", "photo.jpg", JPG_BYTES, "image/jpeg")
    r2 = _upload(client, customer1_token, seed_data["claim1"], "accident_photos", "photo.png", PNG_BYTES, "image/png")
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    created_document_ids += [r1.json()["Document_ID"], r2.json()["Document_ID"]]


# ---------------------------------------------------------------- 3/4/5/6: auth + ownership


def test_unauthenticated_upload_returns_401(client, seed_data):
    response = _upload(client, None, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    assert response.status_code == 401


def test_non_customer_role_cannot_upload(client, surveyor_token, seed_data):
    response = _upload(client, surveyor_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    assert response.status_code == 403


def test_customer_cannot_upload_to_another_customers_claim(client, customer2_token, seed_data):
    response = _upload(client, customer2_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    assert response.status_code == 403


def test_invalid_claim_returns_404(client, customer1_token):
    response = _upload(client, customer1_token, "NO-SUCH-CLAIM", "fir_copy", "fir.pdf", PDF_BYTES)
    assert response.status_code == 404


# ---------------------------------------------------------------- 7/8/9/10: file validation


def test_unsupported_file_extension_rejected(client, customer1_token, seed_data):
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "malware.exe", b"MZ\x90\x00")
    assert response.status_code == 400


def test_empty_file_rejected(client, customer1_token, seed_data):
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "empty.pdf", b"")
    assert response.status_code == 400


def test_oversized_file_rejected(client, customer1_token, seed_data, monkeypatch):
    monkeypatch.setattr(document_upload_module.settings, "DOCUMENT_MAX_UPLOAD_BYTES", 10)
    oversized_content = PDF_BYTES  # already longer than the patched 10-byte limit
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "big.pdf", oversized_content)
    assert response.status_code == 400


def test_invalid_document_type_rejected(client, customer1_token, seed_data):
    response = _upload(client, customer1_token, seed_data["claim1"], "not_a_real_category", "fir.pdf", PDF_BYTES)
    assert response.status_code == 400


def test_content_not_matching_extension_rejected(client, customer1_token, seed_data):
    """A .pdf extension whose bytes are not actually a PDF - the browser's
    claimed extension/MIME type is not trusted on its own."""
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fake.pdf", b"not a real pdf")
    assert response.status_code == 400


# ---------------------------------------------------------------- 11/12/13: ID + persistence + file


def test_document_id_is_generated_server_side(client, customer1_token, seed_data, created_document_ids):
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    body = response.json()
    created_document_ids.append(body["Document_ID"])
    assert DOCUMENT_ID_PATTERN.match(body["Document_ID"])


def test_database_document_metadata_persisted(client, customer1_token, seed_data, created_document_ids):
    response = _upload(client, customer1_token, seed_data["claim1"], "rc_book", "rc.pdf", PDF_BYTES)
    document_id = response.json()["Document_ID"]
    created_document_ids.append(document_id)

    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.Document_ID == document_id).first()
        assert row is not None
        assert row.Claim_ID == seed_data["claim1"]
        assert row.Document_Type == "RC"
        assert row.Verification_Status == "Pending"
    finally:
        db.close()


def test_physical_file_exists_after_successful_upload(client, customer1_token, seed_data, created_document_ids):
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    body = response.json()
    created_document_ids.append(body["Document_ID"])

    path = document_storage.storage_path_for(body["Claim_ID"], body["Document_ID"], body["Document_Name"])
    assert path.exists()
    assert path.read_bytes() == PDF_BYTES


# ---------------------------------------------------------------- 14: rollback


def test_failed_database_transaction_removes_physical_file(client, customer1_token, seed_data, monkeypatch):
    fixed_document_id = "DOC-19990101-ABCDEF"
    monkeypatch.setattr(document_upload_module.crud_document, "generate_document_id", lambda db: fixed_document_id)

    def _boom(db, document):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(document_upload_module.crud_document, "create", _boom)

    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    assert response.status_code == 500

    expected_path = document_storage.storage_path_for(seed_data["claim1"], fixed_document_id, "fir.pdf")
    assert not expected_path.exists()

    db = SessionLocal()
    try:
        assert db.query(Document).filter(Document.Document_ID == fixed_document_id).first() is None
    finally:
        db.close()


# ---------------------------------------------------------------- 15/16: read-back RBAC


def test_customer_can_retrieve_their_uploaded_document_metadata(client, customer1_token, seed_data, created_document_ids):
    upload_response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    document_id = upload_response.json()["Document_ID"]
    created_document_ids.append(document_id)

    response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers(customer1_token))
    assert response.status_code == 200
    assert response.json()["Document_ID"] == document_id


def test_customer_cannot_retrieve_another_customers_document_metadata(
    client, customer1_token, customer2_token, seed_data, created_document_ids
):
    upload_response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_BYTES)
    document_id = upload_response.json()["Document_ID"]
    created_document_ids.append(document_id)

    response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers(customer2_token))
    assert response.status_code == 403


# ---------------------------------------------------------------- 17: path traversal


def test_filename_path_traversal_is_prevented(client, customer1_token, seed_data, created_document_ids):
    response = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "../../../evil.pdf", PDF_BYTES)
    assert response.status_code == 201, response.text
    body = response.json()
    created_document_ids.append(body["Document_ID"])

    storage_root = Path(document_upload_module.settings.DOCUMENT_STORAGE_ROOT).resolve()
    stored_path = document_storage.storage_path_for(body["Claim_ID"], body["Document_ID"], "../../../evil.pdf")

    # The resolved path must stay confined to the storage root and to this
    # claim's own subdirectory - never escape upward via the traversal
    # sequence in the supplied filename.
    assert storage_root in stored_path.parents
    assert stored_path.parent == storage_root / seed_data["claim1"]
    assert stored_path.exists()
    assert ".." not in stored_path.name
