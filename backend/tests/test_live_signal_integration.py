"""Tests for Step 5.8.18 - live analysis checks feeding the AI risk-fusion
signals (services/ai_pipeline.py, POST /officer/claims/{id}/ai-analysis/run).

Real end-to-end: documents and photos are uploaded through the real
endpoints into the real PostgreSQL database and file storage, analyzed, and
the live AI run is called. Every document and evidence row/file created
here is removed afterward.
"""

from uuid import uuid4

from PIL import ImageEnhance

from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from tests.conftest import auth_headers
from tests.evidence_duplication_corpus import jpeg_bytes
from tests.photo_quality_corpus import textured_scene
from tests.test_document_analysis import _text_pdf_bytes, analyzed_document_ids  # noqa: F401
from tests.test_document_analysis import _upload as _upload_document
from tests.test_evidence import _upload as _upload_evidence
from tests.test_evidence import created_evidence_ids  # noqa: F401
import pytest
from tests.surveyor_records import active_claim1_inspection, surveyor_records  # noqa: F401 - fixtures

# Evidence is stored through the camera-capture endpoint (tests/test_evidence.py
# _upload), which needs the surveyor's active, scheduled, complete inspection.
pytestmark = pytest.mark.usefixtures("active_claim1_inspection")



def _run(client, token, claim_id):
    response = client.post(f"/api/v1/officer/claims/{claim_id}/ai-analysis/run", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def _signal(body, name):
    return next(s for s in body["signals"] if s["signal_name"] == name)


def _add_document(client, token, claim_id, document_type, text, created):
    response = _upload_document(client, token, claim_id, document_type, f"{document_type}.pdf", _text_pdf_bytes([text]))
    assert response.status_code == 201, response.text
    document_id = response.json()["Document_ID"]
    created.append(document_id)
    assert client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(token)).status_code == 200
    return document_id


def _add_photo(client, token, claim_id, content, created):
    response = _upload_evidence(client, token, claim_id, "photo.jpg", content)
    assert response.status_code == 201, response.text
    created.append(response.json()["Evidence_ID"])
    return created[-1]


def _seed():
    return int(uuid4().int % 10**6) + 80_000


# ---------------------------------------------------------------- document consistency


