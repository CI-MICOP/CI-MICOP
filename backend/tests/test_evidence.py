"""Tests for POST /api/v1/surveyor/evidence (Step 5.8.6).

Per project rules these run against the real PostgreSQL database and the
real local filesystem storage (see tests/conftest.py); every evidence row
and physical file created here is removed afterward regardless of
outcome.
"""

import re
from pathlib import Path

import pytest

import app.services.evidence_upload as evidence_upload_module
from app.db.session import SessionLocal
from app.db_models.evidence import Evidence
from app.services import evidence_storage
from tests.conftest import auth_headers

JPG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

EVIDENCE_ID_PATTERN = re.compile(r"^EVD-\d{8}-[0-9A-F]{6}$")

FORM_FIELDS = {
    "evidence_type": "Damage Photo",
    "evidence_date": "2026-09-10",
    "evidence_source": "Surveyor",
}


def _fields(claim_id, **overrides):
    body = {"claim_id": claim_id, **FORM_FIELDS}
    body.update(overrides)
    return body


@pytest.fixture()
def created_evidence_ids():
    ids: list[str] = []
    yield ids
    if not ids:
        return
    db = SessionLocal()
    try:
        rows = db.query(Evidence).filter(Evidence.Evidence_ID.in_(ids)).all()
        for row in rows:
            path = evidence_storage.storage_path_for(row.Claim_ID, row.Evidence_ID, row.File_Name)
            evidence_storage.delete_file(path)
        db.query(Evidence).filter(Evidence.Evidence_ID.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _upload(client, token, claim_id, filename, content, content_type="image/jpeg", **field_overrides):
    headers = auth_headers(token) if token else {}
    return client.post(
        "/api/v1/surveyor/evidence",
        headers=headers,
        data=_fields(claim_id, **field_overrides),
        files={"file": (filename, content, content_type)},
    )


# ---------------------------------------------------------------- 9/10/11/12: auth + role + assignment


def test_unauthenticated_evidence_upload_returns_401(client, seed_data):
    response = _upload(client, None, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    assert response.status_code == 401


def test_customer_cannot_upload_evidence(client, customer1_token, seed_data):
    response = _upload(client, customer1_token, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    assert response.status_code == 403


def test_officer_cannot_upload_evidence(client, officer_token, seed_data):
    response = _upload(client, officer_token, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    assert response.status_code == 403


def test_unassigned_surveyor_evidence_upload_rejected(client, surveyor_token, unassigned_claim):
    response = _upload(client, surveyor_token, unassigned_claim, "photo.jpg", JPG_BYTES)
    assert response.status_code == 403


def test_wrong_surveyor_evidence_upload_rejected(client, surveyor_token, other_surveyor_claim):
    response = _upload(client, surveyor_token, other_surveyor_claim["claim_id"], "photo.jpg", JPG_BYTES)
    assert response.status_code == 403


# ---------------------------------------------------------------- 13/14/15/16: valid upload + persistence


def test_assigned_surveyor_evidence_upload_succeeds(client, surveyor_token, seed_data, created_evidence_ids):
    response = _upload(client, surveyor_token, seed_data["claim1"], "damage.jpg", JPG_BYTES)
    assert response.status_code == 201, response.text
    body = response.json()
    created_evidence_ids.append(body["Evidence_ID"])

    assert body["Claim_ID"] == seed_data["claim1"]
    assert body["Evidence_Type"] == "Damage Photo"
    assert body["Evidence_Source"] == "Surveyor"
    assert body["Verification_Status"] == "Pending"


def test_png_upload_also_succeeds(client, surveyor_token, seed_data, created_evidence_ids):
    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.png", PNG_BYTES, content_type="image/png")
    assert response.status_code == 201, response.text
    created_evidence_ids.append(response.json()["Evidence_ID"])


def test_evidence_id_generated_server_side(client, surveyor_token, seed_data, created_evidence_ids):
    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    body = response.json()
    created_evidence_ids.append(body["Evidence_ID"])
    assert EVIDENCE_ID_PATTERN.match(body["Evidence_ID"])


def test_physical_file_exists_after_successful_upload(client, surveyor_token, seed_data, created_evidence_ids):
    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    body = response.json()
    created_evidence_ids.append(body["Evidence_ID"])

    path = evidence_storage.storage_path_for(body["Claim_ID"], body["Evidence_ID"], body["File_Name"])
    assert path.exists()
    assert path.read_bytes() == JPG_BYTES


def test_database_metadata_persists(client, surveyor_token, seed_data, created_evidence_ids):
    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    evidence_id = response.json()["Evidence_ID"]
    created_evidence_ids.append(evidence_id)

    db = SessionLocal()
    try:
        row = db.query(Evidence).filter(Evidence.Evidence_ID == evidence_id).first()
        assert row is not None
        assert row.Claim_ID == seed_data["claim1"]
        assert row.Verification_Status == "Pending"
        # Honest "not yet analyzed" placeholders, never fabricated AI output.
        assert row.Evidence_Confidence_Score == 0
        assert row.Vehicle_Damage_Detected is False
    finally:
        db.close()


# ---------------------------------------------------------------- 17: rollback


def test_failed_database_operation_removes_saved_file(client, surveyor_token, seed_data, monkeypatch):
    fixed_evidence_id = "EVD-19990101-ABCDEF"
    monkeypatch.setattr(evidence_upload_module.crud_evidence, "generate_evidence_id", lambda db: fixed_evidence_id)

    def _boom(db, evidence):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(evidence_upload_module.crud_evidence, "create", _boom)

    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.jpg", JPG_BYTES)
    assert response.status_code == 500

    expected_path = evidence_storage.storage_path_for(seed_data["claim1"], fixed_evidence_id, "photo.jpg")
    assert not expected_path.exists()

    db = SessionLocal()
    try:
        assert db.query(Evidence).filter(Evidence.Evidence_ID == fixed_evidence_id).first() is None
    finally:
        db.close()


# ---------------------------------------------------------------- 18/19: file validation


def test_invalid_file_type_rejected(client, surveyor_token, seed_data):
    response = _upload(client, surveyor_token, seed_data["claim1"], "malware.exe", b"MZ\x90\x00", content_type="application/octet-stream")
    assert response.status_code == 400


def test_empty_file_rejected(client, surveyor_token, seed_data):
    response = _upload(client, surveyor_token, seed_data["claim1"], "empty.jpg", b"")
    assert response.status_code == 400


def test_content_not_matching_extension_rejected(client, surveyor_token, seed_data):
    response = _upload(client, surveyor_token, seed_data["claim1"], "fake.jpg", b"not really a jpeg")
    assert response.status_code == 400


def test_invalid_evidence_type_rejected(client, surveyor_token, seed_data):
    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.jpg", JPG_BYTES, evidence_type="Not A Real Type")
    assert response.status_code == 400


def test_invalid_evidence_source_rejected(client, surveyor_token, seed_data):
    response = _upload(client, surveyor_token, seed_data["claim1"], "photo.jpg", JPG_BYTES, evidence_source="Nobody")
    assert response.status_code == 400


# ---------------------------------------------------------------- 20: path traversal


def test_filename_path_traversal_is_prevented(client, surveyor_token, seed_data, created_evidence_ids):
    response = _upload(client, surveyor_token, seed_data["claim1"], "../../../evil.jpg", JPG_BYTES)
    assert response.status_code == 201, response.text
    body = response.json()
    created_evidence_ids.append(body["Evidence_ID"])

    storage_root = Path(evidence_upload_module.settings.EVIDENCE_STORAGE_ROOT).resolve()
    stored_path = evidence_storage.storage_path_for(body["Claim_ID"], body["Evidence_ID"], "../../../evil.jpg")

    assert storage_root in stored_path.parents
    assert stored_path.parent == storage_root / seed_data["claim1"]
    assert stored_path.exists()
    assert ".." not in stored_path.name
