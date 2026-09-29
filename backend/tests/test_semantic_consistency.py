"""Tests for Step 5.8.13-C - semantic cross-document narrative-consistency
RESEARCH PROTOTYPE.

Two layers, per project convention (mirrors test_document_consistency.py):
  A. Pure algorithm tests against services.semantic_consistency.compare_narrative
     directly, using lightweight fake Document objects (SimpleNamespace) and
     controlled text - fast, thorough coverage of the location-comparison
     rule with no database dependency.
  B. Real end-to-end tests against the actual PostgreSQL dev/test database
     and the real API (client fixture, seed_data's claim1 - see
     tests/conftest.py), uploading genuine PyMuPDF-built PDFs with
     controlled narrative text through the real upload+analyze pipeline.

Per the Step 5.8.13 audit, the offline dataset's document text is Faker-
generated filler unrelated to any real claim fact and must never be used
as evidence of comparison correctness - it is not used anywhere here.
"""

from datetime import date
from types import SimpleNamespace

from app.services import semantic_consistency as sc
from tests.conftest import auth_headers
from tests.test_document_analysis import _text_pdf_bytes, _upload, analyzed_document_ids  # noqa: F401


def _doc(doc_id, doc_type, text, submitted=date(2026, 1, 1)):
    return SimpleNamespace(Document_ID=doc_id, Document_Type=doc_type, Extracted_Text=text, Document_Submitted_Date=submitted)


# ============================================================== A: pure algorithm


def test_consistent_when_same_stated_location():
    fir = _doc("D1", "FIR", "Accident occurred near Gandhipuram.")
    survey = _doc("D2", "Survey Report", "Vehicle was involved in an accident near Gandhipuram.")
    result = sc.compare_narrative(fir, survey)
    assert result.relationship == sc.STATUS_CONSISTENT
    assert result.confidence is None
    assert "Gandhipuram" in result.explanation
    assert "fraud" not in result.explanation.lower()


def test_contradiction_when_different_stated_location():
    fir = _doc("D1", "FIR", "The accident occurred near Gandhipuram.")
    survey = _doc("D2", "Survey Report", "Vehicle was involved in an accident near Peelamedu.")
    result = sc.compare_narrative(fir, survey)
    assert result.relationship == sc.STATUS_CONTRADICTION
    assert result.confidence is None
    assert "Gandhipuram" in result.explanation
    assert "Peelamedu" in result.explanation
    assert "officer review" in result.explanation
    assert "fraud" not in result.explanation.lower()
    assert "Fraud detected" not in result.explanation


def test_inconclusive_when_no_location_mentioned_in_either():
    fir = _doc("D1", "FIR", "Vehicle was involved in an accident.")
    survey = _doc("D2", "Survey Report", "The survey inspection was completed.")
    result = sc.compare_narrative(fir, survey)
    assert result.relationship == sc.STATUS_INCONCLUSIVE
    assert result.confidence is None


def test_inconclusive_when_one_side_has_empty_text():
    fir = _doc("D1", "FIR", "Accident occurred near Gandhipuram.")
    survey = _doc("D2", "Survey Report", "")
    result = sc.compare_narrative(fir, survey)
    assert result.relationship == sc.STATUS_INCONCLUSIVE
    assert "insufficient" in result.explanation.lower()


def test_inconclusive_when_one_document_missing_entirely():
    fir = _doc("D1", "FIR", "Accident occurred near Gandhipuram.")
    result = sc.compare_narrative(fir, None)
    assert result.relationship == sc.STATUS_INCONCLUSIVE
    assert "Survey Report" in result.explanation
    assert result.document_b is None


def test_inconclusive_when_location_is_ambiguous_multiple_mentions():
    """More than one distinct location mentioned in a single document is
    not guessed at - reported UNAVAILABLE-equivalent (INCONCLUSIVE)."""
    fir = _doc("D1", "FIR", "Accident occurred near Gandhipuram, later reported near Peelamedu.")
    survey = _doc("D2", "Survey Report", "Vehicle was involved in an accident near Gandhipuram.")
    result = sc.compare_narrative(fir, survey)
    assert result.relationship == sc.STATUS_INCONCLUSIVE


def test_never_claims_fraud_or_uses_a_probability():
    fir = _doc("D1", "FIR", "The accident occurred near Gandhipuram.")
    survey = _doc("D2", "Survey Report", "Vehicle was involved in an accident near Peelamedu.")
    result = sc.compare_narrative(fir, survey)
    assert result.relationship in (sc.STATUS_CONSISTENT, sc.STATUS_CONTRADICTION, sc.STATUS_INCONCLUSIVE)
    assert result.confidence is None
    assert "fraud" not in result.explanation.lower()
    assert all("fraud" not in limitation.lower() for limitation in result.limitations)


def test_document_pairing_prefers_most_recently_submitted_of_each_type():
    documents = [
        _doc("D1", "FIR", "Accident occurred near Gandhipuram.", submitted=date(2026, 1, 1)),  # older - ignored
        _doc("D3", "FIR", "Accident occurred near Peelamedu.", submitted=date(2026, 2, 1)),  # newest FIR - used
        _doc("D2", "Survey Report", "Vehicle was involved in an accident near Gandhipuram.", submitted=date(2026, 1, 15)),
    ]
    document_a, document_b = sc._select_document_pair(documents)
    assert document_a.Document_ID == "D3"
    assert document_b.Document_ID == "D2"


