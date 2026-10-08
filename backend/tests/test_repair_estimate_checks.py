"""Tests for Steps 5.8.21 and 5.8.22 - repair estimate checks
(services/repair_estimate_checks.py, POST /officer/claims/{id}/repair-estimates/check).

Layers, per project convention:
  A. Pure tests of each check and the controlled corpus
     (tests/repair_estimate_corpus.py).
  B. Real end-to-end tests: estimates and damage records created through the
     real surveyor endpoints into the real PostgreSQL database, then checked
     through the real officer endpoint. Every row created here is removed
     afterward.
"""

from collections import Counter
from datetime import date, time
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.db_models.accident import Accident
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.repair_estimate import RepairEstimate
from app.services import repair_estimate_checks as rec
from tests.conftest import auth_headers
from tests.repair_estimate_corpus import (
    CLAIM_AMOUNT_RATIO,
    CORPUS,
    COST_VS_ESTIMATE,
    DAMAGE_COST_RATIO,
    ESTIMATE_DATE,
    REPAIR_DAYS,
    REPLACEMENT_PARTS,
)
from tests.test_repair_estimate import _payload as estimate_payload
from tests.test_repair_estimate import created_estimate_ids  # noqa: F401
from tests.test_vehicle_damage import _payload as damage_payload
from tests.test_vehicle_damage import created_damage_ids  # noqa: F401

ACCIDENT_DATE = date(2026, 8, 20)

_CORPUS_CHECKS = {
    ESTIMATE_DATE: rec.check_estimate_date,
    CLAIM_AMOUNT_RATIO: rec.check_claim_amount_ratio,
    REPLACEMENT_PARTS: rec.check_replacement_parts,
    COST_VS_ESTIMATE: rec.check_cost_vs_estimate,
    DAMAGE_COST_RATIO: rec.check_damage_cost_ratio,
    REPAIR_DAYS: rec.check_repair_days,
}


def _check(client, token, claim_id):
    return client.post(f"/api/v1/officer/claims/{claim_id}/repair-estimates/check", headers=auth_headers(token))


def _create_estimate(client, token, claim_id, created, **overrides):
    response = client.post(
        "/api/v1/surveyor/repair-estimates", json=estimate_payload(claim_id, **overrides), headers=auth_headers(token)
    )
    assert response.status_code == 201, response.text
    created.append(response.json()["Estimate_ID"])
    return created[-1]


def _create_damage(client, token, claim_id, created, **overrides):
    response = client.post(
        "/api/v1/surveyor/vehicle-damage", json=damage_payload(claim_id, **overrides), headers=auth_headers(token)
    )
    assert response.status_code == 201, response.text
    created.append(response.json()["Damage_ID"])
    return created[-1]


def _result_for(body, estimate_id):
    return next(r for r in body["results"] if r["estimate_id"] == estimate_id)


def _check_named(result, name):
    return next(c for c in result["checks"] if c["check"] == name)


@pytest.fixture()
def claim1_accident(seed_data):
    db = SessionLocal()
    accident_id = "TEST-ACC-5821"
    db.add(
        Accident(
            Accident_ID=accident_id, Claim_ID=seed_data["claim1"], Accident_Date=ACCIDENT_DATE, Accident_Time=time(18, 30),
            Accident_Location="Anna Salai, Chennai", Accident_City="Chennai", Accident_State="Tamil Nadu",
            Accident_Pincode="600002", Accident_Type="Collision", Accident_Description="Test accident record.",
            Weather_Condition="Clear", Road_Condition="Dry", Road_Type_Code="URBAN", Police_Report_Available=False,
            FIR_Number=None, Third_Party_Involved=False, Injury_Reported=False, Witness_Available=False,
        )
    )
    db.commit()
    db.close()
    yield accident_id
    db = SessionLocal()
    db.query(Accident).filter(Accident.Accident_ID == accident_id).delete()
    db.commit()
    db.close()


# ============================================================== A: each check


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case.case_id)
def test_check_returns_recorded_result_for_corpus_case(case):
    assert _CORPUS_CHECKS[case.check](**case.inputs).status == case.observed, f"{case.case_id} ({case.note})"


def test_corpus_summary_matches_validation_report():
    """The counts quoted in REPAIR_ESTIMATE_CHECKS.md. If this fails, the
    corpus or a check changed and the report must be updated to match."""

    def outcome(case):
        if case.ideal == case.observed:
            return "agrees"
        if case.observed == "FLAGGED":
            return "false flag"
        return "missed flag" if case.ideal == "FLAGGED" else "other"

    outcomes = Counter(outcome(case) for case in CORPUS)
    assert len(CORPUS) == 32
    assert outcomes == {"agrees": 28, "missed flag": 4}
    assert [c.case_id for c in CORPUS if c.ideal != c.observed] == ["D05", "P05", "M05", "T06"]


