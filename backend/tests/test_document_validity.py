"""Distinct verification outcomes, RC / licence validity and policy cover.

Database-free: documents are in-memory records carrying the text the
application keeps (Extracted_Text), and the officer endpoint is called with
the CRUD layer replaced by in-memory lookups.
"""

from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.routers import officer
from app.services import accident_consistency, claim_copy_retention, document_consistency, document_validity
from app.services import verification_outcome as vo

ACCIDENT = date(2026, 9, 18)
RC_TEXT = "Registration No: KL07CQ2219\nRegn. Date: 20/07/2011\nRegn. Validity: 19/07/2026\nOwner Name: Arjun Nair"
LICENCE_TEXT = ("Licence No: KL99 2002 0000004\nName: Arjun Nair\nDate of Birth: 30/01/1979\n"
                "Date of Issue: 10/03/2002\nRenewed On: 01/03/2022\nValid Till (Non-Transport): 28/02/2032\n"
                "Class of Vehicle: LMV, MCWG")


def doc(doc_type, text, doc_id=None):
    kept = text if claim_copy_retention.is_copy_retained(doc_type) else claim_copy_retention.verification_record(text)
    return SimpleNamespace(Document_ID=doc_id or f"DOC-{doc_type[:3]}", Document_Type=doc_type, Extracted_Text=kept,
                           OCR_Confidence_Score=Decimal("1.0000") if kept else Decimal("0"))


# ---------------------------------------------------------------- outcomes on the existing checks


def test_registration_outcomes_are_distinct():
    compare = document_consistency._compare_entity
    reg = "registration_number"
    assert compare(reg, "KL07CQ2219", []).outcome == vo.NOT_SUBMITTED
    assert compare(reg, "KL07CQ2219", [doc("RC", "")]).outcome == vo.VERIFICATION_UNAVAILABLE  # no text at all
    assert compare(reg, "KL07CQ2219", [doc("FIR", "nothing useful here", "D1")]).outcome == vo.NOT_SUBMITTED
    assert compare(reg, None, [doc("RC", RC_TEXT)]).outcome == vo.REFERENCE_UNAVAILABLE
    assert compare(reg, "KL07CQ2219", [doc("RC", RC_TEXT)]).outcome == vo.VERIFIED
    assert compare(reg, "KL07CQ2218", [doc("RC", RC_TEXT)]).outcome == vo.MISMATCH


def test_a_missing_reference_is_never_a_mismatch_and_unreadable_text_is_never_a_mismatch():
    compare = document_consistency._compare_entity
    missing_ref = compare("registration_number", None, [doc("RC", RC_TEXT)])
    unreadable = compare("registration_number", "KL07CQ2219", [doc("RC", "")])
    assert missing_ref.status == unreadable.status == document_consistency.STATUS_UNAVAILABLE  # unchanged status
    assert {missing_ref.outcome, unreadable.outcome} == {vo.REFERENCE_UNAVAILABLE, vo.VERIFICATION_UNAVAILABLE}


def test_fir_outcomes_are_distinct():
    fir = accident_consistency.compare_fir_number
    assert fir("0418/2026", []).outcome == vo.NOT_SUBMITTED
    assert fir("0418/2026", [doc("FIR", "")]).outcome == vo.VERIFICATION_UNAVAILABLE
    assert fir("0418/2026", [doc("FIR", "An FIR was lodged.")]).outcome == vo.INCONCLUSIVE
    assert fir(None, [doc("FIR", "FIR No: 0418/2026")]).outcome == vo.REFERENCE_UNAVAILABLE
    assert fir("0418/2026", [doc("FIR", "FIR-No: 0418/2026")]).outcome == vo.VERIFIED
    assert fir("0418/2026", [doc("FIR", "FIR No: 0419/2026")]).outcome == vo.MISMATCH
    assert fir("0418/2026", [doc("FIR", "FIR No: 1/2026 and FIR No: 2/2026")]).outcome == vo.INCONCLUSIVE


# ---------------------------------------------------------------- RC validity


def _registration(rc_documents, record="KL07CQ2219"):
    return document_consistency._compare_entity("registration_number", record, rc_documents)


def test_rc_valid_on_the_accident_date():
    docs = [doc("RC", RC_TEXT)]
    result = document_validity.check_rc_validity(docs, date(2026, 7, 19), _registration(docs))
    assert result.outcome == vo.VERIFIED and result.evidence["valid_upto"] == "2026-07-19"


def test_rc_expired_before_the_accident():
    docs = [doc("RC", RC_TEXT)]
    result = document_validity.check_rc_validity(docs, ACCIDENT, _registration(docs))
    assert result.outcome == vo.INVALID_OR_EXPIRED
    assert "2026-07-19" in result.explanation


def test_rc_without_a_validity_date_is_inconclusive_not_valid_or_expired():
    docs = [doc("RC", "Registration No: KL07CQ2219\nRegn. Date: 20/07/2011")]
    result = document_validity.check_rc_validity(docs, ACCIDENT, _registration(docs))
    assert result.outcome == vo.INCONCLUSIVE
    assert "not assumed valid or expired" in result.explanation


