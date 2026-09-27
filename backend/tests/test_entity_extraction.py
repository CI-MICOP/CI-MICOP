"""Tests for Step 5.8.13-A - deterministic, regex-based entity extraction.

Per the Step 5.8.13 audit, the offline dataset's document text is Faker-
generated filler unrelated to any real claim fact, and the live dev
database currently has no document with genuinely populated
Extracted_Text. These tests therefore use carefully controlled strings
built from this project's own actual identifier formats (
vehicles.Registration_Number = "TN01AB0001" from seed_dev_data.py;
policies.Policy_Number = "POL-000001" style from the structured dataset -
see db_models/vehicle.py, db_models/policy.py) - never the synthetic
document-text dataset, and never a claim of real-document validation.
"""

import pytest

from app.services import entity_extraction as ee


# ---------------------------------------------------------------- A: registration extraction


def test_valid_project_style_registration_is_extracted_with_high_confidence():
    result = ee.extract_entities("Vehicle registration: TN01AB0001")
    assert result.status == "extracted"
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.value == "TN01AB0001"
    assert reg.normalized_value == "TN01AB0001"
    assert reg.source == "regex_strict_format"
    assert reg.confidence == 0.90


def test_registration_whitespace_variation_is_normalized():
    result = ee.extract_entities("TN 01 AB 0001")
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.value == "TN 01 AB 0001"
    assert reg.normalized_value == "TN01AB0001"


def test_registration_hyphen_variation_is_normalized():
    result = ee.extract_entities("TN-01-AB-0001")
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.normalized_value == "TN01AB0001"


def test_registration_lowercase_variation_is_normalized():
    result = ee.extract_entities("tn01ab0001")
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.value == "tn01ab0001"
    assert reg.normalized_value == "TN01AB0001"


def test_unrelated_numeric_text_produces_no_registration_candidate():
    result = ee.extract_entities("Invoice total: 4500.00, quantity 12, tax 18%.")
    assert result.status == "no_candidates"
    assert result.entities == []


def test_malformed_registration_without_label_produces_no_candidate():
    result = ee.extract_entities("random note TN1AB1 end of note")
    assert not any(e.entity_type == ee.REGISTRATION_NUMBER for e in result.entities)


def test_malformed_registration_with_label_returns_weak_candidate_not_high_confidence():
    result = ee.extract_entities("Registration No: TN1AB1")
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.source == "regex_keyword_context"
    assert reg.confidence < 0.5


def test_multiple_registration_candidates_are_all_returned():
    result = ee.extract_entities("Vehicle 1: TN01AB0001. Vehicle 2: KA05MH1234.")
    regs = [e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER]
    assert {r.normalized_value for r in regs} == {"TN01AB0001", "KA05MH1234"}


def test_registration_keyword_capture_does_not_bleed_into_next_word():
    result = ee.extract_entities("reg no TN-01-AB-0001 noted for the record")
    regs = [e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER]
    assert len(regs) == 1
    assert regs[0].normalized_value == "TN01AB0001"


def test_empty_text_is_unavailable():
    result = ee.extract_entities("")
    assert result.status == "unavailable"
    assert result.entities == []


def test_none_text_is_unavailable():
    result = ee.extract_entities(None)
    assert result.status == "unavailable"


def test_whitespace_only_text_is_unavailable():
    result = ee.extract_entities("   \n\t  ")
    assert result.status == "unavailable"


# ---------------------------------------------------------------- B: policy extraction


def test_valid_project_style_policy_number_is_extracted():
    result = ee.extract_entities("Policy Number: POL-000042")
    pol = next(e for e in result.entities if e.entity_type == ee.POLICY_NUMBER)
    assert pol.value == "POL-000042"
    assert pol.normalized_value == "POL-000042"
    assert pol.source == "regex_strict_format"
    assert pol.confidence == 0.70


def test_policy_number_whitespace_and_case_variation():
    result = ee.extract_entities("pol 000042")
    pol = next(e for e in result.entities if e.entity_type == ee.POLICY_NUMBER)
    assert pol.value == "pol 000042"
    assert pol.normalized_value == "POL 000042"


def test_unrelated_claim_number_is_not_treated_as_policy():
    result = ee.extract_entities("Claim Number: CLM-000001")
    assert not any(e.entity_type == ee.POLICY_NUMBER for e in result.entities)