def test_claim_amount_ratio_uses_the_ai_pipeline_reference():
    from app.services import ai_pipeline

    assert rec.REPAIR_RATIO_P90 == ai_pipeline.REPAIR_RATIO_P90
    flagged = rec.check_claim_amount_ratio(Decimal("150000.00"), Decimal("50000.00"))
    assert flagged.value == "3.00"
    assert "2.97" in flagged.reference
    assert "valid reasons" in flagged.explanation


def test_cost_vs_estimate_states_the_gap_and_uses_the_reference_range():
    above = rec.check_cost_vs_estimate(Decimal("52000.00"), Decimal("50000.00"))
    assert above.status == rec.STATUS_NOT_FLAGGED
    assert "INR 2,000.00 (4.0%) above" in above.explanation
    assert "15.4%" in above.reference
    below = rec.check_cost_vs_estimate(Decimal("45000.00"), Decimal("50000.00"))
    assert below.status == rec.STATUS_NOT_FLAGGED
    assert "INR 5,000.00 (10.0%) below" in below.explanation
    assert "equal to" in rec.check_cost_vs_estimate(Decimal("50000.00"), Decimal("50000.00")).explanation
    assert rec.check_cost_vs_estimate(Decimal("100.00"), Decimal("0.00")).status == rec.STATUS_UNAVAILABLE
    flagged = rec.check_cost_vs_estimate(Decimal("60000.00"), Decimal("50000.00"))
    assert flagged.status == rec.STATUS_FLAGGED
    assert "INR 10,000.00 (20.0%) above" in flagged.explanation
    assert "valid reasons" in flagged.explanation


def test_damage_cost_ratio_sums_all_damage_records():
    within = rec.check_damage_cost_ratio(Decimal("60000.00"), [Decimal("10000.00"), Decimal("20000.00")])
    assert within.status == rec.STATUS_NOT_FLAGGED
    assert within.value == "2.00"
    assert "2 record(s)" in within.reference
    assert "5.34" in within.reference
    assert rec.check_damage_cost_ratio(Decimal("60000.00"), []).status == rec.STATUS_UNAVAILABLE
    assert rec.check_damage_cost_ratio(Decimal("60000.00"), [Decimal("0.00")]).status == rec.STATUS_UNAVAILABLE
    assert rec.check_damage_cost_ratio(Decimal("0.00"), [Decimal("10000.00")]).status == rec.STATUS_UNAVAILABLE
    flagged = rec.check_damage_cost_ratio(Decimal("60000.00"), [Decimal("10000.00")])
    assert (flagged.status, flagged.value) == (rec.STATUS_FLAGGED, "6.00")
    assert "valid reasons" in flagged.explanation


def test_repair_days_treats_zero_actual_days_as_not_recorded():
    assert rec.check_repair_days(7, 0).status == rec.STATUS_UNAVAILABLE
    assert rec.check_repair_days(0, 5).status == rec.STATUS_UNAVAILABLE
    over = rec.check_repair_days(7, 12)
    assert over.status == rec.STATUS_NOT_FLAGGED
    assert "5 day(s) more than estimated" in over.explanation
    assert "2 day(s) fewer than estimated" in rec.check_repair_days(7, 5).explanation
    assert "the same as estimated" in rec.check_repair_days(7, 7).explanation
    flagged = rec.check_repair_days(7, 20)
    assert flagged.status == rec.STATUS_FLAGGED
    assert "13 day(s) more than estimated" in flagged.explanation
    assert "valid reasons" in flagged.explanation


def test_reference_ranges_are_ordered():
    assert rec.COST_RATIO_P50 < rec.COST_RATIO_P90
    assert rec.DAMAGE_COST_RATIO_P50 < rec.DAMAGE_COST_RATIO_P90
    assert rec.EXTRA_REPAIR_DAYS_P50 < rec.EXTRA_REPAIR_DAYS_P90


def test_estimate_status_follows_its_checks():
    def check(status):
        return rec.EstimateCheck("X", status, None, None, "")

    assert rec.estimate_status([check(rec.STATUS_NOT_FLAGGED), check(rec.STATUS_FLAGGED)]) == rec.ESTIMATE_POINTS_TO_REVIEW
    assert rec.estimate_status([check(rec.STATUS_NOT_FLAGGED), check(rec.STATUS_INFO)]) == rec.ESTIMATE_NO_POINTS_FOUND
    # Information-only results are never presented as "checked and fine".
    assert rec.estimate_status([check(rec.STATUS_INFO), check(rec.STATUS_UNAVAILABLE)]) == rec.ESTIMATE_UNAVAILABLE