def test_rc_not_submitted_unreadable_and_mismatch():
    assert document_validity.check_rc_validity([], ACCIDENT).outcome == vo.NOT_SUBMITTED
    unread = [doc("RC", "")]
    assert document_validity.check_rc_validity(unread, ACCIDENT, _registration(unread)).outcome == vo.VERIFICATION_UNAVAILABLE
    docs = [doc("RC", RC_TEXT)]
    mismatch = document_validity.check_rc_validity(docs, date(2026, 1, 1), _registration(docs, "KL07CQ2218"))
    assert mismatch.outcome == vo.MISMATCH  # the dates describe another vehicle


def test_rc_reference_is_stated_unavailable_and_accident_date_missing():
    docs = [doc("RC", RC_TEXT)]
    result = document_validity.check_rc_validity(docs, date(2026, 1, 1), _registration(docs))
    assert document_validity.RC_NO_REFERENCE in result.limitations
    assert document_validity.check_rc_validity(docs, None, _registration(docs)).outcome == vo.REFERENCE_UNAVAILABLE


def test_renewed_rc_uses_the_latest_validity_date():
    text = RC_TEXT + "\nRenewal: Registration Valid Upto: 19/07/2031"
    docs = [doc("RC", text)]
    assert document_validity.check_rc_validity(docs, ACCIDENT, _registration(docs)).outcome == vo.VERIFIED


# ---------------------------------------------------------------- licence


def _licence(text, accident=ACCIDENT, vehicle_type="Private Car", reference=None):
    return document_validity.check_licence([doc("Driving Licence", text)], accident, vehicle_type, reference)


def test_licence_valid_and_right_class():
    number, validity, vehicle_class = _licence(LICENCE_TEXT)
    assert validity.outcome == vo.VERIFIED and validity.evidence["valid_to"] == "2032-02-28"
    assert vehicle_class.outcome == vo.VERIFIED
    assert number.outcome == vo.REFERENCE_UNAVAILABLE  # read, but no insurer licence record exists


def test_licence_expired_before_the_accident():
    _, validity, _ = _licence(LICENCE_TEXT.replace("28/02/2032", "31/05/2026"))
    assert validity.outcome == vo.INVALID_OR_EXPIRED


def test_licence_missing_or_impossible_validity_date_is_inconclusive():
    _, missing, _ = _licence("Licence No: KL99 2002 0000004\nClass of Vehicle: LMV")
    _, impossible, _ = _licence("Valid Till: 31/02/2032\nClass of Vehicle: LMV")
    assert missing.outcome == impossible.outcome == vo.INCONCLUSIVE
    assert "31/02/2032" in impossible.explanation


def test_licence_class_mismatch_and_undetermined_class():
    _, _, wrong = _licence(LICENCE_TEXT.replace("LMV, MCWG", "MCWG"))
    assert wrong.outcome == vo.INVALID_OR_EXPIRED and "LMV" in wrong.explanation
    _, _, goods = _licence(LICENCE_TEXT, vehicle_type="Goods Carrier")
    assert goods.outcome == vo.INCONCLUSIVE  # class rule for this type is not modelled
    _, _, no_class = _licence("Valid Till: 28/02/2032")
    assert no_class.outcome == vo.INCONCLUSIVE


def test_licence_numbers_match_and_mismatch_when_a_reference_is_given():
    assert _licence(LICENCE_TEXT, reference="KL9920020000004")[0].outcome == vo.VERIFIED
    assert _licence(LICENCE_TEXT, reference="KL99 2002 0000009")[0].outcome == vo.MISMATCH


def test_licence_not_submitted_and_unreadable():
    assert all(c.outcome == vo.NOT_SUBMITTED for c in document_validity.check_licence([], ACCIDENT, "Private Car"))
    assert all(c.outcome == vo.VERIFICATION_UNAVAILABLE for c in _licence(""))


def test_licence_class_is_never_inferred_from_the_number():
    _, _, vehicle_class = _licence("Licence No: KL99 2002 0000004\nValid Till: 28/02/2032")
    assert vehicle_class.outcome == vo.INCONCLUSIVE


def test_kept_record_holds_the_validity_fields_but_not_personal_details():
    record = claim_copy_retention.verification_record(LICENCE_TEXT)
    assert "28/02/2032" in record and "LMV, MCWG" in record and "KL99 2002 0000004" in record
    for personal in ("Arjun Nair", "30/01/1979", "10/03/2002"):
        assert personal not in record


# ---------------------------------------------------------------- policy cover


def _policy(start=date(2025, 8, 1), end=date(2026, 7, 31), coverage="Own Damage + TP"):
    return SimpleNamespace(Policy_Start_Date=start, Policy_End_Date=end, Coverage_Type=coverage)


