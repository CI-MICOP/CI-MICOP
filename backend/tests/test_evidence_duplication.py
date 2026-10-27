"""Tests for Step 5.8.14 - evidence duplication / reuse check
(services/evidence_duplication.py, POST /officer/claims/{id}/evidence/duplication-check).

Layers, per project convention:
  A. Pure algorithm tests and the controlled generated-image corpus
     (tests/evidence_duplication_corpus.py) against fingerprint_bytes() /
     compare_fingerprints() directly.
  B. Real end-to-end tests: genuine images uploaded through the real
     surveyor evidence endpoint into the real PostgreSQL database and local
     file storage, then checked through the real officer endpoint. Every
     evidence row and file created here is removed afterward.
"""

from collections import Counter
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.evidence import Evidence
from app.services import evidence_duplication as ed
from tests.conftest import TEST_PASSWORD, auth_headers
from tests.evidence_duplication_corpus import CORPUS, jpeg_bytes, scene
from tests.test_evidence import _upload, created_evidence_ids  # noqa: F401
from tests.surveyor_records import active_claim1_inspection, surveyor_records  # noqa: F401 - fixtures

# Evidence is stored through the camera-capture endpoint (tests/test_evidence.py
# _upload), which needs the surveyor's active, scheduled, complete inspection.
pytestmark = pytest.mark.usefixtures("active_claim1_inspection")



def _check(client, token, claim_id):
    return client.post(f"/api/v1/officer/claims/{claim_id}/evidence/duplication-check", headers=auth_headers(token))


def _result_for(body, evidence_id):
    return next(r for r in body["results"] if r["evidence_id"] == evidence_id)


def _unique_scene_bytes():
    """A generated image no other test (or earlier run) will have stored."""
    return jpeg_bytes(scene(int(uuid4().int % 10**9) + 10_000))


# ============================================================== A: algorithm


def test_identical_bytes_are_an_exact_match():
    content = jpeg_bytes(scene(1))
    found = ed.compare_fingerprints(ed.fingerprint_bytes(content), ed.fingerprint_bytes(content))
    assert found == (ed.MATCH_EXACT, 0)


def test_dhash_is_64_bits_and_hamming_counts_differing_bits():
    value = ed.compute_dhash(scene(2))
    assert 0 <= value < 2**64
    assert ed.hamming_distance(0b1011, 0b0001) == 2


def test_undecodable_bytes_have_no_dhash_but_still_match_exactly():
    content = b"\xff\xd8\xff\xe0" + b"not really an image"
    fingerprint = ed.fingerprint_bytes(content)
    assert fingerprint.dhash is None
    assert ed.compare_fingerprints(fingerprint, ed.fingerprint_bytes(content)) == (ed.MATCH_EXACT, None)


def test_missing_stored_file_is_unavailable_not_no_match():
    evidence = SimpleNamespace(Evidence_ID="E1", Evidence_Type="Damage Photo", File_Name="x.jpg", Claim_ID="C1")
    result = ed._result_for(evidence, None, [])
    assert result.status == ed.STATUS_UNAVAILABLE
    assert result.matches == []


def test_explanations_and_limitations_never_mention_fraud():
    content = jpeg_bytes(scene(3))
    fp = ed.fingerprint_bytes(content)
    me = SimpleNamespace(Evidence_ID="E1", Evidence_Type="Damage Photo", File_Name="a.jpg", Claim_ID="C1")
    other = SimpleNamespace(Evidence_ID="E2", Evidence_Type="Damage Photo", File_Name="b.jpg", Claim_ID="C2")
    for result in (ed._result_for(me, fp, [(other, fp)]), ed._result_for(me, fp, [])):
        assert "fraud" not in result.explanation.lower()
    assert all("fraud" not in line.lower() for line in ed._STANDARD_LIMITATIONS)


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case.case_id)
def test_check_returns_recorded_result_for_corpus_case(case):
    a, b = case.image_bytes()
    found = ed.compare_fingerprints(ed.fingerprint_bytes(a), ed.fingerprint_bytes(b))
    assert (found[0] if found else None) == case.observed, f"{case.case_id} ({case.description})"


def test_corpus_summary_matches_validation_report():
    """The counts quoted in EVIDENCE_DUPLICATION.md. If this fails, the
    corpus or the check changed and the report must be updated to match."""
    outcomes = Counter((case.should_match, case.observed is not None) for case in CORPUS)
    assert len(CORPUS) == 18
    assert outcomes[(True, True)] == 7  # copies caught
    assert outcomes[(True, False)] == 6  # copies missed
    assert outcomes[(False, False)] == 5  # different images correctly not matched
    assert outcomes[(False, True)] == 0  # false match - never observed


