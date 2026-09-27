"""Tests for POST /api/v1/officer/claims/{claim_id}/ai-analysis/run
(Step 5.8.11). Per project rules these run against the real PostgreSQL
database (see tests/conftest.py). This endpoint is analyze-only - several
tests assert it never touches Claim.Final_Decision or Approved_Amount and
never persists anything.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.document import Document
from app.db_models.repair_estimate import RepairEstimate
from tests.conftest import _make_bare_claim, auth_headers


@pytest.fixture()
def fresh_claim(seed_data):
    """A brand-new claim: no documents, damage, evidence, repair
    estimate, or inspection - the "insufficient evidence" scenario."""
    claim_id = f"TEST-CLM-PIPE-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    db.add(_make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Fresh claim for AI pipeline tests."))
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


@pytest.fixture()
def claim_with_repair_estimate(seed_data):
    """A claim with a genuine repair estimate, so repair_estimate_anomaly
    becomes available."""
    claim_id = f"TEST-CLM-PIPE-EST-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    claim = _make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Claim with a repair estimate.")
    claim.Claim_Amount = Decimal("50000.00")
    db.add(claim)
    db.add(
        RepairEstimate(
            Estimate_ID=f"TEST-EST-PIPE-{claim_id[-8:]}",
            Claim_ID=claim_id,
            Vehicle_ID=seed_data["vehicle1"],
            Garage_ID="GAR-TEST",
            Estimate_Date=date(2026, 1, 1),
            Repair_Estimate=Decimal("48000.00"),
            Repair_Cost=Decimal("48000.00"),
            Parts_Cost=Decimal("20000.00"),
            Labour_Cost=Decimal("20000.00"),
            Painting_Cost=Decimal("8000.00"),
            Replacement_Parts_Count=1,
            Repaired_Parts_Count=0,
            Estimated_Repair_Days=5,
            Actual_Repair_Days=0,
            Excessive_Claim_Amount_Indicator=False,
            Estimate_Anomaly_Score=Decimal("0.0000"),
        )
    )
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


def _make_document(claim_id: str, suffix: str, document_type: str) -> Document:
    return Document(
        Document_ID=f"TEST-DOC-PIPE-{suffix}",
        Claim_ID=claim_id,
        Document_Type=document_type,
        Document_Name=f"{document_type}.pdf",
        Document_Submitted_Date=date(2026, 1, 1),
        Document_Status="Submitted",
        OCR_Confidence_Score=Decimal("0.0000"),
        Extracted_Text="",
        Document_Completeness=Decimal("0.0000"),
        Document_Mismatch_Indicator=False,
        Verification_Status="Pending",
    )


@pytest.fixture()
def claim_with_documents(seed_data):
    """A claim (Claim_Type "Own Damage", per _make_bare_claim) with 4 of
    its 5 required document types present (Accident Photos missing) - so
    document_completeness becomes available at ratio 4/5, alongside the
    repair-estimate signal, giving 3/7 available signals."""
    claim_id = f"TEST-CLM-PIPE-DOC-{uuid4().hex[:8].upper()}"
    db = SessionLocal()
    claim = _make_bare_claim(claim_id, f"TEST-CLMNUM-{claim_id[-8:]}", seed_data, "Claim with documents.")
    claim.Claim_Amount = Decimal("50000.00")
    db.add(claim)
    db.add(
        RepairEstimate(
            Estimate_ID=f"TEST-EST-PIPE-{claim_id[-8:]}",
            Claim_ID=claim_id,
            Vehicle_ID=seed_data["vehicle1"],
            Garage_ID="GAR-TEST",
            Estimate_Date=date(2026, 1, 1),
            Repair_Estimate=Decimal("48000.00"),
            Repair_Cost=Decimal("48000.00"),
            Parts_Cost=Decimal("20000.00"),
            Labour_Cost=Decimal("20000.00"),
            Painting_Cost=Decimal("8000.00"),
            Replacement_Parts_Count=1,
            Repaired_Parts_Count=0,
            Estimated_Repair_Days=5,
            Actual_Repair_Days=0,
            Excessive_Claim_Amount_Indicator=False,
            Estimate_Anomaly_Score=Decimal("0.0000"),
        )
    )
    for suffix, document_type in [
        ("DL", "Driving Licence"),
        ("RC", "RC"),
        ("POL", "Insurance Policy"),
        ("EST", "Repair Estimate"),
    ]:
        db.add(_make_document(claim_id, f"{claim_id[-8:]}-{suffix}", document_type))
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(Document).filter(Document.Claim_ID == claim_id).delete()
    db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == claim_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


def _run(client, claim_id, token):
    return client.post(f"/api/v1/officer/claims/{claim_id}/ai-analysis/run", headers=auth_headers(token))


# ---------------------------------------------------------------- 1/2: valid analysis / not found


def test_valid_claim_analysis_returns_200(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    assert response.status_code == 200, response.text
    assert response.json()["claim_id"] == fresh_claim


def test_nonexistent_claim_returns_404(client, officer_token):
    response = _run(client, "TEST-CLM-DOES-NOT-EXIST", officer_token)
    assert response.status_code == 404


# ---------------------------------------------------------------- 3/4: RBAC


def test_customer_cannot_run_ai_analysis(client, customer1_token, fresh_claim):
    response = _run(client, fresh_claim, customer1_token)
    assert response.status_code == 403


def test_surveyor_cannot_run_ai_analysis(client, surveyor_token, fresh_claim):
    response = _run(client, fresh_claim, surveyor_token)
    assert response.status_code == 403


def test_unauthenticated_run_returns_401(client, fresh_claim):
    response = client.post(f"/api/v1/officer/claims/{fresh_claim}/ai-analysis/run")
    assert response.status_code == 401


def test_admin_can_run_ai_analysis(client, admin_token, fresh_claim):
    response = _run(client, fresh_claim, admin_token)
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------- 5/6/7: incomplete claim, missing evidence


def test_incomplete_claim_reports_insufficient_evidence(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["available"] is False
    assert body["overall_risk_score"] is None
    assert body["confidence_score"] is None


def test_missing_documents_reflected_honestly_in_evidence_summary(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    body = response.json()
    assert body["evidence_summary"]["documents"] == 0
    assert body["evidence_summary"]["vehicle_damage"] == 0
    assert body["evidence_summary"]["evidence"] == 0
    assert body["evidence_summary"]["inspections"] == 0


def test_missing_repair_estimate_reports_signal_unavailable(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    body = response.json()
    repair_signal = next(s for s in body["signals"] if s["signal_name"] == "repair_estimate_anomaly")
    assert repair_signal["availability"] == "unavailable"
    assert repair_signal["signal_value"] is None
    assert "No repair estimate" in repair_signal["explanation"]


# ---------------------------------------------------------------- 8/9: supported vs unsupported components


def test_supported_component_produces_genuine_output(client, officer_token, claim_with_repair_estimate):
    response = _run(client, claim_with_repair_estimate, officer_token)
    body = response.json()
    assert body["evidence_summary"]["repair_estimates"] == 1

    timing_signal = next(s for s in body["signals"] if s["signal_name"] == "claim_pattern_anomaly")
    assert timing_signal["availability"] == "available"
    assert timing_signal["signal_value"] is not None
    assert 0.0 <= timing_signal["signal_value"] <= 1.0

    repair_signal = next(s for s in body["signals"] if s["signal_name"] == "repair_estimate_anomaly")
    assert repair_signal["availability"] == "available"
    # 48000 / 50000 = 0.96 ratio - a genuine, real computed value.
    assert "0.96" in repair_signal["explanation"]


def test_unsupported_components_report_unavailable_with_specific_reasons(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    body = response.json()
    unavailable_names = {
        "document_consistency_mismatch", "evidence_duplication", "fraud_screening_rule_score",
        "document_completeness", "information_quality",
    }
    for signal in body["signals"]:
        if signal["signal_name"] in unavailable_names:
            assert signal["availability"] == "unavailable"
            assert signal["signal_value"] is None
            assert signal["explanation"]


def test_information_quality_explanation_states_ocr_is_research_prototype(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    body = response.json()
    info_quality = next(s for s in body["signals"] if s["signal_name"] == "information_quality")
    assert "research/prototype" in info_quality["explanation"]


# ---------------------------------------------------------------- 10: no fake score generated


def test_no_fake_score_when_evidence_insufficient(client, officer_token, fresh_claim):
    response = _run(client, fresh_claim, officer_token)
    body = response.json()
    assert body["overall_risk_score"] is None
    assert body["risk_band"] is None
    assert body["confidence_score"] is None


def test_partial_result_score_is_genuinely_computed_not_fabricated(client, officer_token, claim_with_repair_estimate):
    response = _run(client, claim_with_repair_estimate, officer_token)
    body = response.json()
    assert body["status"] == "partial"
    # Score must be the mean of exactly the 2 available signal values -
    # never an arbitrary/round number like 0.5.
    available_values = [s["signal_value"] for s in body["signals"] if s["availability"] == "available"]
    assert len(available_values) == 2
    expected = sum(available_values) / 2
    assert abs(body["overall_risk_score"] - expected) < 1e-9


# ---------------------------------------------------------------- 11/12: cannot modify decision/amount


def test_ai_analysis_run_cannot_modify_final_decision_or_approved_amount(
    client, officer_token, seed_data, claim_with_repair_estimate
):
    db = SessionLocal()
    try:
        before = db.query(Claim).filter(Claim.Claim_ID == claim_with_repair_estimate).first()
        final_decision_before = before.Final_Decision
        approved_amount_before = before.Approved_Amount
    finally:
        db.close()

    response = _run(client, claim_with_repair_estimate, officer_token)
    assert response.status_code == 200

    db = SessionLocal()
    try:
        after = db.query(Claim).filter(Claim.Claim_ID == claim_with_repair_estimate).first()
        assert after.Final_Decision == final_decision_before
        assert after.Approved_Amount == approved_amount_before
        audit_count = db.query(ClaimDecisionAudit).filter(
            ClaimDecisionAudit.Claim_ID == claim_with_repair_estimate
        ).count()
        assert audit_count == 0
    finally:
        db.close()


# ---------------------------------------------------------------- 13/14: Step 5.8.12 document_completeness integration


def test_document_completeness_signal_becomes_available_with_documents(client, officer_token, claim_with_documents):
    response = _run(client, claim_with_documents, officer_token)
    body = response.json()

    completeness_signal = next(s for s in body["signals"] if s["signal_name"] == "document_completeness")
    assert completeness_signal["availability"] == "available"
    # 4 of 5 required "Own Damage" document types present -> ratio 0.8,
    # so the (higher = more concerning) signal_value is 1 - 0.8 = 0.2.
    assert completeness_signal["signal_value"] == pytest.approx(0.2)
    assert "Accident Photos" in completeness_signal["explanation"]

    # Fusion/uncertainty are untouched - they should just now be averaging
    # 3 available signals instead of 2, with no other code path change.
    available_values = [s["signal_value"] for s in body["signals"] if s["availability"] == "available"]
    assert len(available_values) == 3
    expected_score = sum(available_values) / 3
    assert abs(body["overall_risk_score"] - expected_score) < 1e-9


def test_document_completeness_unavailable_for_zero_document_claim(client, officer_token, claim_with_repair_estimate):
    """claim_with_repair_estimate has a repair estimate but zero
    documents - completeness must stay honestly unavailable, never a
    fabricated 0%."""
    response = _run(client, claim_with_repair_estimate, officer_token)
    body = response.json()
    completeness_signal = next(s for s in body["signals"] if s["signal_name"] == "document_completeness")
    assert completeness_signal["availability"] == "unavailable"
    assert completeness_signal["signal_value"] is None
    assert "No documents" in completeness_signal["explanation"]
