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

from app.crud import evidence as crud_evidence
from app.db.session import SessionLocal
from app.db_models.evidence import Evidence
from app.services import evidence_capture, evidence_storage
from tests.conftest import TEST_PASSWORD, auth_headers, get_token
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


# ---------------------------------------------------------------- indoor-friendly location (GPS + map fallback)


def test_gps_accuracy_within_threshold_is_captured_and_qualifies(client, surveyor_token, seed_data, surveyor_records):
    response = _capture(client, surveyor_token, seed_data["claim1"], accuracy_m="10")
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    assert body["capture"]["checks"]["location_status"] == "captured"
    assert body["capture"]["client"]["source"] == "gps"
    assert body["qualifying_capture"] is True


def test_gps_accuracy_worse_than_threshold_is_recorded_not_blocked(client, surveyor_token, seed_data, surveyor_records):
    """The original complaint: poor GPS accuracy must never block the
    upload outright - it is saved, flagged, and simply does not qualify
    on its own (the surveyor is expected to retry GPS or use the map)."""
    response = _capture(client, surveyor_token, seed_data["claim1"], accuracy_m="850")
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    assert body["capture"]["checks"]["location_status"] == "accuracy_insufficient"
    assert body["qualifying_capture"] is False


def _capture_without_coordinates(client, token, claim_id, **fields):
    """Like _capture, but latitude/longitude/accuracy_m are left out of the
    form entirely (an empty string is itself an invalid float and would be
    a 422, not "not provided" - this is the correct way to simulate GPS
    giving nothing at all)."""
    data = {"claim_id": claim_id, "evidence_type": "Vehicle Damage Close-up"}
    data.update(fields)
    return client.post(
        "/api/v1/surveyor/evidence/capture",
        headers=auth_headers(token) if token else {},
        data=data,
        files={"photo": ("capture.jpg", real_jpeg(), "image/jpeg")},
    )


def test_gps_permission_denied_is_recorded_not_blocked(client, surveyor_token, seed_data, surveyor_records):
    response = _capture_without_coordinates(client, surveyor_token, seed_data["claim1"], location_error="permission_denied")
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    assert body["capture"]["checks"]["location_status"] == "unavailable"
    assert body["capture"]["client"]["error"] == "permission_denied"
    assert body["qualifying_capture"] is False


def test_gps_timeout_is_recorded_not_blocked(client, surveyor_token, seed_data, surveyor_records):
    response = _capture_without_coordinates(client, surveyor_token, seed_data["claim1"], location_error="timeout")
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    assert body["capture"]["checks"]["location_status"] == "unavailable"
    assert body["capture"]["client"]["error"] == "timeout"


