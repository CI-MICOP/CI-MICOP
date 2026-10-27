"""Tests for surveyor evidence: the retired file upload (POST
/api/v1/surveyor/evidence, now 410) and in-app camera capture (POST
/api/v1/surveyor/evidence/capture).

Database-backed (see tests/conftest.py) and using the real local
filesystem storage; every evidence row and file created here is removed
afterward by the surveyor_records fixture. Deferred until a test database
is available - tests/test_survey_report_rules.py covers the same rules
without a database.
"""

import pytest

from app.db.session import SessionLocal
from app.db_models.evidence import Evidence
from app.services import evidence_capture, evidence_storage
from tests.conftest import auth_headers
from tests.surveyor_records import active_claim1_inspection, real_jpeg, surveyor_records  # noqa: F401 - fixtures

# Damage/evidence writes need an active, scheduled, complete inspection
# (services/surveyor_workflow.py); seed_data inspection1 is already submitted.
pytestmark = pytest.mark.usefixtures("active_claim1_inspection")


def _capture(client, token, claim_id, content=None, **fields):
    data = {"claim_id": claim_id, "evidence_type": "Vehicle Damage Close-up", "latitude": "13.08", "longitude": "80.27", "accuracy_m": "10"}
    data.update(fields)
    return client.post(
        "/api/v1/surveyor/evidence/capture",
        headers=auth_headers(token) if token else {},
        data=data,
        files={"photo": ("capture.jpg", real_jpeg() if content is None else content, "image/jpeg")},
    )


@pytest.fixture()
def created_evidence_ids():
    """Evidence rows other suites create through _upload, removed afterwards
    with their photos and capture records."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    db = SessionLocal()
    try:
        for row in db.query(Evidence).filter(Evidence.Evidence_ID.in_(ids)).all():
            path = evidence_storage.storage_path_for(row.Claim_ID, row.Evidence_ID, row.File_Name)
            evidence_storage.delete_file(path)
            evidence_storage.delete_file(evidence_capture.metadata_path_for(path))
        db.query(Evidence).filter(Evidence.Evidence_ID.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _upload(client, token, claim_id, filename, content, content_type="image/jpeg", **fields):
    """Stores a surveyor photo for suites that need evidence rows (duplicate,
    quality and live-signal checks). The file-upload endpoint is retired, so
    this goes through the camera-capture endpoint - the only way a surveyor
    photo is stored. `filename` and `content_type` are accepted for the
    callers' signature; the server names the file and checks the bytes."""
    return _capture(client, token, claim_id, content, **fields)


def test_file_upload_endpoint_is_retired(surveyor_records):
    assert surveyor_records.legacy_upload().status_code == 410


@pytest.mark.parametrize("token_fixture", ["customer1_token", "officer_token", "admin_token"])
def test_only_surveyors_can_capture(client, seed_data, request, token_fixture):
    token = request.getfixturevalue(token_fixture)
    assert _capture(client, token, seed_data["claim1"]).status_code == 403


def test_unauthenticated_capture_returns_401(client, seed_data):
    assert _capture(client, None, seed_data["claim1"]).status_code == 401


def test_unassigned_and_other_surveyors_claims_are_rejected(client, surveyor_token, unassigned_claim, other_surveyor_claim):
    assert _capture(client, surveyor_token, unassigned_claim).status_code == 403
    assert _capture(client, surveyor_token, other_surveyor_claim["claim_id"]).status_code == 403


def test_capture_persists_photo_metadata_and_capture_record(client, surveyor_token, seed_data, surveyor_records):
    response = _capture(client, surveyor_token, seed_data["claim1"], surveyor_employee_id="FORGED")
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    assert body["Evidence_Source"] == "Surveyor"
    assert body["Evidence_Type"] == "Vehicle Damage Close-up"
    assert body["capture"]["server"]["surveyor_employee_id"] == seed_data["employee_surveyor"]
    assert body["qualifying_capture"] is True

    path = evidence_storage.storage_path_for(body["Claim_ID"], body["Evidence_ID"], body["File_Name"])
    assert path.is_file()
    assert evidence_capture.metadata_path_for(path).is_file()


@pytest.mark.parametrize(
    "content, fields",
    [
        (b"\xff\xd8\xff" + b"garbage" * 5, {}),
        (b"%PDF-1.7", {}),
        (None, {"evidence_type": "Damage Photo"}),  # dataset types are not capture types
        (None, {"evidence_date": "2099-01-01"}),
        (None, {"latitude": "123"}),
    ],
)
def test_invalid_captures_are_rejected(client, surveyor_token, seed_data, content, fields):
    assert _capture(client, surveyor_token, seed_data["claim1"], content=content, **fields).status_code == 400


def test_surveyor_sees_only_their_own_captures(client, surveyor_token, seed_data, surveyor_records):
    body = _capture(client, surveyor_token, seed_data["claim1"]).json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    detail = client.get(f"/api/v1/surveyor/claims/{seed_data['claim1']}", headers=auth_headers(surveyor_token)).json()
    assert [e["Evidence_ID"] for e in detail["evidence"]] == [body["Evidence_ID"]]
    image = client.get(f"/api/v1/surveyor/evidence/{body['Evidence_ID']}/image", headers=auth_headers(surveyor_token))
    assert image.status_code == 200 and image.content.startswith(b"\xff\xd8\xff")


def test_customer_cannot_see_surveyor_photos(client, customer1_token, surveyor_token, seed_data, surveyor_records):
    body = _capture(client, surveyor_token, seed_data["claim1"]).json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    for path in (f"/api/v1/surveyor/evidence/{body['Evidence_ID']}/image", f"/api/v1/surveyor/claims/{seed_data['claim1']}"):
        assert client.get(path, headers=auth_headers(customer1_token)).status_code == 403
    documents = client.get(f"/api/v1/documents?claim_id={seed_data['claim1']}", headers=auth_headers(customer1_token)).json()
    assert body["Evidence_ID"] not in {d["Document_ID"] for d in documents}
