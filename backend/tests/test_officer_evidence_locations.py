"""Tests for GET /api/v1/officer/claims/{claim_id}/evidence/locations - the
Claims Officer's view of evidence location source/status
(services/evidence_capture.py claim_evidence_locations), added so an
officer can distinguish a GPS-verified capture from an indoor-friendly
map selection - never silently treated as equivalent.
"""

import pytest

from tests.conftest import auth_headers
from tests.surveyor_records import active_claim1_inspection, surveyor_records  # noqa: F401 - fixtures

pytestmark = pytest.mark.usefixtures("active_claim1_inspection")


def _locations(client, token, claim_id):
    return client.get(f"/api/v1/officer/claims/{claim_id}/evidence/locations", headers=auth_headers(token))


def test_officer_sees_gps_verified_and_map_selected_as_distinct(
    client, surveyor_token, officer_token, seed_data, surveyor_records
):
    gps_photo = surveyor_records.capture_photo(latitude=13.0827, longitude=80.2707, accuracy_m=10.0)
    map_photo = surveyor_records.capture_photo_at_map_location(latitude=13.09, longitude=80.28, address_label="T. Nagar")

    response = _locations(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    by_id = {row["Evidence_ID"]: row for row in response.json()["evidence"]}

    assert by_id[gps_photo["Evidence_ID"]]["capture"]["checks"]["location_status"] == "captured"
    assert by_id[gps_photo["Evidence_ID"]]["capture"]["client"]["source"] == "gps"
    assert by_id[gps_photo["Evidence_ID"]]["qualifying_capture"] is True

    assert by_id[map_photo["Evidence_ID"]]["capture"]["checks"]["location_status"] == "map_selected"
    assert by_id[map_photo["Evidence_ID"]]["capture"]["client"]["source"] == "map"
    assert by_id[map_photo["Evidence_ID"]]["capture"]["client"]["address_label"] == "T. Nagar"
    assert by_id[map_photo["Evidence_ID"]]["qualifying_capture"] is True


def test_officer_never_sees_a_storage_path(client, officer_token, seed_data, surveyor_records):
    photo = surveyor_records.capture_photo()
    response = _locations(client, officer_token, seed_data["claim1"])
    body = response.json()
    entry = next(row for row in body["evidence"] if row["Evidence_ID"] == photo["Evidence_ID"])
    assert "path" not in str(entry).lower().replace("qualifying_capture", "").replace("evidence_type", "")


def test_admin_can_also_view_evidence_locations(client, admin_token, seed_data, surveyor_records):
    surveyor_records.capture_photo()
    response = _locations(client, admin_token, seed_data["claim1"])
    assert response.status_code == 200


def test_customer_cannot_view_evidence_locations(client, customer1_token, seed_data):
    assert _locations(client, customer1_token, seed_data["claim1"]).status_code == 403


def test_surveyor_cannot_use_the_officer_endpoint(client, surveyor_token, seed_data):
    assert _locations(client, surveyor_token, seed_data["claim1"]).status_code == 403


def test_unauthenticated_request_is_rejected(client, seed_data):
    response = client.get(f"/api/v1/officer/claims/{seed_data['claim1']}/evidence/locations")
    assert response.status_code == 401


def test_nonexistent_claim_returns_404(client, officer_token, seed_data):
    assert _locations(client, officer_token, "NO-SUCH-CLAIM").status_code == 404


def test_claim_with_no_surveyor_photos_returns_an_empty_list(client, officer_token, seed_data):
    response = _locations(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200
    assert response.json()["evidence"] == []