def test_document_pairing_ignores_stale_placeholder_with_earlier_id_but_later_submission():
    """Regression test for the DEV-CLM-001 manual-validation finding: a
    hand-seeded placeholder document ("DEV-DOC-001") can sort before a
    genuinely uploaded one by Document_ID alone - the pairing rule must
    key off Document_Submitted_Date, not ID order, to avoid permanently
    shadowing real documents with a stale placeholder."""
    documents = [
        _doc("DEV-DOC-001", "FIR", "FIR extract for the reported motor accident.", submitted=date(2026, 8, 21)),
        _doc("DOC-20260927-ABCDEF", "FIR", "Accident occurred near Gandhipuram.", submitted=date(2026, 9, 27)),
    ]
    document_a, _ = sc._select_document_pair(documents)
    assert document_a.Document_ID == "DOC-20260927-ABCDEF"


def test_normalize_location_is_case_and_punctuation_insensitive():
    assert sc.normalize_location("Gandhipuram") == sc.normalize_location("gandhipuram.")


# ============================================================== B: real end-to-end (seed_data claim1)


def test_end_to_end_consistent_via_semantic_consistency_endpoint(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    fir_upload = _upload(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        _text_pdf_bytes(["Accident occurred near Gandhipuram."]),
    )
    survey_upload = _upload(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        _text_pdf_bytes(["Vehicle was involved in an accident near Gandhipuram."]),
    )
    fir_id, survey_id = fir_upload.json()["Document_ID"], survey_upload.json()["Document_ID"]
    analyzed_document_ids.extend([fir_id, survey_id])
    client.post(f"/api/v1/documents/{fir_id}/analyze", headers=auth_headers(customer1_token))
    client.post(f"/api/v1/documents/{survey_id}/analyze", headers=auth_headers(customer1_token))

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["narrative"]["relationship"] == "CONSISTENT"
    assert body["narrative"]["confidence"] is None
    assert body["narrative"]["document_a"]["document_type"] == "FIR"
    assert body["narrative"]["document_b"]["document_type"] == "Survey Report"


def test_end_to_end_contradiction_via_semantic_consistency_endpoint(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    fir_upload = _upload(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        _text_pdf_bytes(["The accident occurred near Gandhipuram."]),
    )
    survey_upload = _upload(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        _text_pdf_bytes(["Vehicle was involved in an accident near Peelamedu."]),
    )
    fir_id, survey_id = fir_upload.json()["Document_ID"], survey_upload.json()["Document_ID"]
    analyzed_document_ids.extend([fir_id, survey_id])
    client.post(f"/api/v1/documents/{fir_id}/analyze", headers=auth_headers(customer1_token))
    client.post(f"/api/v1/documents/{survey_id}/analyze", headers=auth_headers(customer1_token))

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["narrative"]["relationship"] == "CONTRADICTION"


def test_end_to_end_inconclusive_with_no_fir_or_survey_report(client, officer_token, seed_data):
    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["narrative"]["relationship"] == "INCONCLUSIVE"


def test_end_to_end_registration_match_and_location_contradiction_remain_separate(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    """Test 6 from the Step 5.8.13-C brief: a deterministic MATCH on
    registration must not be overridden or hidden by a semantic
    CONTRADICTION on narrative location, and vice versa - they are
    reported as two entirely separate fields."""
    rc_upload = _upload(
        client, customer1_token, seed_data["claim1"], "rc_book", "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TEST-REG-0001."]),
    )
    fir_upload = _upload(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        _text_pdf_bytes(["Vehicle TEST-REG-0001 met with an accident near Gandhipuram."]),
    )
    survey_upload = _upload(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        _text_pdf_bytes(["The insured vehicle TEST-REG-0001 was involved in an accident near Peelamedu."]),
    )
    rc_id, fir_id, survey_id = (
        rc_upload.json()["Document_ID"],
        fir_upload.json()["Document_ID"],
        survey_upload.json()["Document_ID"],
    )
    analyzed_document_ids.extend([rc_id, fir_id, survey_id])
    for document_id in (rc_id, fir_id, survey_id):
        client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deterministic"]["registration"]["status"] == "MATCH"
    assert body["narrative"]["relationship"] == "CONTRADICTION"


# ============================================================== Security / RBAC


def test_rbac_customer_and_surveyor_cannot_call_semantic_consistency_endpoint(
    client, customer1_token, surveyor_token, seed_data
):
    for token in (customer1_token, surveyor_token):
        response = client.post(
            f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
            headers=auth_headers(token),
        )
        assert response.status_code == 403


def test_semantic_consistency_returns_404_for_unknown_claim(client, officer_token):
    response = client.post(
        "/api/v1/officer/claims/NON-EXISTENT-CLAIM/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 404


# ============================================================== Human-in-the-loop safety


def test_semantic_consistency_does_not_touch_final_decision_or_audit(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    from app.db.session import SessionLocal
    from app.db_models.claim import Claim
    from app.db_models.claim_decision_audit import ClaimDecisionAudit

    fir_upload = _upload(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        _text_pdf_bytes(["The accident occurred near Gandhipuram."]),
    )
    survey_upload = _upload(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        _text_pdf_bytes(["Vehicle was involved in an accident near Peelamedu."]),  # contradiction on purpose
    )
    fir_id, survey_id = fir_upload.json()["Document_ID"], survey_upload.json()["Document_ID"]
    analyzed_document_ids.extend([fir_id, survey_id])
    client.post(f"/api/v1/documents/{fir_id}/analyze", headers=auth_headers(customer1_token))
    client.post(f"/api/v1/documents/{survey_id}/analyze", headers=auth_headers(customer1_token))

    db = SessionLocal()
    try:
        before = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        final_decision_before, approved_amount_before = before.Final_Decision, before.Approved_Amount
        audit_before = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
    finally:
        db.close()

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.json()["narrative"]["relationship"] == "CONTRADICTION"

    db = SessionLocal()
    try:
        after = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert after.Final_Decision == final_decision_before
        assert after.Approved_Amount == approved_amount_before
        audit_after = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
        assert audit_after == audit_before
    finally:
        db.close()
