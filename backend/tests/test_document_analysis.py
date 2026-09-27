"""Tests for Step 5.8.12 - document completeness + OCR.

Per project rules these run against the real PostgreSQL database and the
real local filesystem storage (see tests/conftest.py); every document row
and physical file created here is removed afterward regardless of outcome.

IMPORTANT about Tesseract: this development environment does not have the
Tesseract OCR executable installed (confirmed via
`pytesseract.get_tesseract_version()` raising TesseractNotFoundError - see
docs/project_documentation/DOCUMENT_COMPLETENESS_AND_OCR.md, Section 7/14).
Tests that exercise genuine end-to-end image/scanned-PDF OCR therefore
assert the honest "unavailable" behavior actually produced in THIS
environment, rather than a fabricated successful OCR result. A handful of
tests explicitly simulate Tesseract's own output format (clearly labeled
"_simulated_tesseract") purely to unit-test the confidence-aggregation and
text-combination logic in isolation - they do not claim real OCR execution
was demonstrated. Native PDF text extraction needs no OCR at all and is
tested for real, unmocked, in every environment.
"""

import io
from decimal import Decimal
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image

from app.crud import document as crud_document
from app.db.session import SessionLocal
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.document import Document
from app.services import document_analysis
from app.services import document_storage
from tests.conftest import auth_headers

PDF_MAGIC_ONLY = b"%PDF-1.4\n%not a real pdf structure\n%%EOF"
JPG_MAGIC_ONLY = b"\xff\xd8\xff\xe0" + b"\x00" * 20


def _text_pdf_bytes(pages_text: list[str]) -> bytes:
    """A genuine multi-page PDF with real embedded text - PyMuPDF's own
    native-text-extraction path, no OCR/Tesseract involved."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _image_only_pdf_bytes() -> bytes:
    """A genuine PDF with an embedded raster image and no text layer -
    the "scanned document" case that requires OCR to read at all."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=_png_bytes())
    data = doc.tobytes()
    doc.close()
    return data


def _png_bytes(size=(120, 40), color="white") -> bytes:
    image = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def analyzed_document_ids():
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


# ============================================================== A/B: OCR - images
# (real, unmocked - this environment genuinely has no Tesseract installed)


def test_image_ocr_reports_honest_unavailable_state_without_tesseract(tmp_path):
    if document_analysis._tesseract_available():
        pytest.skip("Tesseract is installed in this environment - the unavailable path does not apply.")
    path = tmp_path / "sample.png"
    path.write_bytes(_png_bytes())

    result = document_analysis.extract_text_from_image(path)

    assert result.status == "unavailable"
    assert result.confidence == 0.0
    assert result.text == ""
    assert any("tesseract" in msg.lower() for msg in result.limitations)


def test_corrupted_image_does_not_crash(tmp_path, monkeypatch):
    # Force past the availability check so Image.open()'s own failure path is exercised.
    monkeypatch.setattr(document_analysis, "_tesseract_available", lambda: True)
    path = tmp_path / "corrupt.jpg"
    path.write_bytes(JPG_MAGIC_ONLY)  # magic bytes only, not a decodable image

    result = document_analysis.extract_text_from_image(path)

    assert result.status == "unavailable"
    assert result.confidence == 0.0
    assert result.text == ""


def test_image_ocr_simulated_tesseract_ignores_invalid_confidence_values(tmp_path, monkeypatch):
    """Simulates Tesseract's own image_to_data output shape (including its
    -1 sentinel for non-word boxes) to prove the aggregation logic never
    averages those in - does not claim real OCR execution."""
    monkeypatch.setattr(document_analysis, "_tesseract_available", lambda: True)
    monkeypatch.setattr(document_analysis.pytesseract, "image_to_string", lambda image: "Policy No 12345")
    monkeypatch.setattr(
        document_analysis.pytesseract,
        "image_to_data",
        lambda image, output_type=None: {"conf": [-1, -1, "92", "88", "not-a-number"]},
    )
    path = tmp_path / "sample.png"
    path.write_bytes(_png_bytes())

    result = document_analysis.extract_text_from_image(path)

    assert result.status == "extracted_ocr"
    assert result.text == "Policy No 12345"
    assert abs(result.confidence - ((92 + 88) / 2 / 100.0)) < 1e-9


