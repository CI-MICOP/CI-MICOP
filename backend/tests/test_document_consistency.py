"""Tests for Step 5.8.13-B - deterministic cross-document consistency.

Two layers, per project convention:
  A. Pure algorithm tests against services.document_consistency._compare_entity
     directly, using lightweight fake Document objects (SimpleNamespace) and
     controlled text - fast, thorough coverage of the candidate-resolution
     rule with no database dependency.
  B. Real end-to-end tests against the actual PostgreSQL dev/test database
     and the real API (client fixture, seed_data's claim1 -
     Registration_Number="TEST-REG-0001", Policy_Number="TEST-POLNUM-0001" -
     see tests/conftest.py), uploading genuine PyMuPDF-built PDFs with
     controlled text through the real upload+analyze pipeline.

Per the Step 5.8.13 audit, the offline dataset's document text is Faker-
generated filler unrelated to any real claim fact and must never be used
as evidence of comparison correctness - it is not used anywhere here.
"""

from types import SimpleNamespace

import pytest

from app.services import document_consistency as dc
from app.services import entity_extraction as ee
from tests.conftest import auth_headers
from tests.test_document_analysis import PDF_MAGIC_ONLY, _text_pdf_bytes, _upload, analyzed_document_ids  # noqa: F401 (re-exported fixture)


def _doc(doc_id, doc_type, text, conf=0.9):
    return SimpleNamespace(Document_ID=doc_id, Document_Type=doc_type, Extracted_Text=text, OCR_Confidence_Score=conf)


# ============================================================== A: pure algorithm - registration


def test_registration_exact_match():
    result = dc._compare_entity(
        ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "Vehicle Registration Number: TN01AB0001.")]
    )
    assert result.status == dc.STATUS_MATCH
    assert result.matched_document_type == "RC"
    assert result.matched_document_id == "D1"


def test_registration_match_despite_spaces():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "Reg No: TN 01 AB 0001")])
    assert result.status == dc.STATUS_MATCH


def test_registration_match_despite_hyphens_and_case():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "tn-01-ab-0001")])
    assert result.status == dc.STATUS_MATCH


def test_registration_mismatch():
    result = dc._compare_entity(
        ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "Vehicle Registration Number: KA05MH1234.")]
    )
    assert result.status == dc.STATUS_MISMATCH
    assert result.extracted_value == "KA05MH1234"


def test_registration_no_rc_document_is_unavailable():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "FIR", "TN01AB0001 mentioned here")])
    assert result.status == dc.STATUS_UNAVAILABLE
    assert "no RC document" in result.explanation


def test_registration_rc_document_with_empty_text_is_unavailable():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "")])
    assert result.status == dc.STATUS_UNAVAILABLE
    assert "no usable entity" in result.explanation


def test_registration_no_candidate_in_rc_text_is_unavailable():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "no identifiers in this text")])
    assert result.status == dc.STATUS_UNAVAILABLE


def test_registration_multiple_candidates_exactly_one_matching():
    result = dc._compare_entity(
        ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "TN01AB0001 and also KA05MH1234")]
    )
    assert result.status == dc.STATUS_MATCH
    assert result.extracted_value == "TN01AB0001"
    assert "other, non-matching candidates" in result.explanation


def test_registration_ambiguous_multiple_candidates_is_unavailable():
    """One strict-format candidate plus one weak keyword-context candidate,
    neither matching the reference - not explicit enough to call a mismatch."""
    text = "Registration No: ZZ9XYZ and also mentions KA05MH1234 separately"
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", text)])
    assert result.status == dc.STATUS_UNAVAILABLE
    assert "unverified-format" in result.explanation


def test_registration_multiple_strict_candidates_none_matching_is_mismatch():
    """Two independently well-formed candidates, neither matching - explicit
    enough evidence to call a mismatch rather than reporting unavailable."""
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "KA05MH1234 and DL3CAB5678")])
    assert result.status == dc.STATUS_MISMATCH
    assert "none matches" in result.explanation


