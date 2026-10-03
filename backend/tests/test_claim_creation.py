"""Tests for POST /api/v1/claims - the customer FNOL submission endpoint.

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py); every claim/accident row created here is removed by
the created_claim_ids fixture regardless of test outcome.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.db_models.accident import Accident
from app.db_models.claim import Claim
from app.db_models.vehicle import Vehicle
from tests.conftest import auth_headers

VALID_PAYLOAD = {
    "Claim_Date": "2026-09-01",
    "Claim_Type": "Own Damage",
    "Claim_Amount": "50000.00",
    "Claim_Description": "Front bumper damage from a minor collision.",
    "Place_of_Accident": "Test City",
    "Accident_Pincode": "123456",
    "Third_Party_Involved": False,
    "Injury_Reported": False,
}


def _payload(policy_id, vehicle_id, **overrides):
    body = dict(VALID_PAYLOAD)
    body["Policy_ID"] = policy_id
    body["Vehicle_ID"] = vehicle_id
    body.update(overrides)
    return body


@pytest.fixture()
def created_claim_ids():
    """Claim_IDs created by a test - their Accident + Claim rows are
    deleted afterward regardless of pass/fail."""
    ids: list[str] = []
    yield ids
    if ids:
        db = SessionLocal()
        try:
            db.query(Accident).filter(Accident.Claim_ID.in_(ids)).delete(synchronize_session=False)
            db.query(Claim).filter(Claim.Claim_ID.in_(ids)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


@pytest.fixture(scope="module")
def unlinked_vehicle(seed_data):
    """A second vehicle owned by customer1 but not linked to any policy -
    used to test the policy/vehicle mismatch rejection (Part 3E)."""
    db = SessionLocal()
    vehicle_id = "TEST-VEH-0002"
    vehicle = Vehicle(
        Vehicle_ID=vehicle_id,
        Customer_ID=seed_data["customer1"],
        Policy_ID=None,
        Vehicle_Type="Car - Hatchback",
        Vehicle_Subtype=None,
        Registration_Number="TEST-REG-0002",
        Chassis_Number="TEST-CHS-0002",
        Engine_Number="TEST-ENG-0002",
        Vehicle_Color="Black",
        Make="TestMake",
        Make_Code="MC001",
        Model="TestModel2",
        Variant="Base",
        Manufacturing_Year=2021,
        Registration_Year=2021,
        Vehicle_Age=4,
        Fuel_Type="Petrol",
        Engine_CC=1000,
        CC_PCC_GVW_Code="CC01",
        Vehicle_Value=Decimal("600000.00"),
        Usage_Type="Private",
        GVW_KG=None,
        Load_Capacity_KG=None,
        Seating_Capacity=5,
        Permit_Code=None,
        Nature_of_Goods_Code=None,
        Road_Type_Code="RT01",
        Vehicle_Driven_By_Code="DB01",
        RTA_Location_Code="RTA001",
        Class_Code="CL01",
        Zone_Code="Z01",
        Previous_Claim_Count=0,
        Policy_Start_Date=date(2025, 1, 1),
        Policy_End_Date=date(2026, 1, 1),
    )
    db.add(vehicle)
    db.commit()
    db.close()

    yield vehicle_id

    db = SessionLocal()
    db.query(Vehicle).filter(Vehicle.Vehicle_ID == vehicle_id).delete()
    db.commit()
    db.close()


# ---------------------------------------------------------------- A/B/C: auth + role


def test_authenticated_customer_can_create_a_valid_claim(client, customer1_token, seed_data, created_claim_ids):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert response.status_code == 201, response.text
    body = response.json()
    created_claim_ids.append(body["Claim_ID"])

    assert body["Claim_ID"]
    assert body["Claim_Number"]
    assert body["Policy_ID"] == seed_data["policy1"]
    assert body["Vehicle_ID"] == seed_data["vehicle1"]
    assert body["Customer_ID"] == seed_data["customer1"]
    assert body["Claim_Status"] == "Under Review"
    assert body["Final_Decision"] == "Pending"
    assert Decimal(str(body["Approved_Amount"])) == Decimal("0.00")


def test_unauthenticated_request_returns_401(client, seed_data):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload)
    assert response.status_code == 401


def test_non_customer_role_cannot_create_a_customer_claim(client, surveyor_token, seed_data):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(surveyor_token))
    assert response.status_code == 403


# ---------------------------------------------------------------- D/E/F: ownership + mismatch


def test_customer_cannot_use_another_customers_policy(client, customer2_token, seed_data):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer2_token))
    assert response.status_code == 403


def test_customer_cannot_use_another_customers_vehicle(client, customer1_token, customer2_token, seed_data, created_claim_ids):
    """customer2 owns no vehicle at all - using customer1's vehicle (with
    a policy customer2 also doesn't own) must be rejected, never accepted."""
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer2_token))
    assert response.status_code in (400, 403, 404)

    # Sanity check: the same payload succeeds for the actual owner, proving
    # the rejection above was an ownership check, not a broken endpoint.
    control = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert control.status_code == 201
    created_claim_ids.append(control.json()["Claim_ID"])


