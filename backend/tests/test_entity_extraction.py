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


# ---------------------------------------------------------------- title line above the label


@pytest.mark.parametrize(
    "text",
    [
        "Insurance Policy\nPolicy No: DEV-POLICY-001",
        "Motor Insurance Policy\nPolicy Number: DEV-POLICY-001",
        "INSURANCE POLICY\nPOLICY NO. DEV-POLICY-001",
    ],
)
def test_policy_number_is_found_below_a_title_ending_in_policy(text):
    """A title such as "Insurance Policy" on the line above "Policy No: X"
    used to be matched as keyword + digit-less value ("Policy"), which was
    rejected only after the real label had been consumed - so nothing was
    extracted and the policy check reported UNAVAILABLE."""
    result = ee.extract_entities(text, document_type="Insurance Policy")
    values = [e.normalized_value for e in result.entities if e.entity_type == ee.POLICY_NUMBER]
    assert values == ["DEV-POLICY-001"]


def test_registration_label_below_a_registration_title_is_found_for_non_standard_formats():
    # Not the strict Indian format, so only the keyword fallback can find it.
    result = ee.extract_entities("Vehicle Registration\nRegistration No: KA05X12345", document_type="RC")
    values = [e.normalized_value for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER]
    assert values == ["KA05X12345"]


def test_words_after_a_keyword_are_still_never_taken_as_a_value():
    result = ee.extract_entities("Insurance Policy\nPolicy Type: Comprehensive\nRegistration Certificate")
    assert result.entities == []


# ---------------------------------------------------------------- OCR O/0 and I/1 repair (registration only)


def _registration(text, document_type="RC"):
    result = ee.extract_entities(text, document_type=document_type)
    return [e for e in result.entities if e.entity_type == ee.REGISTRATION_NUMBER]


def test_o_read_in_a_digit_position_is_repaired_to_zero():
    correction = ee.correct_registration_ocr("MHO2EM6629")
    assert correction.corrected == "MH02EM6629"
    assert correction.changes == ["character 3 'O' read as the digit '0'"]


def test_a_well_formed_registration_is_left_unchanged():
    assert ee.correct_registration_ocr("MH02EM6629") is None
    [reg] = _registration("Registration No: MH02EM6629")
    assert (reg.value, reg.normalized_value, reg.source, reg.correction) == (
        "MH02EM6629", "MH02EM6629", "regex_strict_format", None)


@pytest.mark.parametrize("written", ["mho2em6629", "  MHO2EM6629  ", "MH-O2-EM-6629", "mh-o2-em-6629"])
def test_case_whitespace_and_hyphen_variants_of_a_misread_label_value_normalize_the_same(written):
    [reg] = _registration(f"Vehicle Registration No: {written}")
    assert reg.normalized_value == "MH02EM6629"
    assert reg.value == written.strip()  # exactly as read


def test_i_is_repaired_to_one_only_in_digit_positions():
    assert ee.correct_registration_ocr("KA03NFI307").corrected == "KA03NF1307"  # 4-digit number
    assert ee.correct_registration_ocr("TNI9BX4417").corrected == "TN19BX4417"  # RTO code
    # A 1 inside the letter series is never turned into an I (series never use I/O).
    assert ee.correct_registration_ocr("TN09B1X4417") is None
    # No state code contains I, so a leading 1 is not "corrected" into one.
    assert ee.correct_registration_ocr("1N09BX4417") is None


def test_zero_in_the_state_code_is_repaired_only_into_a_real_state_code():
    assert ee.correct_registration_ocr("0D02AB1234").corrected == "OD02AB1234"
    assert ee.correct_registration_ocr("XXO2EM6629") is None  # XX is not a state code


@pytest.mark.parametrize(
    "value",
    [
        "KA05X12345",   # 5-digit tail: the 1 could belong to the series or the number
        "TN09BXO4417",  # confusable character where the series meets the number
        "MHOOEMOOOO",   # would need more than two changes
        "MHO2",         # too short to be a registration
        "POLICY01",     # not registration-shaped
    ],
)
def test_ambiguous_or_invalid_values_are_not_turned_into_valid_registrations(value):
    assert ee.correct_registration_ocr(value) is None


def test_ambiguous_label_value_is_kept_as_read_and_stays_weak():
    [reg] = _registration("Registration No: KA05X12345")
    assert (reg.normalized_value, reg.source, reg.correction) == ("KA05X12345", "regex_keyword_context", None)


def test_repair_is_applied_only_to_values_read_as_registrations():
    # Unlabelled text with O/0 or I/1 lookalikes yields no registration at all.
    assert _registration("Total: Rs. 1O,500 paid at counter MHO2EM6629 ref") == []
    # Policy numbers are never touched by registration repair.
    result = ee.extract_entities("Policy No: POL-92600I", document_type="Insurance Policy")
    assert [e.normalized_value for e in result.entities if e.entity_type == ee.POLICY_NUMBER] == ["POL-92600I"]


def test_repaired_candidate_keeps_the_ocr_text_and_explains_the_change():
    text = "Vehicle Registration No: MHO2EM6629"
    [reg] = _registration(text, document_type="Repair Estimate")
    assert reg.value == "MHO2EM6629"
    assert reg.normalized_value == "MH02EM6629"
    assert reg.source == "regex_keyword_context"  # still weaker evidence than a well-formed value
    assert reg.confidence < 0.5
    assert "reads 'MHO2EM6629'" in reg.correction and "'O' read as the digit '0'" in reg.correction
    assert text == "Vehicle Registration No: MHO2EM6629"
