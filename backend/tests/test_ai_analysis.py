"""Tests for GET /api/v1/officer/claims/{claim_id}/ai-analysis (Step
5.8.10). Per project rules these run against the real PostgreSQL
database (see tests/conftest.py). This endpoint is strictly read-only -
several tests assert it never touches Claim.Final_Decision or
claim_decision_audit.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.cross_document_consistency import CrossDocumentConsistency
from app.db_models.fraud_risk_analysis import FraudRiskAnalysis
from app.db_models.repair_estimate import RepairEstimate
from tests.conftest import _make_bare_claim, auth_headers


@pytest.fixture()
def fresh_claim(seed_data):
    """A claim with no fraud/consistency/repair-estimate rows and a
    Claim_ID that is guaranteed not to appear in the Step 5.4 risk-fusion
    export (which only ever uses CLM-000001..CLM-000654)."""
    claim_id = f"TEST-CLM-AI-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    db.add(_make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Fresh claim for AI analysis tests."))
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


@pytest.fixture()
def risk_fusion_claim(seed_data):
    """A claim whose Claim_ID exactly matches a real Step 5.4 risk-fusion
    representative example (CLM-000007, high_risk_low_confidence.json) -
    lets us exercise the "available=True, full signal breakdown" path
    deterministically without depending on dev-only seed data."""
    claim_id = "CLM-000007"
    db = SessionLocal()
    db.add(_make_bare_claim(claim_id, "TEST-CLMNUM-000007", seed_data, "Matches a real Step 5.4 example claim_id."))
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


@pytest.fixture()
def claim_with_analysis_rows(seed_data):
    """A claim with real (non-placeholder) fraud/consistency/repair-
    estimate rows, to test the "available=True" path for each of the
    three DB-backed sub-analyses."""
    claim_id = f"TEST-CLM-ANALYZED-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    db.add(_make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Claim with real analysis rows."))
    db.add(
        FraudRiskAnalysis(
            Risk_ID=f"TEST-RISK-{claim_id[-8:]}",
            Claim_ID=claim_id,
            Duplicate_Claim_Indicator=False,
            Previous_Similar_Claim=False,
            Suspicious_Garage_Indicator=True,
            Claim_Immediately_After_Policy_Indicator=False,
            Excessive_Claim_Amount_Indicator=False,
            Document_Mismatch_Indicator=False,
            Vehicle_Damage_Mismatch_Indicator=False,
            Accident_Details_Mismatch_Indicator=False,
            Evidence_Reuse_Indicator=False,
            Fraud_Risk_Score=Decimal("45.00"),
            Anomaly_Score=Decimal("0.6000"),
            Overall_Risk_Score=Decimal("45.00"),
            Risk_Category="Medium",
            Fraud_Label=0,
        )
    )
    db.add(
        CrossDocumentConsistency(
            Consistency_ID=f"TEST-CON-{claim_id[-8:]}",
            Claim_ID=claim_id,
            Customer_Statement_Match="Match",
            FIR_Match="Match",
            Surveyor_Report_Match="Mismatch",
            Repair_Estimate_Match="Match",
            Accident_Date_Match="Match",
            Accident_Location_Match="Match",
            Vehicle_Details_Match="Match",
            Damage_Description_Match="Match",
            Claim_Amount_Match="Match",
            Document_Consistency_Score=Decimal("0.7500"),
            Document_Mismatch_Indicator=True,
            Accident_Details_Mismatch_Indicator=False,
            Vehicle_Damage_Mismatch_Indicator=False,
            Overall_Consistency_Status="Partial",
        )
    )
    db.add(
        RepairEstimate(
            Estimate_ID=f"TEST-EST-{claim_id[-8:]}",
            Claim_ID=claim_id,
            Vehicle_ID=seed_data["vehicle1"],
            Garage_ID="GAR-TEST",
            Estimate_Date=date(2026, 1, 1),
            Repair_Estimate=Decimal("10000.00"),
            Repair_Cost=Decimal("10500.00"),
            Parts_Cost=Decimal("5000.00"),
            Labour_Cost=Decimal("4000.00"),
            Painting_Cost=Decimal("1500.00"),
            Replacement_Parts_Count=1,
            Repaired_Parts_Count=0,
            Estimated_Repair_Days=5,
            Actual_Repair_Days=0,
            Excessive_Claim_Amount_Indicator=True,
            Estimate_Anomaly_Score=Decimal("0.7200"),
        )
    )
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == claim_id).delete()
    db.query(CrossDocumentConsistency).filter(CrossDocumentConsistency.Claim_ID == claim_id).delete()
    db.query(FraudRiskAnalysis).filter(FraudRiskAnalysis.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


def _get_analysis(client, claim_id, token):
    return client.get(f"/api/v1/officer/claims/{claim_id}/ai-analysis", headers=auth_headers(token))


# ---------------------------------------------------------------- 1/2/3/4: RBAC


def test_officer_can_access_ai_analysis(client, officer_token, fresh_claim):
    response = _get_analysis(client, fresh_claim, officer_token)
    assert response.status_code == 200, response.text


def test_admin_can_access_ai_analysis(client, admin_token, fresh_claim):
    response = _get_analysis(client, fresh_claim, admin_token)
    assert response.status_code == 200, response.text


def test_customer_cannot_access_ai_analysis(client, customer1_token, fresh_claim):
    response = _get_analysis(client, fresh_claim, customer1_token)
    assert response.status_code == 403


def test_surveyor_cannot_access_ai_analysis(client, surveyor_token, fresh_claim):
    response = _get_analysis(client, fresh_claim, surveyor_token)
    assert response.status_code == 403


def test_unauthenticated_ai_analysis_returns_401(client, fresh_claim):
    response = client.get(f"/api/v1/officer/claims/{fresh_claim}/ai-analysis")
    assert response.status_code == 401


# ---------------------------------------------------------------- 5: not found


def test_unknown_claim_returns_404(client, officer_token):
    response = _get_analysis(client, "TEST-CLM-DOES-NOT-EXIST", officer_token)
    assert response.status_code == 404


# ---------------------------------------------------------------- 6: valid existing result returned correctly


def test_valid_risk_fusion_result_returned_correctly(client, officer_token, risk_fusion_claim):
    response = _get_analysis(client, risk_fusion_claim, officer_token)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert body["overall_risk"] == "HIGH"
    assert body["confidence_band"] == "LOW_CONFIDENCE"
    assert body["human_review_required"] is True
    assert len(body["signals"]) == 7
    assert "DOCUMENT_INCONSISTENCY" in body["reason_codes"]
    assert len(body["explanation"]) >= 1


def test_db_backed_sub_analyses_returned_correctly(client, officer_token, claim_with_analysis_rows):
    response = _get_analysis(client, claim_with_analysis_rows, officer_token)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["fraud_analysis"]["available"] is True
    assert body["fraud_analysis"]["risk_category"] == "Medium"
    assert "SUSPICIOUS_GARAGE_INDICATOR" in body["fraud_analysis"]["reason_codes"]

    assert body["consistency_analysis"]["available"] is True
    assert body["consistency_analysis"]["overall_status"] == "Partial"
    assert "Surveyor_Report_Match: Mismatch" in body["consistency_analysis"]["contradictions"]

    assert body["repair_estimate_analysis"]["available"] is True
    assert body["repair_estimate_analysis"]["anomaly_detected"] is True
    assert Decimal(str(body["repair_estimate_analysis"]["anomaly_score"])) == Decimal("0.7200")
    assert "EXCESSIVE_CLAIM_AMOUNT_INDICATOR" in body["repair_estimate_analysis"]["reason_codes"]


# ---------------------------------------------------------------- 7/8: missing result represented honestly, no fake values


def test_missing_ai_result_represented_honestly(client, officer_token, fresh_claim):
    response = _get_analysis(client, fresh_claim, officer_token)
    body = response.json()

    assert body["available"] is False
    assert body["overall_risk"] is None
    assert body["risk_score"] is None
    assert body["confidence_score"] is None
    assert body["signals"] == []

    assert body["fraud_analysis"]["available"] is False
    assert body["fraud_analysis"]["message"]
    assert body["consistency_analysis"]["available"] is False
    assert body["consistency_analysis"]["message"]
    assert body["repair_estimate_analysis"]["available"] is False
    assert body["repair_estimate_analysis"]["message"]

    assert any("outside the Step 5.4" in msg for msg in body["limitations"])


def test_unanalyzed_repair_estimate_placeholder_is_not_presented_as_available(
    client, surveyor_token, officer_token, seed_data, fresh_claim
):
    """A repair estimate created through the live surveyor endpoint always
    writes the honest Step 5.8.7 placeholder (False/0.0000) - this must
    never be reported as a genuine analyzed anomaly score."""
    # fresh_claim has no surveyor assignment, so create the estimate
    # directly against seed_data's already-assigned claim1 instead.
    create_response = client.post(
        "/api/v1/surveyor/repair-estimates",
        json={
            "Claim_ID": seed_data["claim1"],
            "Garage_ID": "GAR-0001",
            "Estimate_Date": "2026-09-10",
            "Repair_Estimate": "10000.00",
            "Repair_Cost": "10000.00",
            "Parts_Cost": "5000.00",
            "Labour_Cost": "4000.00",
            "Painting_Cost": "1000.00",
            "Replacement_Parts_Count": 1,
            "Repaired_Parts_Count": 0,
            "Estimated_Repair_Days": 5,
        },
        headers=auth_headers(surveyor_token),
    )
    assert create_response.status_code == 201, create_response.text
    estimate_id = create_response.json()["Estimate_ID"]

    try:
        response = _get_analysis(client, seed_data["claim1"], officer_token)
        body = response.json()
        assert body["repair_estimate_analysis"]["available"] is False
        assert "not been analyzed" in body["repair_estimate_analysis"]["message"]
    finally:
        db = SessionLocal()
        db.query(RepairEstimate).filter(RepairEstimate.Estimate_ID == estimate_id).delete()
        db.commit()
        db.close()


# ---------------------------------------------------------------- 9: does not modify claim decision


def test_ai_analysis_endpoint_does_not_modify_claim_decision(client, officer_token, fresh_claim):
    db = SessionLocal()
    try:
        before = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        final_decision_before = before.Final_Decision
        decision_reason_before = before.Decision_Reason
    finally:
        db.close()

    response = _get_analysis(client, fresh_claim, officer_token)
    assert response.status_code == 200

    db = SessionLocal()
    try:
        after = db.query(Claim).filter(Claim.Claim_ID == fresh_claim).first()
        assert after.Final_Decision == final_decision_before
        assert after.Decision_Reason == decision_reason_before
        audit_count = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == fresh_claim).count()
        assert audit_count == 0
    finally:
        db.close()
