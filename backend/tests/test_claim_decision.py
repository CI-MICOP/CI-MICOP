"""Tests for POST /api/v1/officer/claims/{claim_id}/decision (Step 5.8.9).

Per project rules these run against the real PostgreSQL database (see
tests/conftest.py). A claim's first final decision is permanent: once
Final_Decision moves off "Pending", every later submission for that same
claim - sequential or concurrent - is rejected with 409 and leaves the
claim and its single claim_decision_audit row unchanged.
"""

from concurrent.futures import ThreadPoolExecutor
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


def _claim_status(db, claim_id):
    return db.query(Claim).filter(Claim.Claim_ID == claim_id).first().Claim_Status


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


def test_approved_decision_sets_claim_status_to_completed(client, officer_token, fresh_claim):
    """A fresh claim starts "Under Review" - an Approved decision must
    move it to "Completed" so the persisted status agrees with
    Final_Decision (see services/claim_decision.py)."""
    db = SessionLocal()
    try:
        assert _claim_status(db, fresh_claim) == "Under Review"
    finally:
        db.close()

    response = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    assert response.status_code == 201, response.text

    db = SessionLocal()
    try:
        assert _claim_status(db, fresh_claim) == "Completed"
    finally:
        db.close()


def test_rejected_decision_also_sets_claim_status_to_completed(client, officer_token, fresh_claim):
    """A rejected claim is just as finally decided as an approved one - it
    must leave "Under Review" too, not be left looking like it is still
    awaiting a decision (the bug this task fixes)."""
    response = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert response.status_code == 201, response.text

    db = SessionLocal()
    try:
        assert _claim_status(db, fresh_claim) == "Completed"
    finally:
        db.close()


def test_partially_approved_decision_also_sets_claim_status_to_completed(client, officer_token, fresh_claim):
    response = _decide(client, fresh_claim, VALID_PARTIAL, officer_token)
    assert response.status_code == 201, response.text

    db = SessionLocal()
    try:
        assert _claim_status(db, fresh_claim) == "Completed"
    finally:
        db.close()


def test_claim_without_a_final_decision_remains_under_review(client, officer_token, fresh_claim):
    """A claim that has not yet been decided must never be shown as
    finalized - only an actual decision submission changes Claim_Status."""
    db = SessionLocal()
    try:
        assert _claim_status(db, fresh_claim) == "Under Review"
        claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert claim.Final_Decision in (None, "Pending")
    finally:
        db.close()


def test_a_second_decision_after_approval_is_rejected_and_the_first_decision_is_unchanged(
    client, officer_token, fresh_claim
):
    """Once finalized, a claim's decision is permanent - no re-decision or
    override path exists. The second attempt must not alter anything the
    first one already persisted."""
    first = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    assert first.status_code == 201

    second = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert second.status_code == 409
    assert "already been finalized" in second.json()["detail"]

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert claim.Final_Decision == "Approved"
        assert claim.Claim_Status == "Completed"
        assert claim.Approved_Amount == Decimal("45000.00")
        audit_count = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == fresh_claim).count()
        assert audit_count == 1
    finally:
        db.close()


def test_a_second_decision_after_rejection_is_also_rejected(client, officer_token, fresh_claim):
    first = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert first.status_code == 201

    second = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    assert second.status_code == 409

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert claim.Final_Decision == "Rejected"
        assert claim.Claim_Status == "Completed"
    finally:
        db.close()


def test_a_third_decision_attempt_is_rejected_the_same_way(client, officer_token, fresh_claim):
    """The lock holds for every attempt after the first, not just the
    second."""
    assert _decide(client, fresh_claim, VALID_APPROVED, officer_token).status_code == 201
    assert _decide(client, fresh_claim, VALID_REJECTED, officer_token).status_code == 409
    assert _decide(client, fresh_claim, VALID_PARTIAL, officer_token).status_code == 409

    db = SessionLocal()
    try:
        audit_count = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == fresh_claim).count()
        assert audit_count == 1
    finally:
        db.close()


