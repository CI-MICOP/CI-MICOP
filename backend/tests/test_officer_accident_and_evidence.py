"""Tests for the Claims Officer's Accident Information and Evidence
sections on GET /api/v1/officer/claims/{claim_id}, and the new
GET /api/v1/officer/claims/{claim_id}/evidence/{evidence_id}/image
endpoint.

Root cause this fixes: the officer claim-processing endpoint
(routers/officer.py::read_claim_processing_detail) never queried the
accidents or evidence tables at all - both are claim-scoped (Claim_ID is
a NOT NULL FK on each, no role restriction in the database or in
crud/accident.py, crud/evidence.py), so the frontend's "only exposed
through the Surveyor/Admin inspection API" warning did not describe an
actual backend restriction - it described code that simply never asked
for this data.
"""

import pytest

from app.db.session import SessionLocal
from app.db_models.accident import Accident
from tests.conftest import auth_headers
from tests.surveyor_records import active_claim1_inspection, surveyor_records  # noqa: F401 - fixtures
from tests.test_claim_creation import _payload, created_claim_ids  # noqa: F401 - fixtures/helpers

pytestmark = pytest.mark.usefixtures("active_claim1_inspection")


def _detail(client, token, claim_id):
    return client.get(f"/api/v1/officer/claims/{claim_id}", headers=auth_headers(token))


def _image(client, token, claim_id, evidence_id):
    return client.get(
        f"/api/v1/officer/claims/{claim_id}/evidence/{evidence_id}/image", headers=auth_headers(token)
    )


def _create_claim(client, customer_token, seed_data, **overrides):
    body = _payload(seed_data["policy1"], seed_data["vehicle1"], **overrides)
    response = client.post("/api/v1/claims", json=body, headers=auth_headers(customer_token))
    assert response.status_code == 201, response.text
    return response.json()["Claim_ID"], body


# ---------------------------------------------------------------- accident information


def test_officer_can_retrieve_accident_details_for_an_accessible_claim(
    client, customer1_token, officer_token, seed_data, created_claim_ids
):
    claim_id, body = _create_claim(
        client,
        customer1_token,
        seed_data,
        Accident_Time="14:45:00",
        Police_Report_Available=True,
        FIR_Number="FIR-2026-001",
        Third_Party_Involved=True,
        Injury_Reported=True,
    )
    created_claim_ids.append(claim_id)

    response = _detail(client, officer_token, claim_id)
    assert response.status_code == 200, response.text
    accidents = response.json()["accidents"]
    assert len(accidents) == 1
    accident = accidents[0]
    assert accident["Accident_Location"] == body["Place_of_Accident"]
    assert accident["Accident_Pincode"] == body["Accident_Pincode"]
    assert accident["Accident_Description"] == body["Claim_Description"]
    assert accident["Police_Report_Available"] is True
    assert accident["FIR_Number"] == "FIR-2026-001"
    assert accident["Third_Party_Involved"] is True
    assert accident["Injury_Reported"] is True