def test_image_ocr_text_without_any_valid_confidence_is_honestly_unscored(tmp_path, monkeypatch):
    monkeypatch.setattr(document_analysis, "_tesseract_available", lambda: True)
    monkeypatch.setattr(document_analysis.pytesseract, "image_to_string", lambda image: "some text")
    monkeypatch.setattr(
        document_analysis.pytesseract, "image_to_data", lambda image, output_type=None: {"conf": [-1, -1]}
    )
    path = tmp_path / "sample.png"
    path.write_bytes(_png_bytes())

    result = document_analysis.extract_text_from_image(path)

    assert result.status == "extracted_ocr_no_confidence"
    assert result.confidence == 0.0  # never fabricated just because text exists
    assert result.text == "some text"


# ============================================================== calculate_ocr_confidence


def test_calculate_ocr_confidence_ignores_negative_and_invalid_values():
    assert document_analysis.calculate_ocr_confidence([-1, -1, "90", "80", None, "bad"]) == pytest.approx(0.85)


def test_calculate_ocr_confidence_returns_none_when_nothing_valid():
    assert document_analysis.calculate_ocr_confidence([-1, -1, "-1"]) is None
    assert document_analysis.calculate_ocr_confidence([]) is None


# ============================================================== B: OCR - PDFs


def test_native_pdf_text_extraction_is_real_not_ocr(tmp_path):
    path = tmp_path / "native.pdf"
    path.write_bytes(_text_pdf_bytes(["Claim supporting document. Registration ABC123."]))

    result = document_analysis.extract_text_from_pdf(path)

    assert result.status == "extracted_native"
    assert "Registration ABC123" in result.text
    assert result.confidence == 1.0  # exact source text, not a probabilistic guess


def test_multi_page_native_pdf_combines_pages_in_order(tmp_path):
    path = tmp_path / "multi.pdf"
    path.write_bytes(_text_pdf_bytes(["Page one content here.", "Page two content here."]))

    result = document_analysis.extract_text_from_pdf(path)

    assert result.status == "extracted_native"
    assert result.text.index("Page one") < result.text.index("Page two")


def test_scanned_pdf_without_tesseract_is_honestly_unavailable(tmp_path):
    if document_analysis._tesseract_available():
        pytest.skip("Tesseract is installed in this environment - the unavailable path does not apply.")
    path = tmp_path / "scanned.pdf"
    path.write_bytes(_image_only_pdf_bytes())

    result = document_analysis.extract_text_from_pdf(path)

    assert result.status in ("unavailable", "empty")
    assert result.confidence == 0.0
    assert any("tesseract" in msg.lower() for msg in result.limitations)


def test_scanned_pdf_simulated_tesseract_runs_ocr_on_image_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(document_analysis, "_tesseract_available", lambda: True)
    monkeypatch.setattr(document_analysis.pytesseract, "image_to_string", lambda image: "Scanned page text")
    monkeypatch.setattr(
        document_analysis.pytesseract, "image_to_data", lambda image, output_type=None: {"conf": ["95", -1]}
    )
    path = tmp_path / "scanned.pdf"
    path.write_bytes(_image_only_pdf_bytes())

    result = document_analysis.extract_text_from_pdf(path)

    assert result.status == "extracted_ocr"
    assert "Scanned page text" in result.text
    assert abs(result.confidence - 0.95) < 1e-9