def test_registration_missing_structured_reference_is_unavailable():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, None, [_doc("D1", "RC", "TN01AB0001")])
    assert result.status == dc.STATUS_UNAVAILABLE
    assert "no structured reference" in result.explanation


def test_registration_ocr_misread_matches_and_says_what_was_corrected():
    rc = _doc("D1", "RC", "Registration No: MHO2EM6629")
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "MH02EM6629", [rc])
    assert result.status == dc.STATUS_MATCH
    assert result.extracted_value == "MHO2EM6629"  # what the document actually reads
    assert "reads 'MHO2EM6629'" in result.explanation and "giving MH02EM6629" in result.explanation
    assert rc.Extracted_Text == "Registration No: MHO2EM6629"  # stored OCR text untouched


def test_registration_ocr_repair_does_not_hide_a_genuine_mismatch():
    rc = _doc("D1", "RC", "Registration No: MHO2EM6628")
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "MH02EM6629", [rc])
    assert result.status == dc.STATUS_MISMATCH
    assert result.extracted_value == "MHO2EM6628"
    assert "giving MH02EM6628" in result.explanation


def test_registration_unrepairable_misread_is_not_reported_as_a_match():
    rc = _doc("D1", "RC", "Registration No: KA05X12345")
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "KA05XI2345", [rc])
    assert result.status == dc.STATUS_MISMATCH


def test_registration_well_formed_match_explanation_is_unchanged():
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "Registration No: TN01AB0001")])
    assert result.explanation == "Registration number extracted from RC matches the insured record."


def test_registration_across_multiple_documents_of_same_type():
    docs = [_doc("D1", "RC", "TN01AB0001"), _doc("D2", "RC", "TN01AB0001")]
    result = dc._compare_entity(ee.REGISTRATION_NUMBER, "TN01AB0001", docs)
    assert result.status == dc.STATUS_MATCH


# ============================================================== A: pure algorithm - policy


def test_policy_exact_match():
    result = dc._compare_entity(
        ee.POLICY_NUMBER, "POL-000042", [_doc("D1", "Insurance Policy", "Policy Number: POL-000042.")]
    )
    assert result.status == dc.STATUS_MATCH
    assert result.matched_document_type == "Insurance Policy"


def test_policy_normalization_match():
    """Reuses entity_extraction.normalize_policy exactly as-is (Step
    5.8.13-A): case is normalized and internal whitespace is collapsed,
    but hyphens are preserved as part of this project's own POL-XXXXXX
    convention - so "pol-000042" matches "POL-000042", not a
    space-separated variant."""
    result = dc._compare_entity(ee.POLICY_NUMBER, "POL-000042", [_doc("D1", "Insurance Policy", "pol-000042")])
    assert result.status == dc.STATUS_MATCH


def test_policy_mismatch():
    result = dc._compare_entity(
        ee.POLICY_NUMBER, "POL-000042", [_doc("D1", "Insurance Policy", "Policy Number: POL-000099.")]
    )
    assert result.status == dc.STATUS_MISMATCH


def test_policy_no_insurance_policy_document_is_unavailable():
    result = dc._compare_entity(ee.POLICY_NUMBER, "POL-000042", [_doc("D1", "RC", "Policy Number: POL-000042")])
    assert result.status == dc.STATUS_UNAVAILABLE
    assert "no Insurance Policy document" in result.explanation


def test_policy_no_candidate_is_unavailable():
    result = dc._compare_entity(ee.POLICY_NUMBER, "POL-000042", [_doc("D1", "Insurance Policy", "no numbers here")])
    assert result.status == dc.STATUS_UNAVAILABLE


def test_policy_missing_structured_reference_is_unavailable():
    result = dc._compare_entity(ee.POLICY_NUMBER, None, [_doc("D1", "Insurance Policy", "POL-000042")])
    assert result.status == dc.STATUS_UNAVAILABLE
    assert "no structured reference" in result.explanation


