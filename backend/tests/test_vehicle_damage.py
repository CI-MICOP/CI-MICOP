"""Tests for POST /api/v1/surveyor/vehicle-damage and
PATCH /api/v1/surveyor/vehicle-damage/{damage_id} (Step 5.8.6, and the
"Correct this step" edit added afterward).

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py). seed_data's claim1 already has a surveyor_inspections
row for test_surveyor/employee_surveyor (inspection1) - that is what
"assigned" means under the project's existing model (see
docs/project_documentation/SURVEYOR_INSPECTION_WORKFLOW.md).
"""

from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.db_models.vehicle_damage import VehicleDamage
from tests.conftest import auth_headers
from tests.surveyor_records import DAMAGE_FIELDS, active_claim1_inspection, surveyor_records  # noqa: F401 - fixtures

# Damage/evidence writes need an active, scheduled, complete inspection
# (services/surveyor_workflow.py); seed_data inspection1 is already submitted.
pytestmark = pytest.mark.usefixtures("active_claim1_inspection")

VALID_PAYLOAD = {
    "Damage_Type": "Front Damage",
    "Damaged_Part": "Bumper",
    "Damage_Severity": "Minor",
    "Damage_Location": "Front",
    "Estimated_Damage_Cost": "15000.00",
    "Repair_or_Replace": "Repair",
    "Photo_Evidence_Available": True,
    "Damage_Description": "Cracked front bumper from a low-speed collision.",
}


def _payload(claim_id, **overrides):
    body = dict(VALID_PAYLOAD)
    body["Claim_ID"] = claim_id
    body.update(overrides)
    return body


@pytest.fixture()
def created_damage_ids():
    ids: list[str] = []
    yield ids
    if ids:
        db = SessionLocal()
        try:
            db.query(VehicleDamage).filter(VehicleDamage.Damage_ID.in_(ids)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------- 1/2/3: auth + role


def test_unauthenticated_damage_creation_returns_401(client, seed_data):
    response = client.post("/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]))
    assert response.status_code == 401


def test_customer_cannot_create_damage(client, customer1_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(customer1_token)
    )
    assert response.status_code == 403


def test_claims_officer_cannot_create_damage(client, officer_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(officer_token)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- 4/5: assignment


def test_unassigned_surveyor_damage_creation_rejected(client, surveyor_token, unassigned_claim):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(unassigned_claim),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


def test_wrong_surveyor_damage_creation_rejected(client, surveyor_token, other_surveyor_claim):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(other_surveyor_claim["claim_id"]),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- 6/7: valid creation + Vehicle_ID derivation


def test_assigned_surveyor_damage_creation_succeeds(client, surveyor_token, seed_data, created_damage_ids):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"]),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_damage_ids.append(body["Damage_ID"])

    assert body["Damage_ID"].startswith("DMG-")
    assert body["Claim_ID"] == seed_data["claim1"]
    assert body["Vehicle_ID"] == seed_data["vehicle1"]
    assert body["Vehicle_Damage_Mismatch_Indicator"] is False


def test_supplied_vehicle_id_cannot_override_claim_vehicle_id(
    client, surveyor_token, seed_data, created_damage_ids
):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Vehicle_ID="SOME-OTHER-VEHICLE"),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    created_damage_ids.append(body["Damage_ID"])
    assert body["Vehicle_ID"] == seed_data["vehicle1"]
    assert body["Vehicle_ID"] != "SOME-OTHER-VEHICLE"


def test_supplied_surveyor_id_is_ignored(client, surveyor_token, seed_data, other_surveyor_claim, created_damage_ids):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Surveyor_ID=other_surveyor_claim["employee_id"]),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 201, response.text
    created_damage_ids.append(response.json()["Damage_ID"])
    # No Surveyor_ID field exists on VehicleDamage at all - this simply
    # proves the extra field is silently ignored, not used to impersonate.
    db = SessionLocal()
    try:
        assert not hasattr(VehicleDamage, "Surveyor_ID")
    finally:
        db.close()


# ---------------------------------------------------------------- 8: multiple records


def test_multiple_damage_records_allowed_for_same_claim(client, surveyor_token, seed_data, created_damage_ids):
    r1 = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Damaged_Part="Bumper"),
        headers=auth_headers(surveyor_token),
    )
    r2 = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Damaged_Part="Headlight", Damage_Location="Left"),
        headers=auth_headers(surveyor_token),
    )
    assert r1.status_code == 201 and r2.status_code == 201
    created_damage_ids += [r1.json()["Damage_ID"], r2.json()["Damage_ID"]]
    assert r1.json()["Damage_ID"] != r2.json()["Damage_ID"]

    db = SessionLocal()
    try:
        count = db.query(VehicleDamage).filter(VehicleDamage.Claim_ID == seed_data["claim1"]).count()
        assert count >= 2
    finally:
        db.close()


# ---------------------------------------------------------------- validation


def test_invalid_damage_type_rejected(client, surveyor_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Damage_Type="Made Up Damage"),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


def test_negative_estimated_cost_rejected(client, surveyor_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Estimated_Damage_Cost="-1"),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


def test_blank_damage_description_rejected(client, surveyor_token, seed_data):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Damage_Description="   "),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422


def test_database_persists_estimated_cost_as_decimal(client, surveyor_token, seed_data, created_damage_ids):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json=_payload(seed_data["claim1"], Estimated_Damage_Cost="12345.67"),
        headers=auth_headers(surveyor_token),
    )
    damage_id = response.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    db = SessionLocal()
    try:
        row = db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).first()
        assert row.Estimated_Damage_Cost == Decimal("12345.67")
    finally:
        db.close()