def test_quote_comparison_needs_two_estimates_and_reports_the_gap():
    assert rec.compare_quotes([]) is None
    assert rec.compare_quotes([("E1", "GAR-1", Decimal("50000.00"))]) is None
    quotes = rec.compare_quotes(
        [("E1", "GAR-1", Decimal("50000.00")), ("E2", "GAR-2", Decimal("70000.00")), ("E3", "GAR-2", Decimal("60000.00"))]
    )
    assert (quotes.estimates_compared, quotes.garages) == (3, 2)
    assert (quotes.lowest_estimate_id, quotes.highest_estimate_id) == ("E1", "E2")
    assert quotes.difference == Decimal("20000.00")
    assert quotes.difference_percent == 40.0
    assert "information only" in quotes.explanation


def test_explanations_and_limitations_never_mention_fraud():
    results = [_CORPUS_CHECKS[case.check](**case.inputs) for case in CORPUS]
    results += [
        rec.check_cost_vs_estimate(Decimal("52000.00"), Decimal("50000.00")),
        rec.check_damage_cost_ratio(Decimal("60000.00"), [Decimal("10000.00")]),
        rec.check_repair_days(7, 12),
    ]
    assert all("fraud" not in r.explanation.lower() for r in results)
    assert all("fraud" not in line.lower() for line in rec._STANDARD_LIMITATIONS)


# ============================================================== B: real end-to-end


