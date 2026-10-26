"""Tests for Step 5.8.16 - deterministic accident-detail consistency
(services/accident_consistency.py, `accident_details` in
POST /officer/claims/{id}/documents/semantic-consistency).

Layers, per project convention:
  A. Pure extraction/comparison tests and the controlled corpus
     (tests/accident_consistency_corpus.py).
  B. Real end-to-end tests against PostgreSQL and the real API, uploading
     genuine PyMuPDF-built PDFs through the real upload + analyze pipeline.
"""

from collections import Counter
from datetime import date, time
from types import SimpleNamespace

import pytest

from app.db.session import SessionLocal
from app.db_models.accident import Accident
from app.services import accident_consistency as ac
from tests.accident_consistency_corpus import (
    CORPUS,
    MATCH,
    MISMATCH,
    RECORD_DATE,
    RECORD_FIR,
    RECORD_TIME,
    TIME_CORPUS,
    UNAVAILABLE,
)
from tests.conftest import auth_headers
from tests.test_document_analysis import _text_pdf_bytes, _upload, analyzed_document_ids  # noqa: F401


def _doc(doc_id, doc_type, text):
    return SimpleNamespace(Document_ID=doc_id, Document_Type=doc_type, Extracted_Text=text)


def _case_documents(case):
    documents = [_doc("D-FIR", "FIR", case.fir_text)]
    if case.survey_text is not None:
        documents.append(_doc("D-SR", "Survey Report", case.survey_text))
    return documents


def _run(case):
    if case.check == "date":
        return ac.compare_accident_date(RECORD_DATE, _case_documents(case))
    return ac.compare_fir_number(RECORD_FIR, _case_documents(case))


# ============================================================== A: extraction and comparison


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("20/08/2026", date(2026, 8, 20)),
        ("20-08-2026", date(2026, 8, 20)),
        ("20.08.2026", date(2026, 8, 20)),
        ("2026-08-20", date(2026, 8, 20)),
        ("20 August 2026", date(2026, 8, 20)),
        ("20th Aug 2026", date(2026, 8, 20)),
        ("August 20, 2026", date(2026, 8, 20)),
        ("Sept 3, 2026", date(2026, 9, 3)),
    ],
)
def test_parse_date_supported_shapes_are_day_first(raw, expected):
    assert ac.parse_date(raw) == expected


def test_parse_date_rejects_impossible_dates_instead_of_guessing():
    assert ac.parse_date("31/02/2026") is None
    assert ac.parse_date("08/20/2026") is None  # month-first is not supported


def test_only_labelled_dates_are_extracted():
    text = "Report printed 25/08/2026. Date of accident: 20/08/2026. Inspection on 23/08/2026."
    assert [parsed for _, parsed in ac.extract_accident_dates(text)] == [date(2026, 8, 20)]


def test_fir_number_needs_an_explicit_number_label_and_a_digit():
    assert ac.extract_fir_numbers("An FIR was lodged. FIR copy attached.") == []
    assert ac.extract_fir_numbers("FIR No: ABC") == []
    assert ac.extract_fir_numbers("F.I.R. No. 45/2026") == ["45/2026"]


def test_missing_documents_and_missing_record_are_unavailable_not_mismatch():
    assert ac.compare_fir_number(RECORD_FIR, []).status == UNAVAILABLE
    assert ac.compare_accident_date(RECORD_DATE, [_doc("D1", "RC", "Date of accident: 21/08/2026")]).status == UNAVAILABLE
    assert ac.compare_fir_number(None, [_doc("D1", "FIR", "FIR No: 1/2026")]).status == UNAVAILABLE
    assert ac.compare_accident_date(None, [_doc("D1", "FIR", "Date of accident: 20/08/2026")]).status == UNAVAILABLE


def test_mismatch_explanation_names_every_disagreeing_document_and_never_says_fraud():
    documents = [_doc("D1", "FIR", "Date of accident: 21/08/2026"), _doc("D2", "Survey Report", "Date of accident: 22/08/2026")]
    result = ac.compare_accident_date(RECORD_DATE, documents)
    assert result.status == MISMATCH
    assert "D1 states 2026-08-21" in result.explanation
    assert "D2 states 2026-08-22" in result.explanation
    assert "fraud" not in result.explanation.lower()


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case.case_id)
def test_check_returns_recorded_result_for_corpus_case(case):
    result = _run(case)
    assert result.status == case.observed, f"{case.case_id} ({case.description}): {result.explanation}"
    assert "fraud" not in result.explanation.lower()