def test_never_claims_fraud_or_uses_a_probability():
    result = dc._compare_entity(
        ee.REGISTRATION_NUMBER, "TN01AB0001", [_doc("D1", "RC", "Vehicle Registration Number: KA05MH1234.")]
    )
    assert result.status in (dc.STATUS_MATCH, dc.STATUS_MISMATCH, dc.STATUS_UNAVAILABLE)
    assert "fraud" not in result.explanation.lower()
    assert not hasattr(result, "confidence")


# ============================================================== B: real end-to-end (seed_data claim1)


def test_end_to_end_registration_match_via_analyze_endpoint(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Registration Certificate. Vehicle Registration Number: TEST-REG-0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 200, response.text
    reg = response.json()["consistency"]["registration"]
    assert reg["status"] == "MATCH"
    assert reg["structured_value"] == "TEST-REG-0001"
    assert reg["matched_document_type"] == "RC"


def test_end_to_end_registration_mismatch_via_analyze_endpoint(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Registration Certificate. Vehicle Registration Number: KA05MH1234."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    reg = response.json()["consistency"]["registration"]
    assert reg["status"] == "MISMATCH"
    assert reg["structured_value"] == "TEST-REG-0001"


def test_end_to_end_registration_unavailable_with_no_rc_document(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    reg = response.json()["consistency"]["registration"]
    assert reg["status"] == "UNAVAILABLE"


def test_end_to_end_policy_match_via_analyze_endpoint(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "insurance_policy",
        "policy.pdf",
        _text_pdf_bytes(["Insurance Policy Schedule. Policy Number: TEST-POLNUM-0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    pol = response.json()["consistency"]["policy"]
    assert pol["status"] == "MATCH"
    assert pol["structured_value"] == "TEST-POLNUM-0001"


def test_claim_level_endpoint_includes_top_level_consistency(client, customer1_token, officer_token, seed_data, analyzed_document_ids):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TEST-REG-0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze", headers=auth_headers(officer_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["consistency"]["registration"]["status"] == "MATCH"
    # Same claim-level result is also mirrored per document entry.
    doc_entry = next(d for d in body["documents"] if d["Document_ID"] == document_id)
    assert doc_entry["consistency"]["registration"]["status"] == "MATCH"


# ============================================================== Security / RBAC (unchanged)


def test_cross_customer_cannot_trigger_consistency_check_on_anothers_document(
    client, customer1_token, customer2_token, seed_data, analyzed_document_ids
):
    upload = _upload(
        client, customer1_token, seed_data["claim1"], "rc_book", "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TEST-REG-0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer2_token))
    assert response.status_code == 403


def test_existing_rbac_on_claim_level_endpoint_unchanged(client, customer1_token, surveyor_token, seed_data):
    for token in (customer1_token, surveyor_token):
        response = client.post(
            f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze", headers=auth_headers(token)
        )
        assert response.status_code == 403


# ============================================================== Human-in-the-loop safety


def test_consistency_check_does_not_touch_final_decision_or_audit(
    client, customer1_token, seed_data, analyzed_document_ids
):
    from app.db.session import SessionLocal
    from app.db_models.claim import Claim
    from app.db_models.claim_decision_audit import ClaimDecisionAudit

    upload = _upload(
        client, customer1_token, seed_data["claim1"], "rc_book", "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: KA05MH1234."]),  # mismatch on purpose
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    db = SessionLocal()
    try:
        before = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        final_decision_before, approved_amount_before = before.Final_Decision, before.Approved_Amount
        audit_before = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
    finally:
        db.close()

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.json()["consistency"]["registration"]["status"] == "MISMATCH"

    db = SessionLocal()
    try:
        after = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert after.Final_Decision == final_decision_before
        assert after.Approved_Amount == approved_amount_before
        audit_after = db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == seed_data["claim1"]).count()
        assert audit_after == audit_before
    finally:
        db.close()