def test_end_to_end_estimate_with_no_points(
    client, surveyor_token, officer_token, seed_data, claim1_accident, created_estimate_ids, created_damage_ids
):
    _create_damage(client, surveyor_token, seed_data["claim1"], created_damage_ids, Repair_or_Replace="Replace")
    estimate_id = _create_estimate(
        client, surveyor_token, seed_data["claim1"], created_estimate_ids,
        Estimate_Date="2026-08-22", Repair_Estimate="40000.00", Repair_Cost="42000.00",
    )

    response = _check(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["estimates_checked"] == 1
    assert body["quote_comparison"] is None

    result = _result_for(body, estimate_id)
    assert result["status"] == "NO_POINTS_FOUND"
    assert _check_named(result, "ESTIMATE_DATE")["status"] == "NOT_FLAGGED"
    ratio = _check_named(result, "CLAIM_AMOUNT_RATIO")
    assert (ratio["status"], ratio["value"]) == ("NOT_FLAGGED", "0.80")  # 40000 / seed claim amount 50000
    assert _check_named(result, "REPLACEMENT_PARTS")["status"] == "NOT_FLAGGED"
    assert _check_named(result, "COST_VS_ESTIMATE")["status"] == "NOT_FLAGGED"  # 42000 / 40000
    assert _check_named(result, "DAMAGE_COST_RATIO")["status"] == "NOT_FLAGGED"  # 40000 / 15000
    assert _check_named(result, "REPAIR_DAYS")["status"] == "UNAVAILABLE"  # actual days not recorded


def test_end_to_end_estimate_with_every_point_to_review(
    client, surveyor_token, officer_token, seed_data, claim1_accident, created_estimate_ids, created_damage_ids
):
    _create_damage(client, surveyor_token, seed_data["claim1"], created_damage_ids, Repair_or_Replace="Repair")
    estimate_id = _create_estimate(
        client, surveyor_token, seed_data["claim1"], created_estimate_ids,
        Estimate_Date="2026-08-19", Repair_Estimate="150000.00", Repair_Cost="180000.00", Replacement_Parts_Count=3,
        Estimated_Repair_Days=7, Actual_Repair_Days=20,
    )

    result = _result_for(_check(client, officer_token, seed_data["claim1"]).json(), estimate_id)
    assert result["status"] == "POINTS_TO_REVIEW"
    date_check = _check_named(result, "ESTIMATE_DATE")
    assert date_check["status"] == "FLAGGED"
    assert "1 day(s) before" in date_check["explanation"]
    assert _check_named(result, "CLAIM_AMOUNT_RATIO")["status"] == "FLAGGED"
    assert _check_named(result, "REPLACEMENT_PARTS")["status"] == "FLAGGED"
    assert _check_named(result, "COST_VS_ESTIMATE")["status"] == "FLAGGED"  # 180000 / 150000
    assert _check_named(result, "DAMAGE_COST_RATIO")["status"] == "FLAGGED"  # 150000 / 15000
    assert _check_named(result, "REPAIR_DAYS")["status"] == "FLAGGED"  # 13 days over
    assert all("fraud" not in c["explanation"].lower() for c in result["checks"])


def test_end_to_end_without_accident_or_damage_records(
    client, surveyor_token, officer_token, seed_data, created_estimate_ids
):
    estimate_id = _create_estimate(client, surveyor_token, seed_data["claim1"], created_estimate_ids)
    result = _result_for(_check(client, officer_token, seed_data["claim1"]).json(), estimate_id)
    assert _check_named(result, "ESTIMATE_DATE")["status"] == "UNAVAILABLE"
    assert _check_named(result, "REPLACEMENT_PARTS")["status"] == "UNAVAILABLE"
    assert _check_named(result, "DAMAGE_COST_RATIO")["status"] == "UNAVAILABLE"
    assert _check_named(result, "CLAIM_AMOUNT_RATIO")["status"] == "NOT_FLAGGED"  # 50000 / 50000


def test_end_to_end_two_estimates_are_set_side_by_side(
    client, surveyor_token, officer_token, seed_data, created_estimate_ids
):
    low = _create_estimate(
        client, surveyor_token, seed_data["claim1"], created_estimate_ids, Garage_ID="GAR-0001", Repair_Estimate="50000.00"
    )
    high = _create_estimate(
        client, surveyor_token, seed_data["claim1"], created_estimate_ids, Garage_ID="GAR-0002", Repair_Estimate="70000.00"
    )

    body = _check(client, officer_token, seed_data["claim1"]).json()
    assert body["estimates_checked"] == 2
    quotes = body["quote_comparison"]
    assert (quotes["estimates_compared"], quotes["garages"]) == (2, 2)
    assert (quotes["lowest_estimate_id"], quotes["highest_estimate_id"]) == (low, high)
    assert float(quotes["difference"]) == 20000.0
    assert quotes["difference_percent"] == 40.0


def test_claim_without_estimates_returns_an_empty_result(client, officer_token, seed_data):
    body = _check(client, officer_token, seed_data["claim1"]).json()
    assert body["estimates_checked"] == 0
    assert body["results"] == []
    assert body["quote_comparison"] is None


def test_only_this_claims_estimates_are_checked(
    client, surveyor_token, officer_token, seed_data, other_surveyor_claim, created_estimate_ids
):
    own_id = _create_estimate(client, surveyor_token, seed_data["claim1"], created_estimate_ids)
    body = _check(client, officer_token, other_surveyor_claim["claim_id"]).json()
    assert all(r["estimate_id"] != own_id for r in body["results"])


def test_customer_and_surveyor_cannot_run_the_check(client, customer1_token, surveyor_token, seed_data):
    for token in (customer1_token, surveyor_token):
        assert _check(client, token, seed_data["claim1"]).status_code == 403


def test_unauthenticated_check_returns_401(client, seed_data):
    assert client.post(f"/api/v1/officer/claims/{seed_data['claim1']}/repair-estimates/check").status_code == 401


def test_admin_can_run_the_check(client, admin_token, seed_data):
    assert _check(client, admin_token, seed_data["claim1"]).status_code == 200


def test_unknown_claim_returns_404(client, officer_token):
    assert _check(client, officer_token, "NON-EXISTENT-CLAIM").status_code == 404


def test_check_never_writes_estimate_flags_decision_or_audit(
    client, surveyor_token, officer_token, seed_data, created_estimate_ids
):
    estimate_id = _create_estimate(
        client, surveyor_token, seed_data["claim1"], created_estimate_ids, Repair_Estimate="150000.00"
    )

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        decision_before, amount_before = claim.Final_Decision, claim.Approved_Amount
        audit_before = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
    finally:
        db.close()

    result = _result_for(_check(client, officer_token, seed_data["claim1"]).json(), estimate_id)
    assert result["status"] == "POINTS_TO_REVIEW"

    db = SessionLocal()
    try:
        estimate = db.query(RepairEstimate).filter(RepairEstimate.Estimate_ID == estimate_id).first()
        assert estimate.Excessive_Claim_Amount_Indicator is False
        assert float(estimate.Estimate_Anomaly_Score) == 0.0
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert claim.Final_Decision == decision_before
        assert claim.Approved_Amount == amount_before
        audit_after = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
        assert audit_after == audit_before
    finally:
        db.close()