def test_policy_cover_outcomes():
    check = document_validity.check_policy
    assert check(_policy(), date(2026, 1, 1), "Own Damage").outcome == vo.VERIFIED
    assert check(_policy(), date(2026, 9, 2), "Own Damage").outcome == vo.INVALID_OR_EXPIRED
    assert check(None, date(2026, 1, 1), "Own Damage").outcome == vo.REFERENCE_UNAVAILABLE
    assert check(_policy(), None, "Own Damage").outcome == vo.REFERENCE_UNAVAILABLE
    assert check(_policy(end=None), date(2026, 1, 1), "Own Damage").outcome == vo.INCONCLUSIVE
    result = check(_policy(), date(2026, 9, 2), "Own Damage")
    assert result.evidence == {"accident_date": "2026-09-02", "policy_start": "2025-08-01", "policy_end": "2026-07-31",
                               "coverage_type": "Own Damage + TP", "claim_type": "Own Damage"}


def test_policy_existence_is_not_cover_for_an_excluded_section():
    tp_only = _policy(coverage="Third Party Only")
    assert document_validity.check_policy(tp_only, date(2026, 1, 1), "Own Damage").outcome == vo.INVALID_OR_EXPIRED
    assert document_validity.check_policy(tp_only, date(2026, 1, 1), "Third Party").outcome == vo.VERIFIED
    unclear = document_validity.check_policy(_policy(coverage="Standard"), date(2026, 1, 1), "Own Damage")
    assert unclear.outcome == vo.VERIFIED and any("only the period" in line for line in unclear.limitations)


# ---------------------------------------------------------------- officer endpoint (no database)


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *_):
        return self

    def order_by(self, *_):
        return self

    def first(self):
        return self.row


def test_officer_consistency_response_carries_outcomes_and_validity(monkeypatch):
    claim = SimpleNamespace(Claim_ID="CLM-1", Vehicle_ID="VEH-1", Policy_ID="POL-1", Claim_Type="Own Damage")
    documents = [doc("RC", RC_TEXT, "D-RC"), doc("Driving Licence", LICENCE_TEXT.replace("LMV, MCWG", "MCWG"), "D-DL")]
    accident = SimpleNamespace(Accident_Date=ACCIDENT, Accident_Time=time(2, 0), FIR_Number=None)
    vehicle = SimpleNamespace(Registration_Number="KL07CQ2219", Vehicle_Type="Private Car")
    policy = SimpleNamespace(Policy_Number="POL-926008", Policy_Start_Date=date(2026, 7, 7),
                             Policy_End_Date=date(2027, 7, 6), Coverage_Type="Own Damage + TP")
    db = SimpleNamespace(query=lambda model: _Query(accident))
    for module in (officer, document_validity, document_consistency, accident_consistency):
        if hasattr(module, "crud_claim"):
            monkeypatch.setattr(module.crud_claim, "get", lambda db, cid: claim)
        if hasattr(module, "crud_document"):
            monkeypatch.setattr(module.crud_document, "list_by_claim", lambda db, cid: documents)
        if hasattr(module, "crud_vehicle"):
            monkeypatch.setattr(module.crud_vehicle, "get", lambda db, vid: vehicle)
        if hasattr(module, "crud_policy"):
            monkeypatch.setattr(module.crud_policy, "get", lambda db, pid: policy)

    body = officer.analyze_claim_semantic_consistency("CLM-1", current_user=None, db=db).model_dump()

    assert body["deterministic"]["registration"]["outcome"] == vo.VERIFIED
    assert body["deterministic"]["policy"]["outcome"] == vo.NOT_SUBMITTED
    assert body["accident_details"]["fir_number"]["outcome"] == vo.NOT_SUBMITTED
    validity = body["validity"]
    assert validity["rc_validity"]["outcome"] == vo.INVALID_OR_EXPIRED
    assert validity["licence_validity"]["outcome"] == vo.VERIFIED
    assert validity["licence_class"]["outcome"] == vo.INVALID_OR_EXPIRED
    assert validity["licence_number"]["outcome"] == vo.REFERENCE_UNAVAILABLE
    assert validity["policy_cover"]["outcome"] == vo.VERIFIED
    assert validity["policy_cover"]["evidence"]["accident_date"] == "2026-09-18"
    assert set(validity) == {"rc_validity", "licence_number", "licence_validity", "licence_class", "policy_cover"}


@pytest.mark.parametrize("outcome", vo.ALL_OUTCOMES)
def test_every_outcome_is_a_plain_string_code(outcome):
    assert outcome.isupper() and " " not in outcome


# ---------------------------------------------------------------- FIR label: no false positives


@pytest.mark.parametrize("text", [
    "FIR Notes: the complainant arrived late.",
    "See FIR - Nominee details attached.",
    "FIR-registered at Guindy police station on 20/08/2026.",
    "Firm No: 12345 (garage registration)",
    "FIR No: pending",
])
def test_arbitrary_text_is_not_read_as_an_fir_number(text):
    assert accident_consistency.extract_fir_numbers(text) == []


@pytest.mark.parametrize("text", ["FIR No: 0418/2026", "FIR-No: 0418/2026", "FIR - No. 0418/2026", "F.I.R. No. 0418/2026",
                                  "FIR Number: 0418/2026", "FIR NO.:0418/2026"])
def test_fir_label_variants_are_read(text):
    assert accident_consistency.extract_fir_numbers(text) == ["0418/2026"]
