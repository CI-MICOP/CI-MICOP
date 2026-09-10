"""Tests for POST /api/v1/surveyor/repair-estimates (Step 5.8.7).

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py). seed_data's claim1 already has a surveyor_inspections
row for test_surveyor/employee_surveyor (inspection1) - that is what
"assigned" means under the project's existing model (see
docs/project_documentation/SURVEYOR_INSPECTION_WORKFLOW.md).
"""

from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.db_models.repair_estimate import RepairEstimate
from tests.conftest import auth_headers

VALID_PAYLOAD = {
    "Garage_ID": "GAR-0001",
    "Estimate_Date": "2026-09-01",
    "Repair_Estimate": "50000.00",
    "Repair_Cost": "52000.00",
    "Parts_Cost": "20000.00",
    "Labour_Cost": "15000.00",
    "Painting_Cost": "5000.00",
    "Replacement_Parts_Count": 2,
    "Repaired_Parts_Count": 1,
    "Estimated_Repair_Days": 7,
}


def _payload(claim_id, **overrides):
    body = dict(VALID_PAYLOAD)
    body["Claim_ID"] = claim_id
    body.update(overrides)
    return body


@pytest.fixture()
def created_estimate_ids():
    ids: list[str] = []
    yield ids
    if ids:
        db = SessionLocal()
        try:
            db.query(RepairEstimate).filter(RepairEstimate.Estimate_ID.in_(ids)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------- 1/2/3: auth + role


def test_unauthenticated_estimate_creation_returns_401(client, seed_data):
    response = client.post("/api/v1/surveyor/repair-estimates", json=_payload(seed_data["claim1"]))
    assert response.status_code == 401


def test_customer_cannot_create_estimate(client, customer1_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/repair-estimates", json=_payload(seed_data["claim1"]), headers=auth_headers(customer1_token)
    )
    assert response.status_code == 403


def test_claims_officer_cannot_create_estimate(client, officer_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/repair-estimates", json=_payload(seed_data["claim1"]), headers=auth_headers(officer_token)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- 4/5: assignment


def test_unassigned_surveyor_estimate_creation_rejected(client, surveyor_token, unassigned_claim):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(unassigned_claim),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


def test_wrong_surveyor_estimate_creation_rejected(client, surveyor_token, other_surveyor_claim):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(other_surveyor_claim["claim_id"]),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- 6: assigned surveyor succeeds


def test_assigned_surveyor_estimate_creation_succeeds(client, surveyor_token, seed_data, created_estimate_ids):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"]),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_estimate_ids.append(body["Estimate_ID"])

    assert body["Claim_ID"] == seed_data["claim1"]
    assert body["Vehicle_ID"] == seed_data["vehicle1"]
    assert body["Garage_ID"] == "GAR-0001"


# ---------------------------------------------------------------- 7: Vehicle_ID cannot be overridden


def test_supplied_vehicle_id_cannot_override_claim_vehicle_id(
    client, surveyor_token, seed_data, created_estimate_ids
):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], Vehicle_ID="SOME-OTHER-VEHICLE"),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_estimate_ids.append(body["Estimate_ID"])
    assert body["Vehicle_ID"] == seed_data["vehicle1"]
    assert body["Vehicle_ID"] != "SOME-OTHER-VEHICLE"


def test_supplied_surveyor_id_is_ignored(
    client, surveyor_token, seed_data, other_surveyor_claim, created_estimate_ids
):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], Surveyor_ID=other_surveyor_claim["employee_id"]),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    created_estimate_ids.append(response.json()["Estimate_ID"])
    # No Surveyor_ID field exists on RepairEstimate at all - this simply
    # proves the extra field is silently ignored, not used to impersonate.
    assert not hasattr(RepairEstimate, "Surveyor_ID")


# ---------------------------------------------------------------- 8: Estimate_ID generated server-side


def test_estimate_id_is_server_generated(client, surveyor_token, seed_data, created_estimate_ids):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], **{"Estimate_ID": "CLIENT-SUPPLIED-ID"}),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_estimate_ids.append(body["Estimate_ID"])
    assert body["Estimate_ID"] != "CLIENT-SUPPLIED-ID"
    assert body["Estimate_ID"].startswith("EST-")


# ---------------------------------------------------------------- 9/10: negative values rejected


@pytest.mark.parametrize(
    "field", ["Repair_Estimate", "Repair_Cost", "Parts_Cost", "Labour_Cost", "Painting_Cost"]
)
def test_negative_monetary_value_rejected(client, surveyor_token, seed_data, field):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], **{field: "-1"}),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "field", ["Replacement_Parts_Count", "Repaired_Parts_Count", "Estimated_Repair_Days", "Actual_Repair_Days"]
)
def test_negative_count_rejected(client, surveyor_token, seed_data, field):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], **{field: -1}),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


def test_blank_garage_id_rejected(client, surveyor_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], Garage_ID="   "),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- 11: valid estimate persists


def test_valid_estimate_persists_with_decimal_values(client, surveyor_token, seed_data, created_estimate_ids):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], Repair_Estimate="12345.67"),
        headers=auth_headers(surveyor_token),
    )
    estimate_id = response.json()["Estimate_ID"]
    created_estimate_ids.append(estimate_id)

    db = SessionLocal()
    try:
        row = db.query(RepairEstimate).filter(RepairEstimate.Estimate_ID == estimate_id).first()
        assert row.Repair_Estimate == Decimal("12345.67")
        assert row.Claim_ID == seed_data["claim1"]
        assert row.Vehicle_ID == seed_data["vehicle1"]
    finally:
        db.close()


def test_omitted_actual_repair_days_defaults_to_zero_not_a_real_zero_day_repair(
    client, surveyor_token, seed_data, created_estimate_ids
):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"]),
        headers=auth_headers(surveyor_token),
    )
    body = response.json()
    created_estimate_ids.append(body["Estimate_ID"])
    assert body["Actual_Repair_Days"] == 0


# ---------------------------------------------------------------- 12: multiple estimates coexist


def test_multiple_estimates_can_coexist_for_same_claim(client, surveyor_token, seed_data, created_estimate_ids):
    r1 = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], Garage_ID="GAR-0001"),
        headers=auth_headers(surveyor_token),
    )
    r2 = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"], Garage_ID="GAR-0002"),
        headers=auth_headers(surveyor_token),
    )
    assert r1.status_code == 201 and r2.status_code == 201
    created_estimate_ids += [r1.json()["Estimate_ID"], r2.json()["Estimate_ID"]]
    assert r1.json()["Estimate_ID"] != r2.json()["Estimate_ID"]

    db = SessionLocal()
    try:
        count = db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == seed_data["claim1"]).count()
        assert count >= 2
    finally:
        db.close()


# ---------------------------------------------------------------- 13: AI fields not fabricated


def test_ai_fields_are_not_fabricated_model_outputs(client, surveyor_token, seed_data, created_estimate_ids):
    response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json=_payload(seed_data["claim1"]),
        headers=auth_headers(surveyor_token),
    )
    body = response.json()
    created_estimate_ids.append(body["Estimate_ID"])
    assert body["Excessive_Claim_Amount_Indicator"] is False
    assert Decimal(str(body["Estimate_Anomaly_Score"])) == Decimal("0.0000")