# ============================================================== B: real end-to-end


def _login_surveyor2(client):
    response = client.post("/api/v1/auth/login", data={"username": "test_surveyor2", "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _upload_ok(client, token, claim_id, filename, content, created):
    response = _upload(client, token, claim_id, filename, content)
    assert response.status_code == 201, response.text
    evidence_id = response.json()["Evidence_ID"]
    created.append(evidence_id)
    return evidence_id


def test_end_to_end_exact_copy_reused_on_another_claim(
    client, surveyor_token, officer_token, seed_data, other_surveyor_claim, created_evidence_ids
):
    content = _unique_scene_bytes()
    own_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "front.jpg", content, created_evidence_ids)
    other_id = _upload_ok(
        client, _login_surveyor2(client), other_surveyor_claim["claim_id"], "reused.jpg", content, created_evidence_ids
    )

    response = _check(client, officer_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    result = _result_for(response.json(), own_id)
    assert result["status"] == "EXACT_DUPLICATE"
    match = next(m for m in result["matches"] if m["evidence_id"] == other_id)
    assert match["claim_id"] == other_surveyor_claim["claim_id"]
    assert match["same_claim"] is False
    assert match["match_type"] == "EXACT"
    assert "fraud" not in result["explanation"].lower()


def test_end_to_end_near_copy_on_the_same_claim(client, surveyor_token, officer_token, seed_data, created_evidence_ids):
    original = scene(int(uuid4().int % 10**9) + 20_000)
    first_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "a.jpg", jpeg_bytes(original), created_evidence_ids)
    resized = original.resize((original.width // 2, original.height // 2))
    second_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "b.jpg", jpeg_bytes(resized, 60), created_evidence_ids)

    body = _check(client, officer_token, seed_data["claim1"]).json()
    first = _result_for(body, first_id)
    assert first["status"] == "NEAR_DUPLICATE"
    match = next(m for m in first["matches"] if m["evidence_id"] == second_id)
    assert match["same_claim"] is True
    assert match["hash_distance"] <= ed.NEAR_DUPLICATE_MAX_DISTANCE
    assert _result_for(body, second_id)["status"] == "NEAR_DUPLICATE"


def test_end_to_end_different_photo_is_no_match_found(
    client, surveyor_token, officer_token, seed_data, created_evidence_ids
):
    evidence_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "c.jpg", _unique_scene_bytes(), created_evidence_ids)
    result = _result_for(_check(client, officer_token, seed_data["claim1"]).json(), evidence_id)
    assert result["status"] == "NO_MATCH_FOUND"
    assert result["matches"] == []


def test_end_to_end_undecodable_photo_is_unavailable(
    client, surveyor_token, officer_token, seed_data, created_evidence_ids
):
    content = b"\xff\xd8\xff\xe0" + uuid4().bytes  # passes the upload signature check, is not a real image
    evidence_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "broken.jpg", content, created_evidence_ids)
    result = _result_for(_check(client, officer_token, seed_data["claim1"]).json(), evidence_id)
    assert result["status"] == "UNAVAILABLE"


def test_customer_and_surveyor_cannot_run_the_check(client, customer1_token, surveyor_token, seed_data):
    for token in (customer1_token, surveyor_token):
        assert _check(client, token, seed_data["claim1"]).status_code == 403


def test_admin_can_run_the_check(client, admin_token, seed_data):
    assert _check(client, admin_token, seed_data["claim1"]).status_code == 200


def test_unknown_claim_returns_404(client, officer_token):
    assert _check(client, officer_token, "NON-EXISTENT-CLAIM").status_code == 404


def test_check_never_writes_indicator_decision_or_audit(
    client, surveyor_token, officer_token, seed_data, other_surveyor_claim, created_evidence_ids
):
    content = _unique_scene_bytes()
    own_id = _upload_ok(client, surveyor_token, seed_data["claim1"], "d.jpg", content, created_evidence_ids)
    _upload_ok(client, _login_surveyor2(client), other_surveyor_claim["claim_id"], "e.jpg", content, created_evidence_ids)

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        decision_before, amount_before = claim.Final_Decision, claim.Approved_Amount
        audit_before = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
    finally:
        db.close()

    assert _result_for(_check(client, officer_token, seed_data["claim1"]).json(), own_id)["status"] == "EXACT_DUPLICATE"

    db = SessionLocal()
    try:
        evidence = db.query(Evidence).filter(Evidence.Evidence_ID == own_id).first()
        assert evidence.Duplicate_Evidence_Indicator is False
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert claim.Final_Decision == decision_before
        assert claim.Approved_Amount == amount_before
        audit_after = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
        assert audit_after == audit_before
    finally:
        db.close()