def test_missing_accident_record_returns_an_empty_list_not_fabricated_data(client, officer_token, seed_data):
    """seed_data's claim1 has no accidents row (only the claim-level
    Place_of_Accident/Accident_Pincode fields) - the endpoint must say so
    honestly, never invent a record."""
    response = _detail(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    db = SessionLocal()
    try:
        assert db.query(Accident).filter(Accident.Claim_ID == seed_data["claim1"]).count() == 0
    finally:
        db.close()
    assert response.json()["accidents"] == []


# ---------------------------------------------------------------- evidence metadata


def test_officer_can_retrieve_evidence_metadata_for_an_accessible_claim(
    client, officer_token, seed_data, surveyor_records
):
    photo = surveyor_records.capture_photo(latitude=13.0827, longitude=80.2707, accuracy_m=10.0)

    response = _detail(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    evidence = response.json()["evidence"]
    entry = next(e for e in evidence if e["Evidence_ID"] == photo["Evidence_ID"])
    assert entry["Evidence_Type"] == "Vehicle Damage Close-up"
    assert entry["Evidence_Source"] == "Surveyor"
    assert entry["Verification_Status"] == "Pending"
    assert entry["capture"]["checks"]["location_status"] == "captured"
    assert entry["capture"]["client"]["source"] == "gps"
    # No storage path is ever exposed.
    assert "path" not in str(entry).lower().replace("evidence_type", "")


def test_missing_evidence_returns_an_empty_list_not_a_warning(
    client, customer1_token, officer_token, seed_data, created_claim_ids
):
    claim_id, _ = _create_claim(client, customer1_token, seed_data)
    created_claim_ids.append(claim_id)

    response = _detail(client, officer_token, claim_id)
    assert response.status_code == 200, response.text
    assert response.json()["evidence"] == []


def test_evidence_without_a_surveyor_capture_record_shows_no_fabricated_capture_info(
    client, officer_token, seed_data, surveyor_records
):
    """An evidence row with no verified surveyor capture record (for
    example a dataset-imported row) must show capture: null, never a
    fabricated location."""
    photo = surveyor_records.capture_photo()
    db = SessionLocal()
    try:
        from app.db_models.evidence import Evidence
        from app.services import evidence_capture, evidence_storage

        row = db.query(Evidence).filter(Evidence.Evidence_ID == photo["Evidence_ID"]).first()
        path = evidence_storage.storage_path_for(row.Claim_ID, row.Evidence_ID, row.File_Name)
        evidence_capture.metadata_path_for(path).unlink()
    finally:
        db.close()

    response = _detail(client, officer_token, seed_data["claim1"])
    entry = next(e for e in response.json()["evidence"] if e["Evidence_ID"] == photo["Evidence_ID"])
    assert entry["capture"] is None


# ---------------------------------------------------------------- authorization (detail endpoint)


@pytest.mark.parametrize("token_fixture", ["customer1_token", "surveyor_token"])
def test_non_officer_roles_cannot_use_the_officer_claim_endpoint(client, seed_data, request, token_fixture):
    token = request.getfixturevalue(token_fixture)
    assert _detail(client, token, seed_data["claim1"]).status_code == 403


def test_unauthenticated_request_to_claim_detail_is_rejected(client, seed_data):
    response = client.get(f"/api/v1/officer/claims/{seed_data['claim1']}")
    assert response.status_code == 401


def test_nonexistent_claim_returns_404(client, officer_token):
    assert _detail(client, officer_token, "NO-SUCH-CLAIM").status_code == 404


def test_admin_can_also_retrieve_accidents_and_evidence(client, admin_token, seed_data, surveyor_records):
    surveyor_records.capture_photo()
    response = _detail(client, admin_token, seed_data["claim1"])
    assert response.status_code == 200
    assert "accidents" in response.json()
    assert "evidence" in response.json()


# ---------------------------------------------------------------- evidence image serving


def test_officer_can_view_an_evidence_image(client, officer_token, seed_data, surveyor_records):
    photo = surveyor_records.capture_photo()
    response = _image(client, officer_token, seed_data["claim1"], photo["Evidence_ID"])
    assert response.status_code == 200
    assert response.content.startswith(b"\xff\xd8\xff")
    assert response.headers["cache-control"] == "private, no-store"


def test_officer_cannot_view_evidence_through_a_different_claims_url(
    client, officer_token, seed_data, surveyor_records, other_surveyor_claim
):
    """The evidence id is real and belongs to claim1 - requesting it
    under a different, unrelated claim's URL must answer 404, never
    serve the file."""
    photo = surveyor_records.capture_photo()
    response = _image(client, officer_token, other_surveyor_claim["claim_id"], photo["Evidence_ID"])
    assert response.status_code == 404


def test_evidence_image_for_unknown_evidence_id_returns_404(client, officer_token, seed_data):
    assert _image(client, officer_token, seed_data["claim1"], "EVD-DOES-NOT-EXIST").status_code == 404


@pytest.mark.parametrize("token_fixture", ["customer1_token", "surveyor_token"])
def test_non_officer_roles_cannot_use_the_evidence_image_endpoint(
    client, seed_data, surveyor_records, request, token_fixture
):
    photo = surveyor_records.capture_photo()
    token = request.getfixturevalue(token_fixture)
    assert _image(client, token, seed_data["claim1"], photo["Evidence_ID"]).status_code == 403


def test_unauthenticated_request_to_evidence_image_is_rejected(client, seed_data, surveyor_records):
    photo = surveyor_records.capture_photo()
    response = client.get(f"/api/v1/officer/claims/{seed_data['claim1']}/evidence/{photo['Evidence_ID']}/image")
    assert response.status_code == 401


# ---------------------------------------------------------------- existing Surveyor/Admin behaviour unchanged


def test_surveyors_own_evidence_endpoints_still_work_unchanged(client, surveyor_token, seed_data, surveyor_records):
    photo = surveyor_records.capture_photo()
    detail = client.get(f"/api/v1/surveyor/claims/{seed_data['claim1']}", headers=auth_headers(surveyor_token))
    assert detail.status_code == 200
    assert [e["Evidence_ID"] for e in detail.json()["evidence"]] == [photo["Evidence_ID"]]

    image = client.get(
        f"/api/v1/surveyor/evidence/{photo['Evidence_ID']}/image", headers=auth_headers(surveyor_token)
    )
    assert image.status_code == 200 and image.content.startswith(b"\xff\xd8\xff")
