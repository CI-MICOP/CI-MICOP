"""Tests for GET /api/v1/documents/identity and
GET /api/v1/documents/identity/{document_id}/content - the Customer
Portal's "My Documents" identity-document section.

Per project rules these run against the real PostgreSQL database and the
real local filesystem storage (see tests/conftest.py); every document row
and physical file created here is removed afterward regardless of outcome.
"""

from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.db_models.document import Document
from app.services import document_import, document_storage
from tests.conftest import IDS, auth_headers

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


def _import_dl_for_customer1(tmp_path: Path, created_document_ids: list[str]) -> str:
    (tmp_path / "dl.pdf").write_bytes(PDF_BYTES)
    row = document_import.ImportRow(
        line_number=2, customer_id=IDS["customer1"], document_type="Driving Licence", filename="dl.pdf"
    )
    db = SessionLocal()
    try:
        result = document_import.import_one(db, row, tmp_path, "TEST-USER-ADMIN1", dry_run=False)
    finally:
        db.close()
    assert result.outcome == document_import.IMPORTED, result.message
    created_document_ids.append(result.document_id)
    return result.document_id


def test_my_documents_shows_not_uploaded_for_every_type_when_none_imported(client, customer2_token, seed_data):
    response = client.get("/api/v1/documents/identity", headers=auth_headers(customer2_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customer_id"] == IDS["customer2"]
    assert {d["document_type"] for d in body["documents"]} == {"RC", "Driving Licence", "Insurance Policy"}
    assert all(d["availability"] == "not_uploaded" for d in body["documents"])


def test_my_documents_shows_an_imported_document_as_available(
    client, customer1_token, seed_data, tmp_path, created_document_ids
):
    _import_dl_for_customer1(tmp_path, created_document_ids)

    response = client.get("/api/v1/documents/identity", headers=auth_headers(customer1_token))
    assert response.status_code == 200, response.text
    entries = {d["document_type"]: d for d in response.json()["documents"]}
    assert entries["Driving Licence"]["availability"] == "available"
    assert entries["RC"]["availability"] == "not_uploaded"


def test_customer_can_view_their_own_imported_document_content(
    client, customer1_token, seed_data, tmp_path, created_document_ids
):
    document_id = _import_dl_for_customer1(tmp_path, created_document_ids)
    response = client.get(
        f"/api/v1/documents/identity/{document_id}/content", headers=auth_headers(customer1_token)
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_a_different_customer_cannot_view_this_customers_identity_document(
    client, customer2_token, seed_data, tmp_path, created_document_ids
):
    document_id = _import_dl_for_customer1(tmp_path, created_document_ids)
    response = client.get(
        f"/api/v1/documents/identity/{document_id}/content", headers=auth_headers(customer2_token)
    )
    assert response.status_code == 404


def test_unauthenticated_request_is_rejected(client, seed_data):
    response = client.get("/api/v1/documents/identity")
    assert response.status_code == 401


def test_non_customer_role_cannot_use_the_customer_identity_endpoint(client, surveyor_token, seed_data):
    response = client.get("/api/v1/documents/identity", headers=auth_headers(surveyor_token))
    assert response.status_code == 403


def test_missing_file_on_disk_is_reported_unavailable_not_available(
    client, customer1_token, seed_data, tmp_path, created_document_ids
):
    document_id = _import_dl_for_customer1(tmp_path, created_document_ids)
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.Document_ID == document_id).first()
        path = document_storage.storage_path_for(document.Customer_ID, document.Document_ID, document.Document_Name)
        path.unlink()
    finally:
        db.close()

    response = client.get("/api/v1/documents/identity", headers=auth_headers(customer1_token))
    entries = {d["document_type"]: d for d in response.json()["documents"]}
    assert entries["Driving Licence"]["availability"] == "unavailable"
