"""Tests for GET /api/v1/surveyor/claims/{claim_id}/documents and
GET /api/v1/surveyor/claims/{claim_id}/documents/{document_id}/content.

The surveyor's Claim Documents panel must show only RC, Driving Licence and
Insurance Policy - never FIR, Repair Estimate, Survey Report or any other
customer document type (see app/services/surveyor_documents.py). RC,
Driving Licence and Insurance Policy copies are now stored as real files on
upload (services/document_upload.py), so an assigned surveyor can view
them; a document-free-style check for a record predating that change is a
database-free test (tests/test_survey_report_rules.py), since the real
upload flow can no longer produce one. Per project rules these run against
the real PostgreSQL database and the real local filesystem storage (see
tests/conftest.py); every document row and physical file created here is
removed afterward regardless of outcome.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.db_models.document import Document
from app.services import document_storage
from tests.conftest import TEST_PASSWORD, auth_headers, get_token

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n%%EOF"

RESTRICTED_TYPES = ("FIR", "Repair Estimate", "Survey Report")
ALLOWED_TYPES = ("RC", "Driving Licence", "Insurance Policy")


@pytest.fixture()
def created_document_ids():
    """Mirrors tests/test_document_upload.py's fixture: every Document row
    and any physical file created by a test is removed afterward, pass or
    fail, so the shared claim1 fixture's own teardown never hits a
    dangling foreign key."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    db = SessionLocal()
    try:
        rows = db.query(Document).filter(Document.Document_ID.in_(ids)).all()
        for row in rows:
            path = document_storage.storage_path_for(row.Claim_ID, row.Document_ID, row.Document_Name)
            document_storage.delete_file(path)
        db.query(Document).filter(Document.Document_ID.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _upload(client, token, claim_id, document_type, filename, content, content_type="application/pdf"):
    return client.post(
        "/api/v1/documents",
        headers=auth_headers(token),
        data={"claim_id": claim_id, "document_type": document_type},
        files={"file": (filename, content, content_type)},
    )


@pytest.fixture()
def one_of_each_document_type(client, customer1_token, seed_data, created_document_ids):
    """claim1 gets one real document of every customer-facing type - the
    three identity-verification copies and FIR/Repair Estimate, all now
    stored as real files. Uploaded through the real customer endpoint,
    exactly as a customer would."""
    claim_id = seed_data["claim1"]
    ids: dict[str, str] = {}
    for key, document_type in [
        ("rc_book", "RC"),
        ("driving_licence", "Driving Licence"),
        ("insurance_policy", "Insurance Policy"),
    ]:
        response = _upload(client, customer1_token, claim_id, key, f"{key}.pdf", PDF_BYTES)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["Document_Type"] == document_type
        ids[document_type] = body["Document_ID"]
        created_document_ids.append(body["Document_ID"])

    for key, document_type in [("fir_copy", "FIR"), ("repair_estimate", "Repair Estimate")]:
        response = _upload(client, customer1_token, claim_id, key, f"{key}.pdf", PDF_BYTES)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["Document_Type"] == document_type
        ids[document_type] = body["Document_ID"]
        created_document_ids.append(body["Document_ID"])

    return ids


# ---------------------------------------------------------------- listing


def test_lists_only_rc_licence_and_policy(client, surveyor_token, seed_data, one_of_each_document_type):
    claim_id = seed_data["claim1"]
    response = client.get(f"/api/v1/surveyor/claims/{claim_id}/documents", headers=auth_headers(surveyor_token))
    assert response.status_code == 200, response.text
    documents = response.json()["documents"]
    types = {d["document_type"] for d in documents}

    assert types == set(ALLOWED_TYPES)
    for restricted in RESTRICTED_TYPES:
        assert restricted not in types


def test_freshly_uploaded_rc_licence_and_policy_are_available_with_a_stored_file(
    client, surveyor_token, seed_data, one_of_each_document_type
):
    """A real customer upload of RC/Driving Licence/Insurance Policy now
    stores a file (services/document_upload.py), so the assigned surveyor
    sees it as available, with the right media type to open - never a
    falsely-missing "not retained" state for a document that really has a
    file behind it."""
    claim_id = seed_data["claim1"]
    response = client.get(f"/api/v1/surveyor/claims/{claim_id}/documents", headers=auth_headers(surveyor_token))
    documents = {d["document_type"]: d for d in response.json()["documents"]}

    for allowed_type in ALLOWED_TYPES:
        entry = documents[allowed_type]
        assert entry["availability"] == "available", entry
        assert entry["media_type"] == "application/pdf"


def test_allowed_types_can_be_opened_by_the_assigned_surveyor(
    client, surveyor_token, seed_data, one_of_each_document_type
):
    claim_id = seed_data["claim1"]
    for allowed_type in ALLOWED_TYPES:
        document_id = one_of_each_document_type[allowed_type]
        response = client.get(
            f"/api/v1/surveyor/claims/{claim_id}/documents/{document_id}/content",
            headers=auth_headers(surveyor_token),
        )
        assert response.status_code == 200, response.text
        assert response.content == PDF_BYTES
        assert response.headers["content-type"] == "application/pdf"


def test_restricted_types_are_not_openable_even_with_a_real_document_id(
    client, surveyor_token, seed_data, one_of_each_document_type
):
    """Not just hidden from the list - the content route itself refuses a
    guessed/linked document_id for an excluded type."""
    claim_id = seed_data["claim1"]
    for restricted_type in ("FIR", "Repair Estimate"):
        document_id = one_of_each_document_type[restricted_type]
        response = client.get(
            f"/api/v1/surveyor/claims/{claim_id}/documents/{document_id}/content",
            headers=auth_headers(surveyor_token),
        )
        assert response.status_code == 404, response.text


# ---------------------------------------------------------------- authorization


def test_unauthenticated_request_is_rejected(client, seed_data):
    claim_id = seed_data["claim1"]
    response = client.get(f"/api/v1/surveyor/claims/{claim_id}/documents")
    assert response.status_code == 401


def test_non_surveyor_role_cannot_use_the_surveyor_documents_endpoint(client, customer1_token, seed_data):
    claim_id = seed_data["claim1"]
    response = client.get(f"/api/v1/surveyor/claims/{claim_id}/documents", headers=auth_headers(customer1_token))
    assert response.status_code == 403


def test_a_surveyor_not_assigned_to_the_claim_cannot_list_or_view_its_documents(
    client, seed_data, one_of_each_document_type, other_surveyor_claim
):
    """other_surveyor_claim's surveyor (test_surveyor2) is assigned to a
    different claim, never to claim1 - claim1's documents must stay
    inaccessible to them."""
    claim_id = seed_data["claim1"]
    token = get_token(client, "test_surveyor2", TEST_PASSWORD)

    list_response = client.get(f"/api/v1/surveyor/claims/{claim_id}/documents", headers=auth_headers(token))
    assert list_response.status_code == 404, list_response.text

    rc_document_id = one_of_each_document_type["RC"]
    content_response = client.get(
        f"/api/v1/surveyor/claims/{claim_id}/documents/{rc_document_id}/content",
        headers=auth_headers(token),
    )
    assert content_response.status_code == 404, content_response.text


# ---------------------------------------------------------------- unrelated workflows unaffected


def test_officer_still_sees_every_document_type_through_the_general_endpoint(
    client, officer_token, seed_data, one_of_each_document_type
):
    claim_id = seed_data["claim1"]
    response = client.get(f"/api/v1/documents?claim_id={claim_id}", headers=auth_headers(officer_token))
    assert response.status_code == 200, response.text
    types = {d["Document_Type"] for d in response.json()}
    assert set(ALLOWED_TYPES) | {"FIR", "Repair Estimate"} <= types


def test_customer_can_still_list_their_own_fir_and_repair_estimate(
    client, customer1_token, seed_data, one_of_each_document_type
):
    claim_id = seed_data["claim1"]
    response = client.get(f"/api/v1/documents?claim_id={claim_id}", headers=auth_headers(customer1_token))
    assert response.status_code == 200, response.text
    types = {d["Document_Type"] for d in response.json()}
    assert "FIR" in types
    assert "Repair Estimate" in types


# ---------------------------------------------------------------- legacy records without a file


def test_a_record_with_no_file_is_unavailable_not_falsely_available(
    client, surveyor_token, seed_data, created_document_ids
):
    """A document row can exist with no file behind it - e.g. one uploaded
    before RC/licence/policy copies were stored. Inserted directly (the
    real upload endpoint can no longer produce this), only to prove the
    endpoint never reports it as available or serves content for it."""
    claim_id = seed_data["claim1"]
    document_id = "TEST-DOC-RC-NO-FILE"
    db = SessionLocal()
    db.add(
        Document(
            Document_ID=document_id,
            Claim_ID=claim_id,
            Document_Type="RC",
            Document_Name="rc-copy.pdf",
            Document_Submitted_Date=date.today(),
            Document_Status="Submitted",
            OCR_Confidence_Score=Decimal("0.0000"),
            Extracted_Text="Registration No: TN09BX4417",
            Document_Completeness=Decimal("0.0000"),
            Document_Mismatch_Indicator=False,
            Verification_Status="Pending",
        )
    )
    db.commit()
    db.close()
    created_document_ids.append(document_id)

    list_response = client.get(f"/api/v1/surveyor/claims/{claim_id}/documents", headers=auth_headers(surveyor_token))
    entry = next(d for d in list_response.json()["documents"] if d["document_id"] == document_id)
    assert entry["availability"] == "unavailable"

    content_response = client.get(
        f"/api/v1/surveyor/claims/{claim_id}/documents/{document_id}/content",
        headers=auth_headers(surveyor_token),
    )
    assert content_response.status_code == 404, content_response.text
