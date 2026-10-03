"""Step 5.8.13-E: validation of the Step 5.8.13-C narrative location-
consistency research prototype against a controlled multi-document corpus
(tests/semantic_validation_corpus.py).

These tests pin the prototype's CURRENT behaviour on every corpus case -
including the cases where it disagrees with the ideal human label. They do
not assert that the prototype is correct; the agreement summary is
reported in docs/project_documentation/SEMANTIC_CONSISTENCY_VALIDATION.md.
If the prototype is ever changed, these tests show exactly which recorded
results moved, and the corpus `observed` labels and that document must be
updated together.

Two layers, per project convention (mirrors test_semantic_consistency.py):
  A. Every corpus case against compare_narrative() directly.
  B. A subset through the real PostgreSQL + API pipeline, uploading genuine
     PyMuPDF-built PDFs, to confirm native PDF text extraction does not
     change the result.
"""

from collections import Counter
from datetime import date
from types import SimpleNamespace

import pytest

from app.services import semantic_consistency as sc
from tests.conftest import auth_headers
from tests.semantic_validation_corpus import (
    CONSISTENT,
    CONTRADICTION,
    CORPUS,
    END_TO_END_CASE_IDS,
    INCONCLUSIVE,
)
from tests.test_document_analysis import _text_pdf_bytes, _upload, analyzed_document_ids  # noqa: F401

CASES_BY_ID = {case.case_id: case for case in CORPUS}


def _doc(doc_id, doc_type, text):
    return SimpleNamespace(Document_ID=doc_id, Document_Type=doc_type, Extracted_Text=text, Document_Submitted_Date=date(2026, 1, 1))


# ============================================================== corpus integrity


def test_corpus_case_ids_are_unique_and_labels_are_valid():
    ids = [case.case_id for case in CORPUS]
    assert len(ids) == len(set(ids))
    valid = {CONSISTENT, CONTRADICTION, INCONCLUSIVE}
    for case in CORPUS:
        assert case.ideal in valid, case.case_id
        assert case.observed in valid, case.case_id
    assert set(END_TO_END_CASE_IDS) <= set(CASES_BY_ID)


# ============================================================== A: every case, pure algorithm


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case.case_id)
def test_prototype_returns_recorded_result_for_corpus_case(case):
    result = sc.compare_narrative(_doc("A", "FIR", case.fir_text), _doc("B", "Survey Report", case.survey_text))
    assert result.relationship == case.observed, f"{case.case_id} ({case.category}): {result.explanation}"
    assert result.confidence is None
    assert "fraud" not in result.explanation.lower()


def test_agreement_summary_matches_validation_report():
    """The counts quoted in SEMANTIC_CONSISTENCY_VALIDATION.md. If this
    fails, the corpus or the prototype changed and the report must be
    updated to match."""
    outcomes = Counter((case.ideal, case.observed) for case in CORPUS)
    assert len(CORPUS) == 18
    assert sum(n for (ideal, observed), n in outcomes.items() if ideal == observed) == 8
    assert outcomes[(CONSISTENT, CONTRADICTION)] == 3  # false contradiction
    assert outcomes[(CONSISTENT, INCONCLUSIVE)] == 6  # missed agreement
    assert outcomes[(CONTRADICTION, INCONCLUSIVE)] == 1  # missed contradiction
    assert outcomes[(CONTRADICTION, CONSISTENT)] == 0  # false agreement - never observed


# ============================================================== B: real end-to-end subset


@pytest.mark.parametrize("case_id", END_TO_END_CASE_IDS)
def test_end_to_end_pdf_pipeline_gives_same_result_as_corpus(
    case_id, client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    case = CASES_BY_ID[case_id]
    fir_upload = _upload(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", _text_pdf_bytes([case.fir_text])
    )
    survey_upload = _upload(
        client, customer1_token, seed_data["claim1"], "survey_report", "survey.pdf", _text_pdf_bytes([case.survey_text])
    )
    assert fir_upload.status_code == 201, fir_upload.text
    assert survey_upload.status_code == 201, survey_upload.text
    fir_id, survey_id = fir_upload.json()["Document_ID"], survey_upload.json()["Document_ID"]
    analyzed_document_ids.extend([fir_id, survey_id])
    for document_id in (fir_id, survey_id):
        analyze = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
        assert analyze.status_code == 200, analyze.text

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/semantic-consistency",
        headers=auth_headers(officer_token),
    )
    assert response.status_code == 200, response.text
    narrative = response.json()["narrative"]
    assert narrative["document_a"]["document_id"] == fir_id
    assert narrative["document_b"]["document_id"] == survey_id
    assert narrative["relationship"] == case.observed, narrative["explanation"]
    assert narrative["confidence"] is None