def test_policy_label_without_digits_produces_no_candidate():
    result = ee.extract_entities("Policy Type: Comprehensive, no number given here")
    assert not any(e.entity_type == ee.POLICY_NUMBER for e in result.entities)


def test_dev_style_policy_label_is_a_weak_candidate():
    result = ee.extract_entities("Policy: DEV-POLICY-001")
    pol = next(e for e in result.entities if e.entity_type == ee.POLICY_NUMBER)
    assert pol.source == "regex_keyword_context"
    assert pol.normalized_value == "DEV-POLICY-001"


def test_multiple_policy_candidates_are_all_returned():
    result = ee.extract_entities("First policy POL-000001, second policy POL-000002.")
    pols = {e.normalized_value for e in result.entities if e.entity_type == ee.POLICY_NUMBER}
    assert pols == {"POL-000001", "POL-000002"}


def test_malformed_policy_value_without_label_is_ignored():
    result = ee.extract_entities("some code ABC123XYZ mentioned in passing")
    assert not any(e.entity_type == ee.POLICY_NUMBER for e in result.entities)


# ---------------------------------------------------------------- C: document-type context


def test_rc_document_boosts_registration_confidence():
    plain = ee.extract_entities("TN01AB0001", document_type=None)
    rc = ee.extract_entities("TN01AB0001", document_type="RC")
    plain_reg = next(e for e in plain.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    rc_reg = next(e for e in rc.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert rc_reg.confidence > plain_reg.confidence


def test_insurance_policy_document_boosts_policy_confidence():
    plain = ee.extract_entities("POL-000042", document_type=None)
    policy_doc = ee.extract_entities("POL-000042", document_type="Insurance Policy")
    plain_pol = next(e for e in plain.entities if e.entity_type == ee.POLICY_NUMBER)
    boosted_pol = next(e for e in policy_doc.entities if e.entity_type == ee.POLICY_NUMBER)
    assert boosted_pol.confidence > plain_pol.confidence


def test_fir_document_type_does_not_block_a_plausible_registration_candidate():
    result = ee.extract_entities("TN01AB0001", document_type="FIR")
    assert any(e.entity_type == ee.REGISTRATION_NUMBER for e in result.entities)


def test_survey_report_document_type_does_not_block_a_plausible_candidate():
    result = ee.extract_entities("Policy Number: POL-000042", document_type="Survey Report")
    assert any(e.entity_type == ee.POLICY_NUMBER for e in result.entities)


def test_unsupported_document_type_still_extracts_without_boost():
    result = ee.extract_entities("TN01AB0001", document_type="Accident Photos")
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.confidence == 0.90  # no boost applied for a non-strong-context type


# ---------------------------------------------------------------- OCR-confidence rule


def test_low_ocr_confidence_halves_every_candidate_confidence():
    high_ocr = ee.extract_entities("TN01AB0001", ocr_confidence=0.9)
    low_ocr = ee.extract_entities("TN01AB0001", ocr_confidence=0.1)
    high_reg = next(e for e in high_ocr.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    low_reg = next(e for e in low_ocr.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert low_reg.confidence == pytest.approx(high_reg.confidence * 0.5)


def test_missing_ocr_confidence_applies_no_adjustment():
    result = ee.extract_entities("TN01AB0001", ocr_confidence=None)
    reg = next(e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER)
    assert reg.confidence == 0.90


# ---------------------------------------------------------------- limitations honesty


def test_limitations_always_state_deterministic_not_nlp_not_validated():
    result = ee.extract_entities("TN01AB0001")
    assert any("not an nlp model" in msg.lower() for msg in result.limitations)
    assert any("not been validated" in msg.lower() for msg in result.limitations)


def test_does_not_compare_against_any_structured_value():
    """Step 5.8.13-A must never claim a match/mismatch verdict against the
    claim's own data - that is Step 5.8.13-B's job. "matches the format"
    (a pure pattern-shape description) is fine; a consistency verdict is not."""
    result = ee.extract_entities("TN01AB0001")
    for entity in result.entities:
        assert not hasattr(entity, "matches_claim")
        assert "mismatch" not in entity.reason.lower()
        assert "claim" not in entity.reason.lower()
        assert "consistent" not in entity.reason.lower()
