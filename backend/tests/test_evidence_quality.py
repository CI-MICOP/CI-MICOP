"""Tests for Step 5.8.15 - evidence photo quality check
(services/evidence_quality.py, POST /officer/claims/{id}/evidence/quality-check).

Layers, per project convention:
  A. Pure algorithm tests and the controlled generated-image corpus
     (tests/photo_quality_corpus.py) against measure_image() / flags_for().
  B. Real end-to-end tests: genuine images uploaded through the real
     surveyor evidence endpoint into the real PostgreSQL database and local
     file storage, then checked through the real officer endpoint. Every
     evidence row and file created here is removed afterward.
"""

from collections import Counter
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import ImageEnhance, ImageFilter

from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.evidence import Evidence
from app.services import evidence_quality as eq
from tests.conftest import auth_headers
from tests.evidence_duplication_corpus import jpeg_bytes
from tests.photo_quality_corpus import CORPUS, textured_scene
from tests.test_evidence import _upload, created_evidence_ids  # noqa: F401
from tests.surveyor_records import active_claim1_inspection, surveyor_records  # noqa: F401 - fixtures

# Evidence is stored through the camera-capture endpoint (tests/test_evidence.py
# _upload), which needs the surveyor's active, scheduled, complete inspection.
pytestmark = pytest.mark.usefixtures("active_claim1_inspection")



def _check(client, token, claim_id):
    return client.post(f"/api/v1/officer/claims/{claim_id}/evidence/quality-check", headers=auth_headers(token))


def _result_for(body, evidence_id):
    return next(r for r in body["results"] if r["evidence_id"] == evidence_id)


def _upload_ok(client, token, claim_id, filename, content, created):
    response = _upload(client, token, claim_id, filename, content)
    assert response.status_code == 201, response.text
    created.append(response.json()["Evidence_ID"])
    return created[-1]


def _seed():
    return int(uuid4().int % 10**6) + 50_000


# ============================================================== A: algorithm


def test_flags_follow_each_documented_threshold():
    ok = eq.PhotoMeasurements(width=640, height=480, brightness=120, contrast=30, reblur_ratio=0.3)
    assert eq.flags_for(ok) == []
    assert eq.flags_for(eq.PhotoMeasurements(640, 479, 120, 30, 0.3)) == [eq.FLAG_LOW_RESOLUTION]
    assert eq.flags_for(eq.PhotoMeasurements(640, 480, 59.9, 30, 0.3)) == [eq.FLAG_TOO_DARK]
    assert eq.flags_for(eq.PhotoMeasurements(640, 480, 200.1, 30, 0.3)) == [eq.FLAG_TOO_BRIGHT]
    assert eq.flags_for(eq.PhotoMeasurements(640, 480, 120, 14.9, 0.3)) == [eq.FLAG_LOW_CONTRAST]
    assert eq.flags_for(eq.PhotoMeasurements(640, 480, 120, 30, 0.81)) == [eq.FLAG_BLURRY]


def test_measurements_report_the_original_size_of_large_photos():
    m = eq.measure_image(textured_scene(1).resize((1920, 1440)))
    assert (m.width, m.height) == (1920, 1440)


def test_undecodable_bytes_cannot_be_measured():
    assert eq.measure_bytes(b"\xff\xd8\xff\xe0" + b"not an image") is None


def test_missing_or_undecodable_file_is_unavailable():
    evidence = SimpleNamespace(Evidence_ID="E1", Evidence_Type="Damage Photo", File_Name="x.jpg", Claim_ID="C1")
    assert eq.assess_evidence(evidence, None).status == eq.STATUS_UNAVAILABLE
    assert eq.assess_evidence(evidence, b"\xff\xd8\xff\xe0junk").status == eq.STATUS_UNAVAILABLE


def test_explanations_and_limitations_never_mention_fraud():
    evidence = SimpleNamespace(Evidence_ID="E1", Evidence_Type="Damage Photo", File_Name="x.jpg", Claim_ID="C1")
    clear = jpeg_bytes(textured_scene(2))
    dark = jpeg_bytes(ImageEnhance.Brightness(textured_scene(2)).enhance(0.2))
    for content in (clear, dark, None):
        assert "fraud" not in eq.assess_evidence(evidence, content).explanation.lower()
    assert all("fraud" not in line.lower() for line in eq._STANDARD_LIMITATIONS)


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case.case_id)
def test_check_returns_recorded_flags_for_corpus_case(case):
    flags = tuple(eq.flags_for(eq.measure_image(case.image())))
    assert flags == case.observed_flags, f"{case.case_id} ({case.description})"


