"""Tests for POST /api/v1/officer/claims/{claim_id}/decision (Step 5.8.9).

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py). claim_decision_audit is append-only: repeated
decisions on the same claim must accumulate rows, never overwrite or
delete previous ones.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from tests.conftest import _make_bare_claim, auth_headers


@pytest.fixture()
def fresh_claim(seed_data):
    """A claim with no prior decision audit history, isolated per test so
    "decision history is preserved" tests don't interfere with each
    other."""
    claim_id = f"TEST-CLM-DECISION-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    claim = _make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Fresh claim for decision tests.")
    claim.Claim_Amount = Decimal("50000.00")
    db.add(claim)
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


VALID_APPROVED = {
    "Final_Decision": "Approved",
    "Decision_Reason": "Documents and evidence are consistent with the claimed damage.",
    "Approved_Amount": "45000.00",
    "Officer_Comments": "Standard approval.",
}
VALID_REJECTED = {
    "Final_Decision": "Rejected",
    "Decision_Reason": "Evidence does not support the claimed accident circumstances.",
    "Approved_Amount": "0.00",
    "Officer_Comments": "Rejected after review.",
}
VALID_PARTIAL = {
    "Final_Decision": "Partially Approved",
    "Decision_Reason": "Only part of the claimed damage is covered under the policy.",
    "Approved_Amount": "20000.00",
    "Officer_Comments": "Partial approval - depreciation applied.",
}


def _decide(client, claim_id, body, token):
    return client.post(
        f"/api/v1/officer/claims/{claim_id}/decision", json=body, headers=auth_headers(token)
    )


# ---------------------------------------------------------------- 1/2/3: valid decisions


def test_officer_can_submit_valid_approved_decision(client, officer_token, fresh_claim):
    response = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["Final_Decision"] == "Approved"
    assert body["Claim_ID"] == fresh_claim


def test_officer_can_submit_valid_rejected_decision(client, officer_token, fresh_claim):
    response = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert response.status_code == 201, response.text
    assert response.json()["Final_Decision"] == "Rejected"


def test_officer_can_submit_valid_partially_approved_decision(client, officer_token, fresh_claim):
    response = _decide(client, fresh_claim, VALID_PARTIAL, officer_token)
    assert response.status_code == 201, response.text
    assert response.json()["Final_Decision"] == "Partially Approved"


# ---------------------------------------------------------------- 4/5/6: validation


def test_decision_reason_is_required(client, officer_token, fresh_claim):
    body = dict(VALID_APPROVED, Decision_Reason="   ")
    response = _decide(client, fresh_claim, body, officer_token)
    assert response.status_code == 422


def test_negative_approved_amount_rejected(client, officer_token, fresh_claim):
    body = dict(VALID_APPROVED, Approved_Amount="-1")
    response = _decide(client, fresh_claim, body, officer_token)
    assert response.status_code == 422


def test_invalid_decision_value_rejected(client, officer_token, fresh_claim):
    body = dict(VALID_APPROVED, Final_Decision="Escalated")
    response = _decide(client, fresh_claim, body, officer_token)
    assert response.status_code == 422


# ---------------------------------------------------------------- 7/8: cross-field rules


def test_rejected_claim_cannot_have_positive_approved_amount(client, officer_token, fresh_claim):
    body = dict(VALID_REJECTED, Approved_Amount="5000.00")
    response = _decide(client, fresh_claim, body, officer_token)
    assert response.status_code == 422


def test_approved_decision_requires_positive_approved_amount(client, officer_token, fresh_claim):
    body = dict(VALID_APPROVED, Approved_Amount="0.00")
    response = _decide(client, fresh_claim, body, officer_token)
    assert response.status_code == 422


def test_approved_amount_may_exceed_claim_amount(client, officer_token, fresh_claim):
    """The approved dataset itself has no such cap (252/654 real rows
    have Approved_Amount > Claim_Amount) - see
    CLAIMS_OFFICER_DECISION_WORKFLOW.md. No such rule is invented here."""
    body = dict(VALID_APPROVED, Approved_Amount="999999.00")
    response = _decide(client, fresh_claim, body, officer_token)
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------- 9/10/11: RBAC


def test_customer_cannot_submit_decision(client, customer1_token, fresh_claim):
    response = _decide(client, fresh_claim, VALID_APPROVED, customer1_token)
    assert response.status_code == 403


def test_surveyor_cannot_submit_decision(client, surveyor_token, fresh_claim):
    response = _decide(client, fresh_claim, VALID_APPROVED, surveyor_token)
    assert response.status_code == 403


def test_admin_cannot_submit_decision_no_employee_id(client, admin_token, fresh_claim):
    """Admin accounts have no Employee_ID in this project's data, and
    Claims_Officer_ID is a NOT NULL FK to authentication_users.Employee_ID
    - see api/v1/deps.py::require_claims_officer_employee_id."""
    response = _decide(client, fresh_claim, VALID_APPROVED, admin_token)
    assert response.status_code == 403


def test_unauthenticated_decision_returns_401(client, fresh_claim):
    response = client.post(f"/api/v1/officer/claims/{fresh_claim}/decision", json=VALID_APPROVED)
    assert response.status_code == 401


def test_nonexistent_claim_returns_404(client, officer_token):
    response = _decide(client, "TEST-CLM-DOES-NOT-EXIST", VALID_APPROVED, officer_token)
    assert response.status_code == 404


# ---------------------------------------------------------------- 12/13/14: persistence


def test_claim_fields_are_updated(client, officer_token, seed_data, fresh_claim):
    response = _decide(client, fresh_claim, VALID_PARTIAL, officer_token)
    assert response.status_code == 201

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert claim.Final_Decision == "Partially Approved"
        assert claim.Decision_Reason == VALID_PARTIAL["Decision_Reason"]
        assert claim.Approved_Amount == Decimal("20000.00")
        assert claim.Decision_Date is not None
    finally:
        db.close()


def test_audit_record_is_created_with_correct_officer_id(client, officer_token, seed_data, fresh_claim):
    response = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    audit_id = response.json()["Audit_ID"]

    db = SessionLocal()
    try:
        row = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Audit_ID == audit_id).first()
        assert row is not None
        assert row.Claim_ID == fresh_claim
        assert row.Claims_Officer_ID == seed_data["employee_officer"]
        assert row.Final_Decision == "Approved"
        assert row.Approved_Amount == Decimal("45000.00")
        assert row.Escalation_Status == "Not Escalated"
        assert row.Audit_Action == "Created"
    finally:
        db.close()


def test_no_genuine_ai_recommendation_uses_honest_placeholder(client, officer_token, fresh_claim):
    """fresh_claim has no prior claim_decision_audit row, so there is no
    genuine AI signal to carry forward."""
    response = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    body = response.json()
    assert body["AI_Recommendation"] == "Pending"
    assert Decimal(str(body["AI_Confidence_Score"])) == Decimal("0.0000")
    assert body["Human_Review_Required"] is True


# ---------------------------------------------------------------- 15/17: history preserved


def test_decision_history_is_preserved_across_repeated_submissions(client, officer_token, fresh_claim):
    first = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    second = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["Audit_ID"] != second.json()["Audit_ID"]

    db = SessionLocal()
    try:
        rows = (
            db.query(ClaimDecisionAudit)
            .filter(ClaimDecisionAudit.Claim_ID == fresh_claim)
            .all()
        )
        assert len(rows) == 2
        first_row = db.query(ClaimDecisionAudit).filter(
            ClaimDecisionAudit.Audit_ID == first.json()["Audit_ID"]
        ).first()
        assert first_row is not None
        assert first_row.Final_Decision == "Approved"

        claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert claim.Final_Decision == "Rejected"
    finally:
        db.close()


def test_second_decision_carries_forward_first_decisions_ai_recommendation_if_real(
    client, officer_token, fresh_claim, monkeypatch
):
    """If a prior audit row already has a genuine AI_Recommendation (from
    the real dataset's vocabulary), a later decision on the same claim
    should carry it forward as supporting information - not recompute or
    fabricate a new one."""
    db = SessionLocal()
    db.add(
        ClaimDecisionAudit(
            Audit_ID="TEST-AUD-PRIOR-0001",
            Claim_ID=fresh_claim,
            Claims_Officer_ID="TEST-EMP-OFF1",
            AI_Recommendation="Approve",
            AI_Confidence_Score=Decimal("0.8800"),
            Human_Review_Required=False,
            Final_Decision="Approved",
            Decision_Reason="Prior genuine AI-backed decision for this test.",
            Approved_Amount=Decimal("10000.00"),
            Decision_Date=__import__("datetime").date(2026, 1, 1),
            Escalation_Status="Not Escalated",
            Escalated_To=None,
            Officer_Comments="",
            Audit_Action="Created",
            Audit_Timestamp=__import__("datetime").datetime(2026, 1, 1),
        )
    )
    db.commit()
    db.close()

    response = _decide(client, fresh_claim, VALID_PARTIAL, officer_token)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["AI_Recommendation"] == "Approve"
    assert Decimal(str(body["AI_Confidence_Score"])) == Decimal("0.8800")


# ---------------------------------------------------------------- 16: rollback


def test_failed_commit_leaves_no_partial_decision_state(client, officer_token, seed_data, fresh_claim, monkeypatch):
    from app.crud import claim_decision_audit as crud_audit

    colliding_id = "AUD-ROLLBACK-TEST-0001"
    monkeypatch.setattr(crud_audit, "generate_audit_id", lambda db: colliding_id)

    db = SessionLocal()
    db.add(
        ClaimDecisionAudit(
            Audit_ID=colliding_id,
            Claim_ID=seed_data["claim1"],
            Claims_Officer_ID=seed_data["employee_officer"],
            AI_Recommendation="Pending",
            AI_Confidence_Score=Decimal("0.0000"),
            Human_Review_Required=True,
            Final_Decision="Approved",
            Decision_Reason="Pre-existing row to force a primary-key collision.",
            Approved_Amount=Decimal("1.00"),
            Decision_Date=__import__("datetime").date(2026, 1, 1),
            Escalation_Status="Not Escalated",
            Escalated_To=None,
            Officer_Comments="",
            Audit_Action="Created",
            Audit_Timestamp=__import__("datetime").datetime(2026, 1, 1),
        )
    )
    db.commit()
    db.close()

    original_final_decision = None
    db = SessionLocal()
    try:
        original_final_decision = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first().Final_Decision
    finally:
        db.close()

    try:
        response = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
        assert response.status_code == 500

        db = SessionLocal()
        try:
            claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
            assert claim.Final_Decision == original_final_decision
            count = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == fresh_claim).count()
            assert count == 0
        finally:
            db.close()
    finally:
        db = SessionLocal()
        db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Audit_ID == colliding_id).delete()
        db.commit()
        db.close()