def test_map_selected_location_is_stored_as_map_selected_not_gps_verified(
    client, surveyor_token, seed_data, surveyor_records
):
    response = _capture_without_coordinates(
        client, surveyor_token, seed_data["claim1"],
        latitude="13.0827", longitude="80.2707",
        location_source="map", address_label="Anna Salai, Chennai",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    assert body["capture"]["checks"]["location_status"] == "map_selected"
    assert body["capture"]["checks"]["location_status"] != "captured"
    assert body["capture"]["client"]["source"] == "map"
    assert body["capture"]["client"]["accuracy_m"] is None
    assert body["capture"]["client"]["address_label"] == "Anna Salai, Chennai"
    # Indoor-friendly fallback: an explicit map pick does qualify, same as a good GPS fix.
    assert body["qualifying_capture"] is True


def test_map_selection_cannot_be_upgraded_to_gps_verified_by_the_client(
    client, surveyor_token, seed_data, surveyor_records
):
    """A map-selected point cannot be relabelled gps-verified just by
    submitting different request fields - the server derives the status
    from location_source + coordinates; there is no status field at all."""
    response = _capture(
        client, surveyor_token, seed_data["claim1"],
        latitude="13.0827", longitude="80.2707", accuracy_m="5",
        location_source="map", address_label="Anna Salai, Chennai",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    surveyor_records.evidence_ids.append(body["Evidence_ID"])
    # Even though a plausible "accuracy_m" was also sent, a map pick never
    # becomes "captured" (gps-verified) - accuracy only applies to GPS.
    assert body["capture"]["checks"]["location_status"] == "map_selected"
    assert body["capture"]["client"]["accuracy_m"] is None


def test_map_selection_requires_valid_coordinates(client, surveyor_token, seed_data):
    missing = _capture_without_coordinates(client, surveyor_token, seed_data["claim1"], location_source="map")
    assert missing.status_code == 400

    out_of_range = _capture(
        client, surveyor_token, seed_data["claim1"], latitude="999", longitude="80.27", location_source="map"
    )
    assert out_of_range.status_code == 400


def test_unsupported_location_source_is_rejected(client, surveyor_token, seed_data):
    response = _capture(client, surveyor_token, seed_data["claim1"], location_source="satellite")
    assert response.status_code == 400


def test_invalid_map_selection_leaves_no_evidence_or_file_behind(client, surveyor_token, seed_data):
    """A rejected (400) capture must never leave a half-created evidence
    row or an orphaned stored file."""
    before = db_evidence_count(seed_data["claim1"])
    response = _capture_without_coordinates(client, surveyor_token, seed_data["claim1"], location_source="map")
    assert response.status_code == 400
    assert db_evidence_count(seed_data["claim1"]) == before


def db_evidence_count(claim_id: str) -> int:
    db = SessionLocal()
    try:
        return db.query(Evidence).filter(Evidence.Claim_ID == claim_id).count()
    finally:
        db.close()


# ---------------------------------------------------------------- keep / delete before submission


def test_surveyor_can_keep_a_saved_photo_before_submission(client, surveyor_token, surveyor_records):
    body = surveyor_records.capture_photo()
    response = client.patch(
        f"/api/v1/surveyor/evidence/{body['Evidence_ID']}", json={"kept": True}, headers=auth_headers(surveyor_token)
    )
    assert response.status_code == 200, response.text
    assert response.json()["capture"]["review"]["kept"] is True

    # The surveyor can change their mind while the survey stays editable.
    response = client.patch(
        f"/api/v1/surveyor/evidence/{body['Evidence_ID']}", json={"kept": False}, headers=auth_headers(surveyor_token)
    )
    assert response.status_code == 200, response.text
    assert response.json()["capture"]["review"]["kept"] is False
    # Keeping/un-keeping is a review decision only - it never changes
    # whether the photo counts toward the surveyor-photo requirement.
    assert response.json()["qualifying_capture"] is True


def test_surveyor_can_delete_a_saved_photo_before_submission(client, surveyor_token, seed_data, surveyor_records):
    before = db_evidence_count(seed_data["claim1"])
    body = surveyor_records.capture_photo()
    evidence_id = body["Evidence_ID"]
    path = evidence_storage.storage_path_for(body["Claim_ID"], evidence_id, body["File_Name"])
    assert path.is_file()

    response = client.delete(f"/api/v1/surveyor/evidence/{evidence_id}", headers=auth_headers(surveyor_token))
    assert response.status_code == 204, response.text
    surveyor_records.evidence_ids.remove(evidence_id)  # already gone - nothing left for cleanup to do

    assert db_evidence_count(seed_data["claim1"]) == before
    assert not path.is_file()
    assert not evidence_capture.metadata_path_for(path).is_file()

    detail = client.get(f"/api/v1/surveyor/claims/{seed_data['claim1']}", headers=auth_headers(surveyor_token)).json()
    assert evidence_id not in [e["Evidence_ID"] for e in detail["evidence"]]


def test_deleting_one_photo_does_not_affect_another_evidence_file(client, surveyor_token, surveyor_records):
    """Each stored file name embeds its own Evidence_ID
    (services/evidence_storage.py), so no two evidence rows ever share a
    file - deleting one must never touch another's photo."""
    first = surveyor_records.capture_photo()
    second = surveyor_records.capture_photo()
    second_path = evidence_storage.storage_path_for(second["Claim_ID"], second["Evidence_ID"], second["File_Name"])

    response = client.delete(f"/api/v1/surveyor/evidence/{first['Evidence_ID']}", headers=auth_headers(surveyor_token))
    assert response.status_code == 204, response.text
    surveyor_records.evidence_ids.remove(first["Evidence_ID"])

    assert second_path.is_file()
    image = client.get(f"/api/v1/surveyor/evidence/{second['Evidence_ID']}/image", headers=auth_headers(surveyor_token))
    assert image.status_code == 200


def test_surveyor_cannot_keep_or_delete_another_surveyors_evidence(
    client, surveyor_token, other_surveyor_claim, created_evidence_ids
):
    other_token = get_token(client, "test_surveyor2", TEST_PASSWORD)
    capture = client.post(
        "/api/v1/surveyor/evidence/capture",
        headers=auth_headers(other_token),
        data={
            "claim_id": other_surveyor_claim["claim_id"],
            "evidence_type": "Vehicle Damage Close-up",
            "latitude": "13.08",
            "longitude": "80.27",
            "accuracy_m": "10",
        },
        files={"photo": ("capture.jpg", real_jpeg(), "image/jpeg")},
    )
    assert capture.status_code == 201, capture.text
    other_evidence_id = capture.json()["Evidence_ID"]
    created_evidence_ids.append(other_evidence_id)

    assert (
        client.patch(
            f"/api/v1/surveyor/evidence/{other_evidence_id}", json={"kept": True}, headers=auth_headers(surveyor_token)
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/surveyor/evidence/{other_evidence_id}", headers=auth_headers(surveyor_token)).status_code
        == 404
    )
    # surveyor2 can still manage their own photo.
    assert (
        client.patch(
            f"/api/v1/surveyor/evidence/{other_evidence_id}", json={"kept": True}, headers=auth_headers(other_token)
        ).status_code
        == 200
    )


def test_keep_and_delete_of_unknown_evidence_id_return_404(client, surveyor_token):
    assert (
        client.patch(
            "/api/v1/surveyor/evidence/EVD-DOES-NOT-EXIST", json={"kept": True}, headers=auth_headers(surveyor_token)
        ).status_code
        == 404
    )
    assert (
        client.delete("/api/v1/surveyor/evidence/EVD-DOES-NOT-EXIST", headers=auth_headers(surveyor_token)).status_code
        == 404
    )


def test_submitted_survey_evidence_cannot_be_kept_or_deleted(
    client, surveyor_token, surveyor_records, active_claim1_inspection
):
    body = surveyor_records.capture_photo()
    submit = surveyor_records.patch(active_claim1_inspection["Inspection_ID"], {"Survey_Report_Submitted": True})
    assert submit.status_code == 200, submit.text

    assert (
        client.patch(
            f"/api/v1/surveyor/evidence/{body['Evidence_ID']}", json={"kept": True}, headers=auth_headers(surveyor_token)
        ).status_code
        == 409
    )
    assert (
        client.delete(f"/api/v1/surveyor/evidence/{body['Evidence_ID']}", headers=auth_headers(surveyor_token)).status_code
        == 409
    )


def test_failed_deletion_leaves_consistent_database_and_storage_state(
    client, surveyor_token, seed_data, surveyor_records, monkeypatch
):
    body = surveyor_records.capture_photo()
    path = evidence_storage.storage_path_for(body["Claim_ID"], body["Evidence_ID"], body["File_Name"])

    def _boom(db, evidence):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(crud_evidence, "delete", _boom)
    response = client.delete(f"/api/v1/surveyor/evidence/{body['Evidence_ID']}", headers=auth_headers(surveyor_token))
    assert response.status_code == 500

    assert db_evidence_count(seed_data["claim1"]) >= 1
    assert path.is_file()
    assert evidence_capture.metadata_path_for(path).is_file()