def test_two_concurrent_decisions_on_the_same_claim_cannot_both_finalize_it(client, officer_token, fresh_claim):
    """crud/claim.py::get_for_update row-locks the claim for the duration
    of each decision's transaction, so of two requests racing for the same
    still-Pending claim, exactly one succeeds and the other is rejected -
    never both, regardless of request order."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_decide, client, fresh_claim, VALID_APPROVED, officer_token)
        future_b = pool.submit(_decide, client, fresh_claim, VALID_REJECTED, officer_token)
        status_codes = sorted([future_a.result().status_code, future_b.result().status_code])

    assert status_codes == [201, 409]

    db = SessionLocal()
    try:
        audit_count = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == fresh_claim).count()
        assert audit_count == 1
        claim = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert claim.Final_Decision in ("Approved", "Rejected")
    finally:
        db.close()


def test_claims_list_endpoint_reflects_the_updated_status_after_approval(client, officer_token, fresh_claim):
    """Bullet 4/5.4 of the task: subsequent API responses (not just the
    decision endpoint's own response) must return the updated status and
    final decision - and the queue/all-claims split both read from this
    same endpoint."""
    response = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
    assert response.status_code == 201

    listing = client.get("/api/v1/officer/claims", params={"limit": 200}, headers=auth_headers(officer_token))
    assert listing.status_code == 200
    by_id = {c["Claim_ID"]: c for c in listing.json()}
    assert by_id[fresh_claim]["Claim_Status"] == "Completed"
    assert by_id[fresh_claim]["Final_Decision"] == "Approved"

    # The same claim must not also still be returned by the Under Review
    # filter the Queue page actually uses - no duplicates across the two
    # sections.
    under_review = client.get(
        "/api/v1/officer/claims",
        params={"limit": 200, "claim_status": "Under Review"},
        headers=auth_headers(officer_token),
    )
    assert fresh_claim not in {c["Claim_ID"] for c in under_review.json()}


def test_claims_list_endpoint_reflects_the_updated_status_after_rejection(client, officer_token, fresh_claim):
    """Same as the approval case above, but for a rejection - a rejected
    claim must leave the Under Review queue and appear under the
    Completed filter too, the exact bug this task fixes."""
    response = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert response.status_code == 201

    completed = client.get(
        "/api/v1/officer/claims",
        params={"limit": 200, "claim_status": "Completed"},
        headers=auth_headers(officer_token),
    )
    by_id = {c["Claim_ID"]: c for c in completed.json()}
    assert by_id[fresh_claim]["Claim_Status"] == "Completed"
    assert by_id[fresh_claim]["Final_Decision"] == "Rejected"

    under_review = client.get(
        "/api/v1/officer/claims",
        params={"limit": 200, "claim_status": "Under Review"},
        headers=auth_headers(officer_token),
    )
    assert fresh_claim not in {c["Claim_ID"] for c in under_review.json()}


def test_customer_sees_the_finalized_status_after_a_rejection(client, officer_token, customer1_token, fresh_claim):
    """The Customer Portal's Claim Details page reads this same endpoint -
    it must never show "Under Review" once the officer has finalized the
    claim, on this fetch or any later one (refresh/re-login re-fetch the
    same way, so there is nothing else to keep in sync)."""
    response = _decide(client, fresh_claim, VALID_REJECTED, officer_token)
    assert response.status_code == 201

    seen = client.get(f"/api/v1/claims/{fresh_claim}", headers=auth_headers(customer1_token))
    assert seen.status_code == 200
    body = seen.json()
    assert body["Claim_Status"] == "Completed"
    assert body["Final_Decision"] == "Rejected"
    assert body["Decision_Reason"] == VALID_REJECTED["Decision_Reason"]
    assert body["Decision_Date"] is not None


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


def test_decision_audit_history_accumulates_independently_per_claim(client, officer_token, seed_data, fresh_claim):
    """Each claim now gets exactly one decision (the lock), so "history is
    preserved" means deciding one claim must not touch another claim's own
    audit trail or claim record."""
    other_claim_id = f"TEST-CLM-DECISION-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    other_claim = _make_bare_claim(
        other_claim_id, f"TEST-CLMNUM-{other_claim_id[-8:]}", seed_data, "A second, unrelated claim."
    )
    db.add(other_claim)
    db.commit()
    db.close()

    try:
        first = _decide(client, fresh_claim, VALID_APPROVED, officer_token)
        second = _decide(client, other_claim_id, VALID_REJECTED, officer_token)
        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["Audit_ID"] != second.json()["Audit_ID"]

        db = SessionLocal()
        try:
            assert db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == fresh_claim).count() == 1
            assert db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == other_claim_id).count() == 1
            assert db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first().Final_Decision == "Approved"
            assert db.query(Claim).filter(Claim.Claim_ID == other_claim_id).first().Final_Decision == "Rejected"
        finally:
            db.close()
    finally:
        db = SessionLocal()
        db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == other_claim_id).delete()
        db.query(Claim).filter(Claim.Claim_ID == other_claim_id).delete()
        db.commit()
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