def test_corpus_summary_matches_validation_report():
    """The counts quoted in ACCIDENT_DETAIL_CONSISTENCY.md. If this fails,
    the corpus or the checks changed and the report must be updated."""
    outcomes = Counter((case.ideal, case.observed) for case in CORPUS)
    # Step 5.8.16: 20 cases, 14 agreeing, 1 false mismatch (F07). Step 5.8.17
    # fixed A09/A12/F07 and added held-out cases A13-A15, F09-F10. The FIR
    # label-variant cases F11-F15 were added with the "FIR-No" fix.
    assert len(CORPUS) == 30
    assert sum(n for (ideal, observed), n in outcomes.items() if ideal == observed) == 27
    assert outcomes[(MATCH, UNAVAILABLE)] == 3  # missed - reported as unavailable (A10, A11, F08)
    assert outcomes[(MATCH, MISMATCH)] == 0  # false mismatch - none since Step 5.8.17
    assert outcomes[(MISMATCH, MATCH)] == 0  # false match - never observed


# ============================================================== accident time (Step 5.8.17)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("18:30", time(18, 30)),
        ("18.30", time(18, 30)),
        ("6:30 PM", time(18, 30)),
        ("6.30 p.m.", time(18, 30)),
        ("6 PM", time(18, 0)),
        ("12:15 AM", time(0, 15)),
        ("12:15 PM", time(12, 15)),
        ("1845 hrs", time(18, 45)),
    ],
)
def test_parse_time_supported_shapes(raw, expected):
    assert ac.parse_time(raw) == expected


def test_parse_time_rejects_impossible_times():
    assert ac.parse_time("25:00") is None
    assert ac.parse_time("13:00 PM") is None


def test_time_tolerance_boundary_and_midnight_wrap():
    documents = [_doc("D1", "FIR", "Time of accident: 19:00")]
    assert ac.compare_accident_time(time(18, 30), documents).status == MATCH  # exactly 30 minutes
    assert ac.compare_accident_time(time(18, 29), documents).status == MISMATCH  # 31 minutes
    late = [_doc("D1", "FIR", "Time of accident: 23:50")]
    assert ac.compare_accident_time(time(0, 10), late).status == MATCH  # 20 minutes across midnight


def test_recorded_midnight_is_treated_as_no_time_on_record():
    result = ac.compare_accident_time(time(0, 0), [_doc("D1", "FIR", "Time of accident: 18:30")])
    assert result.status == UNAVAILABLE
    assert "00:00 is stored when the time is left blank" in result.explanation


@pytest.mark.parametrize("case", TIME_CORPUS, ids=lambda case: case.case_id)
def test_time_check_returns_recorded_result_for_corpus_case(case):
    result = ac.compare_accident_time(RECORD_TIME, _case_documents(case))
    assert result.status == case.observed, f"{case.case_id} ({case.description}): {result.explanation}"
    assert "fraud" not in result.explanation.lower()


def test_time_corpus_summary_matches_validation_report():
    outcomes = Counter((case.ideal, case.observed) for case in TIME_CORPUS)
    assert len(TIME_CORPUS) == 11
    assert sum(n for (ideal, observed), n in outcomes.items() if ideal == observed) == 10
    assert outcomes[(MATCH, UNAVAILABLE)] == 1  # missed - T09 "at around"
    assert outcomes[(MATCH, MISMATCH)] == 0
    assert outcomes[(MISMATCH, MATCH)] == 0


# ============================================================== B: real end-to-end


@pytest.fixture()
def claim1_accident(seed_data):
    db = SessionLocal()
    accident_id = "TEST-ACC-5816"
    db.add(
        Accident(
            Accident_ID=accident_id, Claim_ID=seed_data["claim1"], Accident_Date=RECORD_DATE, Accident_Time=time(18, 30),
            Accident_Location="Anna Salai, Chennai", Accident_City="Chennai", Accident_State="Tamil Nadu",
            Accident_Pincode="600002", Accident_Type="Collision", Accident_Description="Test accident record.",
            Weather_Condition="Clear", Road_Condition="Dry", Road_Type_Code="URBAN", Police_Report_Available=True,
            FIR_Number=RECORD_FIR, Third_Party_Involved=False, Injury_Reported=False, Witness_Available=False,
        )
    )
    db.commit()
    db.close()
    yield accident_id
    db = SessionLocal()
    db.query(Accident).filter(Accident.Accident_ID == accident_id).delete()
    db.commit()
    db.close()


