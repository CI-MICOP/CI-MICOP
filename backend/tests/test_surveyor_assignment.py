"""Tests for the Step 5.8.8 Surveyor Assignment mechanism:
GET /api/v1/officer/surveyors and
POST /api/v1/officer/claims/{claim_id}/assign-surveyor.

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py). Assignment is represented by creating the claim's
first surveyor_inspections row - the same "assigned" definition already
established in Steps 5.8.5/5.8.6/5.8.7 (crud_claim.surveyor_is_assigned).
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.claim import Claim
from app.db_models.surveyor_inspection import SurveyorInspection
from tests.conftest import TEST_PASSWORD, _make_bare_claim, auth_headers


@pytest.fixture()
def fresh_claim(seed_data):
    """A brand-new claim with zero surveyor_inspections rows - the
    "brand-new customer claim" scenario this step's assignment mechanism
    must support. Function-scoped (unlike the shared unassigned_claim
    fixture) so each assignment test gets its own never-assigned claim."""
    claim_id = f"TEST-CLM-ASSIGN-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    db.add(_make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Fresh claim for assignment tests."))
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(SurveyorInspection).filter(SurveyorInspection.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def inactive_surveyor():
    """Synthetic account with Account_Status != "Active", used only to
    exercise the assignment endpoint's active-account check. The real
    dataset has no inactive accounts (Account_Status is "Active" for all
    660 real authentication_users rows) - this value is not claimed to
    be realistic production data, only a defensive-test fixture."""
    db = SessionLocal()
    employee_id = "TEST-EMP-SURV-INACTIVE"
    user_id = "TEST-USER-SURV-INACTIVE"
    db.add(
        AuthenticationUser(
            User_ID=user_id,
            Username="test_surveyor_inactive",
            Password_Hash=hash_password(TEST_PASSWORD),
            Role="Surveyor",
            Customer_ID=None,
            Employee_ID=employee_id,
            Email="test_surveyor_inactive@example.com",
            Phone="9990000007",
            Account_Status="Inactive",
            Login_Status="Logged Out",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=2,
            Insurer_Code=None,
        )
    )
    db.commit()
    db.close()

    yield employee_id

    db = SessionLocal()
    db.query(AuthenticationUser).filter(AuthenticationUser.User_ID == user_id).delete()
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def customer_with_employee_id():
    """Synthetic: a Customer-role account that (unrealistically) has an
    Employee_ID populated. Real Customer accounts never have an
    Employee_ID (see db_models/authentication_user.py) - this exists
    only to exercise the assignment endpoint's Role check in depth as
    defense-in-depth, not to claim this combination occurs in
    production."""
    db = SessionLocal()
    employee_id = "TEST-EMP-CUST-FAKE"
    user_id = "TEST-USER-CUST-FAKE"
    db.add(
        AuthenticationUser(
            User_ID=user_id,
            Username="test_customer_with_employee_id",
            Password_Hash=hash_password(TEST_PASSWORD),
            Role="Customer",
            Customer_ID=None,
            Employee_ID=employee_id,
            Email="test_customer_with_employee_id@example.com",
            Phone="9990000008",
            Account_Status="Active",
            Login_Status="Active",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=1,
            Insurer_Code=None,
        )
    )
    db.commit()
    db.close()

    yield employee_id

    db = SessionLocal()
    db.query(AuthenticationUser).filter(AuthenticationUser.User_ID == user_id).delete()
    db.commit()
    db.close()


def _assign(client, claim_id, employee_id, token=None, **extra_body):
    headers = auth_headers(token) if token else {}
    body = {"surveyor_employee_id": employee_id, **extra_body}
    return client.post(f"/api/v1/officer/claims/{claim_id}/assign-surveyor", json=body, headers=headers)


# ---------------------------------------------------------------- GET /officer/surveyors: 1-6


def test_unauthenticated_list_surveyors_returns_401(client):
    response = client.get("/api/v1/officer/surveyors")
    assert response.status_code == 401


def test_customer_cannot_list_surveyors(client, customer1_token):
    response = client.get("/api/v1/officer/surveyors", headers=auth_headers(customer1_token))
    assert response.status_code == 403


def test_surveyor_cannot_list_surveyors(client, surveyor_token):
    response = client.get("/api/v1/officer/surveyors", headers=auth_headers(surveyor_token))
    assert response.status_code == 403


def test_officer_can_list_surveyors(client, officer_token, seed_data):
    response = client.get("/api/v1/officer/surveyors", headers=auth_headers(officer_token))
    assert response.status_code == 200
    ids = [s["Employee_ID"] for s in response.json()]
    assert seed_data["employee_surveyor"] in ids


def test_admin_can_list_surveyors(client, admin_token):
    response = client.get("/api/v1/officer/surveyors", headers=auth_headers(admin_token))
    assert response.status_code == 200


def test_only_active_surveyors_are_returned(client, officer_token, seed_data, inactive_surveyor):
    response = client.get("/api/v1/officer/surveyors", headers=auth_headers(officer_token))
    ids = [s["Employee_ID"] for s in response.json()]
    assert seed_data["employee_surveyor"] in ids
    assert inactive_surveyor not in ids
    assert seed_data["employee_officer"] not in ids
    for row in response.json():
        assert row["Account_Status"] == "Active"
        assert "Password_Hash" not in row


# ---------------------------------------------------------------- assignment RBAC: 7/8/9/10


def test_customer_cannot_assign_surveyor(client, customer1_token, seed_data, fresh_claim):
    response = _assign(client, fresh_claim, seed_data["employee_surveyor"], customer1_token)
    assert response.status_code == 403


def test_surveyor_cannot_assign_surveyor(client, surveyor_token, seed_data, fresh_claim):
    response = _assign(client, fresh_claim, seed_data["employee_surveyor"], surveyor_token)
    assert response.status_code == 403


def test_officer_can_assign_surveyor(client, officer_token, seed_data, fresh_claim):
    response = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["Claim_ID"] == fresh_claim
    assert body["Surveyor_ID"] == seed_data["employee_surveyor"]
    assert body["Inspection_Status"] == "Assigned"


def test_admin_can_assign_surveyor(client, admin_token, seed_data, fresh_claim):
    response = _assign(client, fresh_claim, seed_data["employee_surveyor"], admin_token)
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------- 11/12: not found


def test_assign_to_nonexistent_claim_returns_404(client, officer_token, seed_data):
    response = _assign(client, "TEST-CLM-DOES-NOT-EXIST", seed_data["employee_surveyor"], officer_token)
    assert response.status_code == 404


def test_assign_nonexistent_surveyor_returns_404(client, officer_token, fresh_claim):
    response = _assign(client, fresh_claim, "TEST-EMP-DOES-NOT-EXIST", officer_token)
    assert response.status_code == 404


# ---------------------------------------------------------------- 13/14/15: role/status rejection


def test_customer_role_supplied_as_surveyor_rejected(
    client, officer_token, fresh_claim, customer_with_employee_id
):
    response = _assign(client, fresh_claim, customer_with_employee_id, officer_token)
    assert response.status_code == 422


def test_claims_officer_supplied_as_surveyor_rejected(client, officer_token, seed_data, fresh_claim):
    response = _assign(client, fresh_claim, seed_data["employee_officer"], officer_token)
    assert response.status_code == 422


def test_inactive_surveyor_rejected(client, officer_token, fresh_claim, inactive_surveyor):
    response = _assign(client, fresh_claim, inactive_surveyor, officer_token)
    assert response.status_code == 422


# ---------------------------------------------------------------- 16: duplicate/reassignment -> 409


def test_duplicate_assignment_rejected_with_conflict(client, officer_token, seed_data, fresh_claim):
    first = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    assert first.status_code == 201

    second = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    assert second.status_code == 409


def test_reassignment_to_different_surveyor_rejected_with_conflict(
    client, officer_token, seed_data, fresh_claim, other_surveyor_claim
):
    first = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    assert first.status_code == 201

    second = _assign(client, fresh_claim, other_surveyor_claim["employee_id"], officer_token)
    assert second.status_code == 409


# ---------------------------------------------------------------- 17: server remains authoritative


def test_extra_body_fields_cannot_redirect_assignment(client, officer_token, seed_data, fresh_claim):
    response = _assign(
        client,
        fresh_claim,
        seed_data["employee_surveyor"],
        officer_token,
        Claim_ID="TEST-CLM-SOME-OTHER-CLAIM",
        Inspection_ID="INSP-CLIENT-SUPPLIED",
        Inspection_Status="Completed",
        Survey_Report_Submitted=True,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["Claim_ID"] == fresh_claim
    assert body["Inspection_Status"] == "Assigned"
    assert body["Survey_Report_Submitted"] is False
    assert not body["Inspection_ID"].startswith("INSP-CLIENT-SUPPLIED")


# ---------------------------------------------------------------- 18/21: persistence + no fabricated findings


def test_assignment_persists_with_no_fabricated_findings(client, officer_token, seed_data, fresh_claim):
    response = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    inspection_id = response.json()["Inspection_ID"]

    db = SessionLocal()
    try:
        row = db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == inspection_id).first()
        assert row.Claim_ID == fresh_claim
        assert row.Surveyor_ID == seed_data["employee_surveyor"]
        assert row.Inspection_Status == "Assigned"
        assert row.Vehicle_Condition == "Pending"
        assert row.Damage_Observed == "Pending"
        assert row.Damage_Severity == "Pending"
        assert row.Repair_Recommendation == "Pending"
        assert row.Parts_Required == 0
        assert row.Surveyor_Comments == ""
        assert row.Survey_Report_Submitted is False
        assert row.Surveyor_Confidence_Score == Decimal("0.0000")
    finally:
        db.close()


# ---------------------------------------------------------------- 19/20: downstream surveyor access


def test_assigned_surveyor_can_access_claim_after_assignment(client, officer_token, surveyor_token, seed_data, fresh_claim):
    assign_response = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    assert assign_response.status_code == 201

    response = client.get(f"/api/v1/surveyor/claims/{fresh_claim}", headers=auth_headers(surveyor_token))
    assert response.status_code == 200


def test_different_surveyor_still_cannot_access_claim_after_assignment(
    client, officer_token, seed_data, fresh_claim, other_surveyor_claim
):
    assign_response = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
    assert assign_response.status_code == 201

    other_token = _login_other_surveyor(client)
    response = client.get(f"/api/v1/surveyor/claims/{fresh_claim}", headers=auth_headers(other_token))
    assert response.status_code == 403


def _login_other_surveyor(client):
    response = client.post(
        "/api/v1/auth/login", data={"username": "test_surveyor2", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


# ---------------------------------------------------------------- 22: rollback behavior


def test_failed_commit_leaves_no_partial_assignment(client, officer_token, seed_data, fresh_claim, monkeypatch):
    from app.crud import surveyor_inspection as crud_inspection

    original_generate = crud_inspection.generate_inspection_id
    failing_id = "INSP-ROLLBACK-TEST-0001"
    monkeypatch.setattr(crud_inspection, "generate_inspection_id", lambda db: failing_id)

    # The pre-existing colliding row is deliberately placed on a
    # *different* claim (seed_data's claim1, already assigned) so
    # fresh_claim itself still has zero inspections and passes the
    # duplicate-active-assignment check - the failure this test forces
    # is specifically the ID-collision/commit path, not that check.
    db = SessionLocal()
    db.add(
        SurveyorInspection(
            Inspection_ID=failing_id,
            Claim_ID=seed_data["claim1"],
            Surveyor_ID=seed_data["employee_surveyor"],
            Inspection_Date=date(2026, 1, 1),
            Inspection_Location="Pre-existing row to force a primary-key collision.",
            Vehicle_Condition="Pending",
            Damage_Observed="Pending",
            Damage_Severity="Pending",
            Parts_Required=0,
            Repair_Recommendation="Pending",
            Surveyor_Comments="",
            Inspection_Status="Assigned",
            Survey_Report_Submitted=False,
            Surveyor_Confidence_Score=Decimal("0.0000"),
        )
    )
    db.commit()
    db.close()

    try:
        response = _assign(client, fresh_claim, seed_data["employee_surveyor"], officer_token)
        assert response.status_code == 500

        db = SessionLocal()
        try:
            count = db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == failing_id).count()
            assert count == 1
        finally:
            db.close()
    finally:
        monkeypatch.setattr(crud_inspection, "generate_inspection_id", original_generate)
        db = SessionLocal()
        db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == failing_id).delete()
        db.commit()
        db.close()