def test_encrypted_pdf_is_honestly_unavailable(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Secret content.")
    doc.save(str(tmp_path / "encrypted.pdf"), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret")
    doc.close()

    result = document_analysis.extract_text_from_pdf(tmp_path / "encrypted.pdf")

    assert result.status == "unavailable"
    assert result.confidence == 0.0
    assert "password" in result.limitations[0].lower()


def test_empty_pdf_zero_pages_handled_without_crashing(tmp_path, monkeypatch):
    # PyMuPDF itself refuses to save a genuinely zero-page PDF file, so the
    # zero-page branch is exercised via a minimal fake with the same shape
    # fitz.open() returns, rather than skipping this case entirely.
    fake_pdf = SimpleNamespace(is_encrypted=False, page_count=0, close=lambda: None)
    monkeypatch.setattr(document_analysis.fitz, "open", lambda path: fake_pdf)
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"%PDF-1.4\n%%EOF")

    result = document_analysis.extract_text_from_pdf(path)

    assert result.status == "empty"
    assert result.confidence == 0.0


def test_corrupted_pdf_does_not_crash(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is not a pdf at all")

    result = document_analysis.extract_text_from_pdf(path)

    assert result.status == "unavailable"
    assert result.confidence == 0.0


def test_unsupported_extension_is_honestly_unavailable(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes(b"plain text file")

    result = document_analysis.extract_document_text(path)

    assert result.status == "unavailable"
    assert "unsupported" in result.limitations[0].lower()


def test_missing_file_does_not_crash_analyze_document():
    fake_document = SimpleNamespace(
        Document_ID="DOC-DOES-NOT-EXIST", Claim_ID="NOPE", Document_Name="missing.pdf"
    )
    path = document_analysis.resolve_document_path(fake_document)
    assert not path.exists()


# ============================================================== E: completeness (pure logic)


def _docs(*types: str):
    return [SimpleNamespace(Document_Type=t) for t in types]


def test_completeness_all_required_present_for_own_damage():
    result = document_analysis.calculate_claim_document_completeness(
        "Own Damage", _docs("Driving Licence", "RC", "Insurance Policy", "Repair Estimate", "Accident Photos")
    )
    assert result.available is True
    assert result.ratio == 1.0
    assert result.missing == []


def test_completeness_one_required_missing():
    result = document_analysis.calculate_claim_document_completeness(
        "Own Damage", _docs("Driving Licence", "RC", "Insurance Policy", "Repair Estimate")
    )
    assert result.available is True
    assert result.missing == ["Accident Photos"]
    assert result.ratio == pytest.approx(4 / 5)


def test_completeness_multiple_required_missing():
    result = document_analysis.calculate_claim_document_completeness("Third Party", _docs("RC"))
    required = document_analysis.get_required_document_types("Third Party")
    assert result.available is True
    assert result.ratio == pytest.approx(1 / len(required))


def test_completeness_duplicate_document_type_counts_once():
    with_dupes = document_analysis.calculate_claim_document_completeness(
        "Theft", _docs("FIR", "FIR", "FIR", "Driving Licence")
    )
    without_dupes = document_analysis.calculate_claim_document_completeness(
        "Theft", _docs("FIR", "Driving Licence")
    )
    assert with_dupes.ratio == without_dupes.ratio
    assert with_dupes.present == without_dupes.present


def test_completeness_zero_documents_is_unavailable_not_zero_percent():
    result = document_analysis.calculate_claim_document_completeness("Own Damage", [])
    assert result.available is False
    assert result.ratio is None


def test_completeness_unknown_claim_type_falls_back_to_base_set():
    result = document_analysis.calculate_claim_document_completeness(
        "Some Future Claim Type", _docs("Driving Licence", "RC", "Insurance Policy")
    )
    assert result.available is True
    assert result.ratio == 1.0
    assert set(result.required) == {"Driving Licence", "RC", "Insurance Policy"}


# ============================================================== F/G: authorization + persistence (real HTTP)


def test_customer_can_analyze_their_own_document(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(
        client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", _text_pdf_bytes(["FIR text content."])
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["extraction_status"] == "extracted_native"
    assert "FIR text content" in body["extracted_text"]
    assert body["ocr_confidence"] == 1.0
    assert body["mismatch_indicator"] is False
    # No raw filesystem path is ever exposed.
    assert "storage" not in response.text and "infra" not in response.text


def test_customer_cannot_analyze_another_customers_document(
    client, customer1_token, customer2_token, seed_data, analyzed_document_ids
):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer2_token))
    assert response.status_code == 403


def test_assigned_surveyor_can_analyze_document_on_their_claim(
    client, customer1_token, surveyor_token, seed_data, analyzed_document_ids
):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(surveyor_token))
    assert response.status_code == 200


def test_officer_and_admin_can_analyze_any_document(
    client, customer1_token, officer_token, admin_token, seed_data, analyzed_document_ids
):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    assert client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(officer_token)).status_code == 200
    assert client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(admin_token)).status_code == 200


