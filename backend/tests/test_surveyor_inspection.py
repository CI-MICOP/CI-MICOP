"""Tests for POST /api/v1/surveyor/inspections and the tightened
PATCH /api/v1/surveyor/inspections/{id} behavior (Step 5.8.5).

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py). seed_data's claim1 already has a *completed*
inspection (inspection1: Inspection_Status="Completed",
Survey_Report_Submitted=True) for test_surveyor/employee_surveyor - this
is what "assignment" means under the project's existing model (a
SurveyorInspection row establishes it), and it is not "active", so
test_surveyor may legitimately start a new (re-)inspection on claim1.
"""

import pytest

from app.db.session import SessionLocal
from app.db_models.surveyor_inspection import SurveyorInspection
from tests.conftest import auth_headers

# unassigned_claim and other_surveyor_claim fixtures live in conftest.py -
# shared with tests/test_vehicle_damage.py and tests/test_evidence.py.

INSPECTION_ID_PATTERN = "INSP-"


@pytest.fixture()
def created_inspection_ids():
    ids: list[str] = []
    yield ids
    if ids:
        db = SessionLocal()
        try:
            db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID.in_(ids)).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------- A/B/C: role + auth


def test_customer_cannot_create_inspection(client, customer1_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(customer1_token),
    )
    assert response.status_code == 403


def test_claims_officer_cannot_create_inspection(client, officer_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 403


def test_unauthenticated_create_inspection_returns_401(client, seed_data):
    response = client.post("/api/v1/surveyor/inspections", json={"Claim_ID": seed_data["claim1"]})
    assert response.status_code == 401


# ---------------------------------------------------------------- D/E: assignment


def test_surveyor_cannot_create_inspection_for_unassigned_claim(client, surveyor_token, unassigned_claim):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": unassigned_claim},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


def test_surveyor_cannot_create_inspection_for_another_surveyors_assigned_claim(
    client, surveyor_token, other_surveyor_claim
):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": other_surveyor_claim["claim_id"]},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- F: impersonation


def test_surveyor_cannot_supply_another_surveyor_id(
    client, surveyor_token, seed_data, other_surveyor_claim, created_inspection_ids
):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"], "Surveyor_ID": other_surveyor_claim["employee_id"]},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_inspection_ids.append(body["Inspection_ID"])
    assert body["Surveyor_ID"] == seed_data["employee_surveyor"]
    assert body["Surveyor_ID"] != other_surveyor_claim["employee_id"]


# ---------------------------------------------------------------- H/2/3/4/5: valid creation


def test_surveyor_can_create_inspection_for_their_assigned_claim(
    client, surveyor_token, seed_data, created_inspection_ids
):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_inspection_ids.append(body["Inspection_ID"])

    assert body["Inspection_ID"].startswith(INSPECTION_ID_PATTERN)
    assert body["Surveyor_ID"] == seed_data["employee_surveyor"]
    assert body["Claim_ID"] == seed_data["claim1"]
    assert body["Inspection_Status"] == "Assigned"
    assert body["Survey_Report_Submitted"] is False
    assert body["Vehicle_Condition"] == "Pending"
    assert body["Damage_Observed"] == "Pending"
    assert body["Parts_Required"] == 0


def test_inspection_persists_in_postgresql(client, surveyor_token, seed_data, created_inspection_ids):
    response = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    )
    inspection_id = response.json()["Inspection_ID"]
    created_inspection_ids.append(inspection_id)

    db = SessionLocal()
    try:
        row = db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == inspection_id).first()
        assert row is not None
        assert row.Claim_ID == seed_data["claim1"]
        assert row.Surveyor_ID == seed_data["employee_surveyor"]
        assert row.Survey_Report_Submitted is False
    finally:
        db.close()


# ---------------------------------------------------------------- G: duplicate prevention


def test_duplicate_active_inspection_is_rejected(client, surveyor_token, seed_data, created_inspection_ids):
    first = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    )
    assert first.status_code == 201
    created_inspection_ids.append(first.json()["Inspection_ID"])

    second = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    )
    assert second.status_code == 409


# ---------------------------------------------------------------- I/J/K: update ownership


def test_surveyor_can_update_their_own_inspection(client, surveyor_token, seed_data, created_inspection_ids):
    created = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    ).json()
    created_inspection_ids.append(created["Inspection_ID"])

    response = client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={"Vehicle_Condition": "Good"},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 200
    assert response.json()["Vehicle_Condition"] == "Good"


def test_surveyor_cannot_update_another_surveyors_inspection(client, surveyor_token, other_surveyor_claim):
    response = client.patch(
        f"/api/v1/surveyor/inspections/{other_surveyor_claim['inspection_id']}",
        json={"Vehicle_Condition": "Good"},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


def test_surveyor_cannot_submit_another_surveyors_report(client, surveyor_token, other_surveyor_claim):
    response = client.patch(
        f"/api/v1/surveyor/inspections/{other_surveyor_claim['inspection_id']}",
        json={"Survey_Report_Submitted": True},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- update persistence + report submission


def test_update_persists(client, surveyor_token, seed_data, created_inspection_ids):
    created = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    ).json()
    created_inspection_ids.append(created["Inspection_ID"])

    client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={"Vehicle_Condition": "Poor", "Surveyor_Comments": "Visible dent on rear door."},
        headers=auth_headers(surveyor_token),
    )

    db = SessionLocal()
    try:
        row = db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == created["Inspection_ID"]).first()
        assert row.Vehicle_Condition == "Poor"
        assert row.Surveyor_Comments == "Visible dent on rear door."
    finally:
        db.close()


def test_incomplete_report_cannot_be_submitted(client, surveyor_token, seed_data, created_inspection_ids):
    created = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    ).json()
    created_inspection_ids.append(created["Inspection_ID"])

    response = client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={"Survey_Report_Submitted": True},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 400

    db = SessionLocal()
    try:
        row = db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == created["Inspection_ID"]).first()
        assert row.Survey_Report_Submitted is False
    finally:
        db.close()


def test_report_submission_persists_and_completes_status(client, surveyor_token, seed_data, created_inspection_ids):
    created = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    ).json()
    created_inspection_ids.append(created["Inspection_ID"])

    client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={
            "Vehicle_Condition": "Fair",
            "Damage_Observed": "Yes",
            "Damage_Severity": "Minor",
            "Repair_Recommendation": "Repair",
        },
        headers=auth_headers(surveyor_token),
    )
    response = client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={"Survey_Report_Submitted": True},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["Survey_Report_Submitted"] is True
    assert body["Inspection_Status"] == "Completed"

    db = SessionLocal()
    try:
        row = db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == created["Inspection_ID"]).first()
        assert row.Survey_Report_Submitted is True
        assert row.Inspection_Status == "Completed"
    finally:
        db.close()


# ---------------------------------------------------------------- schema-level value constraints


def test_unsupported_inspection_status_rejected(client, surveyor_token, seed_data, created_inspection_ids):
    created = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    ).json()
    created_inspection_ids.append(created["Inspection_ID"])

    response = client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={"Inspection_Status": "Made Up Status"},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


def test_negative_parts_required_rejected(client, surveyor_token, seed_data, created_inspection_ids):
    created = client.post(
        "/api/v1/surveyor/inspections",
        json={"Claim_ID": seed_data["claim1"]},
        headers=auth_headers(surveyor_token),
    ).json()
    created_inspection_ids.append(created["Inspection_ID"])

    response = client.patch(
        f"/api/v1/surveyor/inspections/{created['Inspection_ID']}",
        json={"Parts_Required": -1},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422