# ---------------------------------------------------------------- PATCH (edit existing record)


def _update_payload(**overrides):
    body = dict(VALID_PAYLOAD)
    body.pop("Claim_ID", None)
    body.update(overrides)
    return body


def test_assigned_surveyor_can_update_their_own_damage_record(client, surveyor_token, seed_data, created_damage_ids):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    response = client.patch(
        f"/api/v1/surveyor/vehicle-damage/{damage_id}",
        json=_update_payload(Damaged_Part="Rear Bumper", Damage_Location="Rear", Estimated_Damage_Cost="22000.00"),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["Damage_ID"] == damage_id
    assert body["Damaged_Part"] == "Rear Bumper"
    assert body["Damage_Location"] == "Rear"
    assert Decimal(str(body["Estimated_Damage_Cost"])) == Decimal("22000.00")


def test_update_preserves_claim_id_and_vehicle_id_even_if_a_different_one_is_sent(
    client, surveyor_token, seed_data, created_damage_ids
):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    response = client.patch(
        f"/api/v1/surveyor/vehicle-damage/{damage_id}",
        json={**_update_payload(), "Claim_ID": "SOME-OTHER-CLAIM", "Vehicle_ID": "SOME-OTHER-VEHICLE"},
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["Claim_ID"] == seed_data["claim1"]
    assert body["Vehicle_ID"] == seed_data["vehicle1"]


def test_update_does_not_create_a_duplicate_record(client, surveyor_token, seed_data, created_damage_ids):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    client.patch(
        f"/api/v1/surveyor/vehicle-damage/{damage_id}",
        json=_update_payload(Damaged_Part="Updated Part"),
        headers=auth_headers(surveyor_token),
    )

    db = SessionLocal()
    try:
        count = db.query(VehicleDamage).filter(VehicleDamage.Claim_ID == seed_data["claim1"]).count()
        row = db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).first()
        assert count == 1
        assert row.Damaged_Part == "Updated Part"
    finally:
        db.close()


def test_update_persists_changed_estimated_cost_as_decimal(client, surveyor_token, seed_data, created_damage_ids):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    client.patch(
        f"/api/v1/surveyor/vehicle-damage/{damage_id}",
        json=_update_payload(Estimated_Damage_Cost="9999.50"),
        headers=auth_headers(surveyor_token),
    )

    db = SessionLocal()
    try:
        row = db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).first()
        assert row.Estimated_Damage_Cost == Decimal("9999.50")
    finally:
        db.close()


def test_update_rejects_an_invalid_damage_type(client, surveyor_token, seed_data, created_damage_ids):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    response = client.patch(
        f"/api/v1/surveyor/vehicle-damage/{damage_id}",
        json=_update_payload(Damage_Type="Made Up Damage"),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 422

    db = SessionLocal()
    try:
        row = db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).first()
        assert row.Damage_Type == VALID_PAYLOAD["Damage_Type"]
    finally:
        db.close()


def test_update_nonexistent_damage_id_returns_404(client, surveyor_token, seed_data):
    response = client.patch(
        "/api/v1/surveyor/vehicle-damage/DMG-DOES-NOT-EXIST",
        json=_update_payload(),
        headers=auth_headers(surveyor_token),
    )
    assert response.status_code == 404


def test_unauthenticated_update_returns_401(client, surveyor_token, seed_data, created_damage_ids):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    response = client.patch(f"/api/v1/surveyor/vehicle-damage/{damage_id}", json=_update_payload())
    assert response.status_code == 401


def test_customer_cannot_update_damage(client, customer1_token, surveyor_token, seed_data, created_damage_ids):
    created = client.post(
        "/api/v1/surveyor/vehicle-damage", json=_payload(seed_data["claim1"]), headers=auth_headers(surveyor_token)
    )
    damage_id = created.json()["Damage_ID"]
    created_damage_ids.append(damage_id)

    response = client.patch(
        f"/api/v1/surveyor/vehicle-damage/{damage_id}",
        json=_update_payload(),
        headers=auth_headers(customer1_token),
    )
    assert response.status_code == 403


def test_unassigned_surveyor_cannot_update_another_surveyors_damage_record(
    client, surveyor_token, seed_data, other_surveyor_claim
):
    """other_surveyor_claim belongs to a different surveyor (TEST-EMP-SURV2).
    A damage record created directly on it must be unreachable by
    surveyor1's PATCH - proving this is enforced on the backend, not just
    by hiding the Edit button in the UI."""
    db = SessionLocal()
    damage_id = "TEST-DMG-SURV2"
    try:
        db.add(
            VehicleDamage(
                Damage_ID=damage_id,
                Claim_ID=other_surveyor_claim["claim_id"],
                # _make_bare_claim always uses seed_data's own vehicle1 - the
                # only Vehicle_ID guaranteed to satisfy the FK here.
                Vehicle_ID=seed_data["vehicle1"],
                **DAMAGE_FIELDS,
                Vehicle_Damage_Mismatch_Indicator=False,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        response = client.patch(
            f"/api/v1/surveyor/vehicle-damage/{damage_id}",
            json=_update_payload(Damaged_Part="Should not be allowed"),
            headers=auth_headers(surveyor_token),
        )
        assert response.status_code == 403

        db = SessionLocal()
        try:
            row = db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).first()
            assert row.Damaged_Part == DAMAGE_FIELDS["Damaged_Part"]
        finally:
            db.close()
    finally:
        db = SessionLocal()
        db.query(VehicleDamage).filter(VehicleDamage.Damage_ID == damage_id).delete()
        db.commit()
        db.close()