def _upload_and_analyze(client, token, claim_id, document_type, filename, text, created):
    response = _upload(client, token, claim_id, document_type, filename, _text_pdf_bytes([text]))
    assert response.status_code == 201, response.text
    document_id = response.json()["Document_ID"]
    created.append(document_id)
    analyze = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(token))
    assert analyze.status_code == 200, analyze.text
    return document_id


def _check(client, officer_token, claim_id):
    response = client.post(
        f"/api/v1/officer/claims/{claim_id}/documents/semantic-consistency", headers=auth_headers(officer_token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_end_to_end_fir_match_and_survey_date_mismatch(
    client, customer1_token, officer_token, seed_data, claim1_accident, analyzed_document_ids
):
    fir_id = _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        "FIR No: 123/2026. Date of accident: 20/08/2026.", analyzed_document_ids,
    )
    survey_id = _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        "Date of accident: 22/08/2026. Front bumper damaged.", analyzed_document_ids,
    )

    details = _check(client, officer_token, seed_data["claim1"])["accident_details"]

    assert details["fir_number"]["status"] == "MATCH"
    assert details["fir_number"]["structured_value"] == "123/2026"
    assert details["fir_number"]["matched_document_id"] == fir_id

    assert details["accident_date"]["status"] == "MISMATCH"
    assert details["accident_date"]["structured_value"] == "2026-08-20"
    assert details["accident_date"]["matched_document_id"] == survey_id
    assert "2026-08-22" in details["accident_date"]["explanation"]


def test_end_to_end_accident_date_match(client, customer1_token, officer_token, seed_data, claim1_accident, analyzed_document_ids):
    _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        "The accident occurred on 20 August 2026 near Anna Salai.", analyzed_document_ids,
    )
    details = _check(client, officer_token, seed_data["claim1"])["accident_details"]
    assert details["accident_date"]["status"] == "MATCH"
    assert details["fir_number"]["status"] == "UNAVAILABLE"  # no labelled FIR number in the text


def test_end_to_end_without_accident_record_is_unavailable(client, officer_token, seed_data):
    details = _check(client, officer_token, seed_data["claim1"])["accident_details"]
    assert details["accident_date"]["status"] == "UNAVAILABLE"
    assert details["fir_number"]["status"] == "UNAVAILABLE"
    assert details["accident_time"]["status"] == "UNAVAILABLE"
    assert "no accident record" in details["accident_date"]["explanation"]


def test_end_to_end_accident_time_match_and_mismatch(
    client, customer1_token, officer_token, seed_data, claim1_accident, analyzed_document_ids
):
    fir_id = _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        "Time of accident: 6:30 PM.", analyzed_document_ids,
    )
    details = _check(client, officer_token, seed_data["claim1"])["accident_details"]
    assert details["accident_time"]["status"] == "MATCH"
    assert details["accident_time"]["structured_value"] == "18:30"
    assert details["accident_time"]["matched_document_id"] == fir_id

    _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        "Time of accident: 21:00.", analyzed_document_ids,
    )
    details = _check(client, officer_token, seed_data["claim1"])["accident_details"]
    assert details["accident_time"]["status"] == "MISMATCH"
    assert "21:00" in details["accident_time"]["explanation"]


def test_end_to_end_existing_registration_and_narrative_results_are_unchanged(
    client, customer1_token, officer_token, seed_data, claim1_accident, analyzed_document_ids
):
    """Adding accident_details must not alter the existing fields."""
    _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf",
        "FIR No: 999/2026. Accident occurred near Gandhipuram.", analyzed_document_ids,
    )
    _upload_and_analyze(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf",
        "Vehicle was involved in an accident near Peelamedu.", analyzed_document_ids,
    )
    body = _check(client, officer_token, seed_data["claim1"])
    assert body["narrative"]["relationship"] == "CONTRADICTION"
    assert set(body["deterministic"]) == {"registration", "policy"}
    assert body["accident_details"]["fir_number"]["status"] == "MISMATCH"