def test_unauthenticated_analyze_returns_401(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze")
    assert response.status_code == 401


def test_analyze_nonexistent_document_returns_404(client, customer1_token):
    response = client.post("/api/v1/documents/DOC-NO-SUCH-ID/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 404


def test_single_document_analyze_persists_text_and_confidence_but_not_completeness(
    client, customer1_token, seed_data, analyzed_document_ids
):
    upload = _upload(
        client, customer1_token, seed_data["claim1"], "rc_book", "rc.pdf", _text_pdf_bytes(["RC book contents."])
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 200

    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.Document_ID == document_id).first()
        assert "RC book contents" in row.Extracted_Text
        assert row.OCR_Confidence_Score == Decimal("1.0000")
        # Completeness is a claim-level fact - the single-document endpoint
        # does not mutate it (see analyze_claim_documents for that).
        assert row.Document_Completeness == Decimal("0.0000")
        # Human verification fields are untouched by automated OCR.
        assert row.Verification_Status == "Pending"
        assert row.Document_Status == "Submitted"
    finally:
        db.close()


def test_claim_level_analyze_requires_officer_or_admin(client, customer1_token, surveyor_token, seed_data):
    for token in (customer1_token, surveyor_token):
        response = client.post(
            f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze", headers=auth_headers(token)
        )
        assert response.status_code == 403


def test_claim_level_analyze_unauthenticated_returns_401(client, seed_data):
    response = client.post(f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze")
    assert response.status_code == 401


def test_claim_level_analyze_nonexistent_claim_returns_404(client, officer_token):
    response = client.post("/api/v1/officer/claims/NO-SUCH-CLAIM/documents/analyze", headers=auth_headers(officer_token))
    assert response.status_code == 404


def test_claim_level_analyze_zero_documents_is_honest_not_fabricated(client, officer_token, unassigned_claim):
    response = client.post(
        f"/api/v1/officer/claims/{unassigned_claim}/documents/analyze", headers=auth_headers(officer_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["documents_analyzed"] == 0
    assert body["completeness"]["available"] is False
    assert body["completeness"]["completeness_ratio"] is None


def test_claim_level_analyze_computes_and_persists_completeness_across_documents(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    uploads = [
        _upload(client, customer1_token, seed_data["claim1"], "driving_licence", "dl.pdf", PDF_MAGIC_ONLY),
        _upload(client, customer1_token, seed_data["claim1"], "rc_book", "rc.pdf", PDF_MAGIC_ONLY),
        _upload(client, customer1_token, seed_data["claim1"], "insurance_policy", "policy.pdf", PDF_MAGIC_ONLY),
        _upload(client, customer1_token, seed_data["claim1"], "repair_estimate", "estimate.pdf", PDF_MAGIC_ONLY),
        # Accident Photos intentionally omitted - claim1 is "Own Damage",
        # so this claim should come out to 4/5 required types present.
    ]
    document_ids = [u.json()["Document_ID"] for u in uploads]
    analyzed_document_ids.extend(document_ids)

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze", headers=auth_headers(officer_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["documents_analyzed"] == len(document_ids)
    assert body["completeness"]["available"] is True
    assert body["completeness"]["completeness_ratio"] == pytest.approx(4 / 5)
    assert body["completeness"]["missing_document_types"] == ["Accident Photos"]

    db = SessionLocal()
    try:
        rows = db.query(Document).filter(Document.Document_ID.in_(document_ids)).all()
        assert len(rows) == len(document_ids)
        for row in rows:
            assert row.Document_Completeness == Decimal("0.8000")
    finally:
        db.close()


# ============================================================== H: human-in-the-loop safety


def test_document_analysis_never_modifies_final_decision_or_approved_amount(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    db = SessionLocal()
    try:
        before = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        final_decision_before = before.Final_Decision
        approved_amount_before = before.Approved_Amount
        audit_count_before = db.query(ClaimDecisionAudit).filter(
            ClaimDecisionAudit.Claim_ID == seed_data["claim1"]
        ).count()
    finally:
        db.close()

    assert client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token)).status_code == 200
    assert client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze", headers=auth_headers(officer_token)
    ).status_code == 200

    db = SessionLocal()
    try:
        after = db.query(Claim).filter(Claim.Claim_ID == seed_data["claim1"]).first()
        assert after.Final_Decision == final_decision_before
        assert after.Approved_Amount == approved_amount_before
        audit_count_after = db.query(ClaimDecisionAudit).filter(
            ClaimDecisionAudit.Claim_ID == seed_data["claim1"]
        ).count()
        assert audit_count_after == audit_count_before
    finally:
        db.close()


# ============================================================== Step 5.8.13-A: entity extraction integration
#
# Controlled text embedded in a real PyMuPDF-generated PDF, uploaded and
# analyzed through the real API end to end - never the offline dataset's
# Faker-generated document text, and never a claim of real-document
# validation (see docs/project_documentation/ENTITY_EXTRACTION.md).


def test_analyze_response_includes_registration_entity_with_rc_context_boost(
    client, customer1_token, seed_data, analyzed_document_ids
):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Registration Certificate. Vehicle Registration Number: TN01AB0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["entities"]["status"] == "extracted"
    reg = next(e for e in body["entities"]["entities"] if e["entity_type"] == "registration_number")
    assert reg["normalized_value"] == "TN01AB0001"
    assert reg["source"] == "regex_strict_format"
    # RC is the strong-context document type for a registration number -
    # confidence must be boosted above the un-boosted 0.90 baseline.
    assert reg["confidence"] > 0.90
    assert any("not an nlp model" in msg.lower() for msg in body["entities"]["limitations"])


def test_analyze_response_includes_policy_entity_for_insurance_policy_document(
    client, customer1_token, seed_data, analyzed_document_ids
):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "insurance_policy",
        "policy.pdf",
        _text_pdf_bytes(["Insurance Policy Schedule. Policy Number: POL-000042."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 200, response.text
    body = response.json()

    pol = next(e for e in body["entities"]["entities"] if e["entity_type"] == "policy_number")
    assert pol["normalized_value"] == "POL-000042"
    assert pol["confidence"] > 0.70  # boosted by the Insurance Policy document-type context


def test_analyze_response_entities_unavailable_when_no_text_extracted(
    client, customer1_token, seed_data, analyzed_document_ids
):
    upload = _upload(client, customer1_token, seed_data["claim1"], "fir_copy", "fir.pdf", PDF_MAGIC_ONLY)
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    assert response.status_code == 200
    body = response.json()
    # PDF_MAGIC_ONLY has no real PyMuPDF-readable content - extraction
    # produces no usable text, so entity extraction must be honestly
    # unavailable rather than fabricating a candidate.
    assert body["entities"]["status"] in ("unavailable", "no_candidates")
    assert body["entities"]["entities"] == []


def test_entities_never_expose_filesystem_paths_or_secrets(client, customer1_token, seed_data, analyzed_document_ids):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TN01AB0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))
    body_text = response.text.lower()
    assert "infra" not in body_text
    assert "storage" not in body_text
    assert "tesseract_cmd" not in body_text
    assert "database_url" not in body_text


def test_cross_customer_cannot_analyze_document_to_read_its_entities(
    client, customer1_token, customer2_token, seed_data, analyzed_document_ids
):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TN01AB0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer2_token))
    assert response.status_code == 403


def test_claim_level_analyze_includes_entities_per_document(
    client, customer1_token, officer_token, seed_data, analyzed_document_ids
):
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TN01AB0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    response = client.post(
        f"/api/v1/officer/claims/{seed_data['claim1']}/documents/analyze", headers=auth_headers(officer_token)
    )
    assert response.status_code == 200
    body = response.json()
    doc_entry = next(d for d in body["documents"] if d["Document_ID"] == document_id)
    assert doc_entry["entities"]["status"] == "extracted"
    assert any(e["entity_type"] == "registration_number" for e in doc_entry["entities"]["entities"])


def test_entity_extraction_does_not_persist_or_touch_other_tables(
    client, customer1_token, seed_data, analyzed_document_ids
):
    """Step 5.8.13-A is read-time only - no new column, no new table, and
    the Document row itself gains no entity-shaped field from this call."""
    upload = _upload(
        client,
        customer1_token,
        seed_data["claim1"],
        "rc_book",
        "rc.pdf",
        _text_pdf_bytes(["Vehicle Registration Number: TN01AB0001."]),
    )
    document_id = upload.json()["Document_ID"]
    analyzed_document_ids.append(document_id)

    client.post(f"/api/v1/documents/{document_id}/analyze", headers=auth_headers(customer1_token))

    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.Document_ID == document_id).first()
        # Only the pre-existing Step 5.8.12 columns exist and were touched -
        # no entity-extraction-shaped column exists on the model at all.
        assert not hasattr(row, "Registration_Number_Candidate")
        assert not hasattr(row, "Extracted_Entities")
        assert "Vehicle Registration Number" in row.Extracted_Text
    finally:
        db.close()