def test_document_consistency_signal_from_a_location_contradiction(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    _add_document(client, customer1_token, seed_data["claim1"], "fir_copy", "The accident occurred near Gandhipuram.", analyzed_document_ids)
    _add_document(client, customer1_token, seed_data["claim1"], "survey_report", "The vehicle was damaged near Peelamedu.", analyzed_document_ids)

    signal = _signal(_run(client, officer_token, seed_data["claim1"]), "document_consistency_mismatch")
    assert signal["availability"] == "available"
    assert signal["signal_value"] == 1.0  # 1 of 1 comparable check disagrees
    assert "1/1" in signal["explanation"]
    assert "FIR vs Survey Report location" in signal["explanation"]
    assert "fraud" not in signal["explanation"].lower()


def test_document_consistency_signal_is_zero_when_documents_agree(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    _add_document(client, customer1_token, seed_data["claim1"], "fir_copy", "The accident occurred near Gandhipuram.", analyzed_document_ids)
    _add_document(client, customer1_token, seed_data["claim1"], "survey_report", "The vehicle was damaged near Gandhipuram.", analyzed_document_ids)

    signal = _signal(_run(client, officer_token, seed_data["claim1"]), "document_consistency_mismatch")
    assert signal["availability"] == "available"
    assert signal["signal_value"] == 0.0


def test_document_consistency_signal_unavailable_without_comparable_text(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    _add_document(client, customer1_token, seed_data["claim1"], "fir_copy", "Vehicle met with an accident.", analyzed_document_ids)

    signal = _signal(_run(client, officer_token, seed_data["claim1"]), "document_consistency_mismatch")
    assert signal["availability"] == "unavailable"
    assert signal["signal_value"] is None
    assert "Analyze Documents" in signal["explanation"]


# ---------------------------------------------------------------- evidence duplication


def test_evidence_duplication_signal_is_one_when_a_photo_is_copied(
    client, surveyor_token, officer_token, seed_data, created_evidence_ids
):
    content = jpeg_bytes(textured_scene(_seed()))
    _add_photo(client, surveyor_token, seed_data["claim1"], content, created_evidence_ids)
    _add_photo(client, surveyor_token, seed_data["claim1"], content, created_evidence_ids)

    signal = _signal(_run(client, officer_token, seed_data["claim1"]), "evidence_duplication")
    assert signal["availability"] == "available"
    assert signal["signal_value"] == 1.0
    assert "not an image-recognition model" in signal["explanation"]


def test_evidence_duplication_signal_is_zero_for_original_photos(
    client, surveyor_token, officer_token, seed_data, created_evidence_ids
):
    _add_photo(client, surveyor_token, seed_data["claim1"], jpeg_bytes(textured_scene(_seed())), created_evidence_ids)

    signal = _signal(_run(client, officer_token, seed_data["claim1"]), "evidence_duplication")
    assert signal["availability"] == "available"
    assert signal["signal_value"] == 0.0


def test_evidence_signals_unavailable_without_photos(client, officer_token, seed_data):
    body = _run(client, officer_token, seed_data["claim1"])
    assert _signal(body, "evidence_duplication")["availability"] == "unavailable"
    assert _signal(body, "information_quality")["availability"] == "unavailable"


# ---------------------------------------------------------------- information quality


def test_information_quality_signal_is_share_of_photos_with_issues(
    client, surveyor_token, officer_token, seed_data, created_evidence_ids
):
    base = textured_scene(_seed())
    _add_photo(client, surveyor_token, seed_data["claim1"], jpeg_bytes(base), created_evidence_ids)
    _add_photo(
        client, surveyor_token, seed_data["claim1"],
        jpeg_bytes(ImageEnhance.Brightness(textured_scene(_seed())).enhance(0.2)), created_evidence_ids,
    )

    signal = _signal(_run(client, officer_token, seed_data["claim1"]), "information_quality")
    assert signal["availability"] == "available"
    assert signal["signal_value"] == 0.5  # 1 of 2 photos too dark
    assert signal["confidence"] == 1.0  # claim1 has a surveyor inspection on record
    assert "OCR" in signal["explanation"]


# ---------------------------------------------------------------- fusion and safety


def test_fraud_screening_stays_unavailable_and_score_uses_only_available_signals(
    client, customer1_token, surveyor_token, officer_token, seed_data, analyzed_document_ids, created_evidence_ids
):
    _add_document(client, customer1_token, seed_data["claim1"], "fir_copy", "The accident occurred near Gandhipuram.", analyzed_document_ids)
    _add_document(client, customer1_token, seed_data["claim1"], "survey_report", "The vehicle was damaged near Peelamedu.", analyzed_document_ids)
    _add_photo(client, surveyor_token, seed_data["claim1"], jpeg_bytes(textured_scene(_seed())), created_evidence_ids)

    body = _run(client, officer_token, seed_data["claim1"])
    assert _signal(body, "fraud_screening_rule_score")["availability"] == "unavailable"
    assert body["status"] == "partial"  # 7/7 is never reachable while fraud screening stays off

    available = [s for s in body["signals"] if s["availability"] == "available"]
    assert {s["signal_name"] for s in available} >= {"document_consistency_mismatch", "evidence_duplication", "information_quality"}
    expected = sum(s["signal_value"] for s in available) / len(available)
    assert abs(body["overall_risk_score"] - expected) < 1e-9


def test_live_run_with_new_signals_never_touches_decision_or_audit(
    client, customer1_token, surveyor_token, officer_token, seed_data, analyzed_document_ids, created_evidence_ids
):
    _add_document(client, customer1_token, seed_data["claim1"], "fir_copy", "The accident occurred near Gandhipuram.", analyzed_document_ids)
    _add_document(client, customer1_token, seed_data["claim1"], "survey_report", "The vehicle was damaged near Peelamedu.", analyzed_document_ids)
    content = jpeg_bytes(textured_scene(_seed()))
    _add_photo(client, surveyor_token, seed_data["claim1"], content, created_evidence_ids)
    _add_photo(client, surveyor_token, seed_data["claim1"], content, created_evidence_ids)

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        before = (claim.Final_Decision, claim.Approved_Amount, claim.Claim_Status)
        audit_before = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
    finally:
        db.close()

    body = _run(client, officer_token, seed_data["claim1"])
    assert _signal(body, "evidence_duplication")["signal_value"] == 1.0

    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert (claim.Final_Decision, claim.Approved_Amount, claim.Claim_Status) == before
        assert db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count() == audit_before
    finally:
        db.close()