def test_policy_vehicle_mismatch_is_rejected(client, customer1_token, seed_data, unlinked_vehicle):
    payload = _payload(seed_data["policy1"], unlinked_vehicle)
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert response.status_code == 400


# ---------------------------------------------------------------- G/H/I: ID + number generation


def test_claim_id_and_number_are_generated_and_unique(client, customer1_token, seed_data, created_claim_ids):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    r1 = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    r2 = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert r1.status_code == 201 and r2.status_code == 201
    b1, b2 = r1.json(), r2.json()
    created_claim_ids += [b1["Claim_ID"], b2["Claim_ID"]]

    assert b1["Claim_ID"] != b2["Claim_ID"]
    assert b1["Claim_Number"] != b2["Claim_Number"]
    assert b1["Claim_Number"] != "DEV-CLAIM-001"
    assert b1["Claim_Number"].startswith("CLM-")
    assert b1["Claim_ID"].startswith("CLM-")


# ---------------------------------------------------------------- J/K: persistence + initial state


def test_created_claim_persists_in_postgresql(client, customer1_token, seed_data, created_claim_ids):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    claim_id = response.json()["Claim_ID"]
    created_claim_ids.append(claim_id)

    db = SessionLocal()
    try:
        row = db.query(Claim).filter(Claim.Claim_ID == claim_id).first()
        assert row is not None
        assert row.Claim_Status == "Under Review"
        assert row.Final_Decision == "Pending"
    finally:
        db.close()


def test_new_claim_starts_under_review_pending(client, customer1_token, seed_data, created_claim_ids):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    body = response.json()
    created_claim_ids.append(body["Claim_ID"])
    assert body["Claim_Status"] == "Under Review"
    assert body["Final_Decision"] == "Pending"


def test_accident_child_row_is_created_with_submitted_details(client, customer1_token, seed_data, created_claim_ids):
    payload = _payload(
        seed_data["policy1"], seed_data["vehicle1"], Third_Party_Involved=True, Injury_Reported=True
    )
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    claim_id = response.json()["Claim_ID"]
    created_claim_ids.append(claim_id)

    db = SessionLocal()
    try:
        accident = db.query(Accident).filter(Accident.Claim_ID == claim_id).first()
        assert accident is not None
        assert accident.Third_Party_Involved is True
        assert accident.Injury_Reported is True
        assert accident.Accident_Pincode == payload["Accident_Pincode"]
    finally:
        db.close()


def test_fir_number_is_stored_on_the_accident_row(client, customer1_token, seed_data, created_claim_ids):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"], FIR_Number="123/2026", Police_Report_Available=True)
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert response.status_code == 201, response.text
    claim_id = response.json()["Claim_ID"]
    created_claim_ids.append(claim_id)

    db = SessionLocal()
    try:
        accident = db.query(Accident).filter(Accident.Claim_ID == claim_id).first()
        assert accident.FIR_Number == "123/2026"
        assert accident.Police_Report_Available is True
    finally:
        db.close()


def test_fir_number_longer_than_the_column_is_rejected_cleanly(client, customer1_token, seed_data):
    payload = _payload(seed_data["policy1"], seed_data["vehicle1"], FIR_Number="X" * 31)
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert response.status_code == 422


# ---------------------------------------------------------------- L: rollback on child failure


def test_transaction_rolls_back_if_accident_creation_fails(client, customer1_token, seed_data, monkeypatch):
    import app.services.claim_creation as claim_creation_module

    fixed_claim_id = "TEST-CLM-ROLLBACK"
    monkeypatch.setattr(claim_creation_module.crud_claim, "generate_claim_id", lambda db: fixed_claim_id)

    def _boom(db, accident):
        raise RuntimeError("simulated accident insert failure")

    monkeypatch.setattr(claim_creation_module.crud_accident, "create", _boom)

    payload = _payload(seed_data["policy1"], seed_data["vehicle1"])
    response = client.post("/api/v1/claims", json=payload, headers=auth_headers(customer1_token))
    assert response.status_code == 500

    db = SessionLocal()
    try:
        assert db.query(Claim).filter(Claim.Claim_ID == fixed_claim_id).first() is None
    finally:
        db.close()