def test_corpus_summary_matches_validation_report():
    """The counts quoted in EVIDENCE_PHOTO_QUALITY.md. If this fails, the
    corpus or the check changed and the report must be updated to match."""

    def outcome(case):
        ideal, observed = set(case.ideal_flags), set(case.observed_flags)
        if ideal == observed:
            return "agrees"
        if ideal < observed and ideal:
            return "extra flag"
        if not ideal and observed:
            return "false flag"
        return "missed flag"

    outcomes = Counter(outcome(case) for case in CORPUS)
    assert len(CORPUS) == 15
    assert outcomes == {"agrees": 12, "extra flag": 2, "false flag": 1}


# ============================================================== B: real end-to-end


def test_end_to_end_clear_and_problem_photos(client, surveyor_token, officer_token, seed_data, created_evidence_ids):
    base = textured_scene(_seed())
    clear_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "clear.jpg", jpeg_bytes(base), created_evidence_ids)
    dark_id = _upload_ok(
        client, surveyor_token, seed_data["claim1"], "dark.jpg",
        jpeg_bytes(ImageEnhance.Brightness(base).enhance(0.2)), created_evidence_ids,
    )
    blurry_id = _upload_ok(
        client, surveyor_token, seed_data["claim1"], "blurry.jpg",
        jpeg_bytes(base.filter(ImageFilter.GaussianBlur(4))), created_evidence_ids,
    )
    small_id = _upload_ok(
        client, surveyor_token, seed_data["claim1"], "small.jpg", jpeg_bytes(base.resize((320, 240))), created_evidence_ids
    )

    response = _check(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    body = response.json()

    clear = _result_for(body, clear_id)
    assert clear["status"] == "NO_ISSUES_FOUND"
    assert clear["flags"] == []
    assert clear["measurements"]["width"] == 640

    assert "TOO_DARK" in _result_for(body, dark_id)["flags"]
    assert _result_for(body, blurry_id)["flags"] == ["BLURRY"]
    small = _result_for(body, small_id)
    assert small["status"] == "ISSUES_FOUND"
    assert small["flags"] == ["LOW_RESOLUTION"]
    assert "fraud" not in small["explanation"].lower()


def test_end_to_end_undecodable_photo_is_unavailable(client, surveyor_token, officer_token, seed_data, created_evidence_ids):
    evidence_id = _upload_ok(
        client, surveyor_token, seed_data["claim1"], "broken.jpg", b"\xff\xd8\xff\xe0" + uuid4().bytes, created_evidence_ids
    )
    result = _result_for(_check(client, officer_token, seed_data["claim1"]).json(), evidence_id)
    assert result["status"] == "UNAVAILABLE"
    assert result["measurements"] is None


def test_only_this_claims_photos_are_checked(
    client, surveyor_token, officer_token, seed_data, other_surveyor_claim, created_evidence_ids
):
    own_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "own.jpg", jpeg_bytes(textured_scene(_seed())), created_evidence_ids)
    body = _check(client, officer_token, other_surveyor_claim["claim_id"]).json()
    assert all(r["evidence_id"] != own_id for r in body["results"])


def test_customer_and_surveyor_cannot_run_the_check(client, customer1_token, surveyor_token, seed_data):
    for token in (customer1_token, surveyor_token):
        assert _check(client, token, seed_data["claim1"]).status_code == 403


def test_admin_can_run_the_check(client, admin_token, seed_data):
    assert _check(client, admin_token, seed_data["claim1"]).status_code == 200


def test_unknown_claim_returns_404(client, officer_token):
    assert _check(client, officer_token, "NON-EXISTENT-CLAIM").status_code == 404


def test_check_never_writes_quality_fields_decision_or_audit(
    client, surveyor_token, officer_token, seed_data, created_evidence_ids
):
    dark = ImageEnhance.Brightness(textured_scene(_seed())).enhance(0.2)
    evidence_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "d.jpg", jpeg_bytes(dark), created_evidence_ids)

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        decision_before, amount_before = claim.Final_Decision, claim.Approved_Amount
        audit_before = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
    finally:
        db.close()

    assert _result_for(_check(client, officer_token, seed_data["claim1"]).json(), evidence_id)["status"] == "ISSUES_FOUND"

    db = SessionLocal()
    try:
        evidence = db.query(Evidence).filter(Evidence.Evidence_ID == evidence_id).first()
        assert float(evidence.Image_Quality) == 0.0
        assert float(evidence.Evidence_Confidence_Score) == 0.0
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert claim.Final_Decision == decision_before
        assert claim.Approved_Amount == amount_before
        audit_after = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
        assert audit_after == audit_before
    finally:
        db.close()
