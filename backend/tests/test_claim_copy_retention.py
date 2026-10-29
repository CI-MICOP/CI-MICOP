"""RC / driving-licence / policy copies are read AND kept as a stored file
(so an assigned surveyor can view them - see services/surveyor_documents.py),
but what is persisted in Extracted_Text stays reduced to the verification
record, and the stored filename stays a neutral placeholder.

Database-free: the CRUD calls are replaced by in-memory stand-ins, and the
document storage root and the temporary directory point at pytest's
tmp_path, so the tests can show exactly what is and is not left behind.
"""

import asyncio
import io
import tempfile
from decimal import Decimal
from types import SimpleNamespace

import fitz
import pytest
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.schemas.document import DocumentOut
from app.services import claim_copy_retention, document_analysis, document_upload, entity_extraction

RC_TEXT = """Certificate of Registration (copy)
Registration No: TN09BX4417
Regn. Date: 12/03/2022
Owner Name: Priya Sharma
Address: 15, Station Road, Delhi, Delhi 110017
Chassis No: ZZZHYU22SCN000001
"""
POLICY_TEXT = """Motor Insurance Policy Schedule
Policy No: POL-926009
Insured: Priya Sharma
Period of Insurance: 18/02/2026 to 17/02/2027
Vehicle Details
Registration No: DL3CBV8840
"""
LICENCE_TEXT = """Driving Licence (copy)
Licence No: DL99 2018 0000005
Name: Priya Sharma
Date of Birth: 08/09/1994
Address: 15, Station Road, Delhi
Class of Vehicle: LMV, MCWG
"""
# OCR-style variants: label and value on separate lines, a misread letter
# O for zero, and two different well-formed numbers.
OCR_TEXTS = [
    "Vehicle Registration\nRegistration No:\nMHO2EM6629\nOwner: Fatima Shaikh",
    "Reg No - MH02EM6628 noted by the clerk\nMaker: Honda",
    "Certificate\nTN09CB6627\nsome text TN09CB6672 more text",
    "Policy Number: POL926001 issued to Ananya Iyer",
]


def _candidates(text, document_type):
    result = entity_extraction.extract_entities(text, document_type=document_type)
    return sorted(
        (c.entity_type, c.value, c.normalized_value, c.source, c.confidence, getattr(c, "correction", None))
        for c in result.entities
    )


@pytest.mark.parametrize(
    "text, document_type",
    [(RC_TEXT, "RC"), (POLICY_TEXT, "Insurance Policy"), (LICENCE_TEXT, "Driving Licence")]
    + [(text, "RC") for text in OCR_TEXTS],
)
def test_kept_record_gives_the_same_candidates_as_the_full_text(text, document_type):
    record = claim_copy_retention.verification_record(text)
    assert _candidates(record, document_type) == _candidates(text, document_type)


def test_kept_record_drops_personal_details():
    for text in (RC_TEXT, POLICY_TEXT, LICENCE_TEXT):
        record = claim_copy_retention.verification_record(text)
        for personal in ("Priya Sharma", "Station Road", "08/09/1994", "110017"):
            assert personal not in record
    assert "TN09BX4417" in claim_copy_retention.verification_record(RC_TEXT)
    assert "POL-926009" in claim_copy_retention.verification_record(POLICY_TEXT)


def test_only_rc_licence_and_policy_have_reduced_extracted_text():
    """is_copy_retained now governs text reduction, not file storage - all
    seven types store a file; only these three reduce Extracted_Text."""
    assert not any(
        claim_copy_retention.is_copy_retained(t) for t in ("RC", "Driving Licence", "Insurance Policy")
    )
    assert all(
        claim_copy_retention.is_copy_retained(t)
        for t in ("FIR", "Repair Estimate", "Accident Photos", "Survey Report")
    )


# ---------------------------------------------------------------- upload flow


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=10)
    content = doc.tobytes()
    doc.close()
    return content


JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


class FakeDb:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.added = []
        self.rolled_back = False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("database unavailable")

    def rollback(self):
        self.rolled_back = True

    def refresh(self, _):
        pass


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    storage, temp = tmp_path / "storage", tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", str(storage))
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(document_upload.crud_claim, "get", lambda db, cid: SimpleNamespace(Customer_ID="C1"))
    monkeypatch.setattr(document_upload.crud_document, "generate_document_id", lambda db: "DOC-TEST-000001")
    monkeypatch.setattr(document_upload.crud_document, "create", lambda db, doc: db.added.append(doc) or doc)
    return SimpleNamespace(storage=storage, temp=temp)


def _files(path):
    return [p for p in path.rglob("*") if p.is_file()] if path.exists() else []


def _upload(db, document_type, filename, content):
    upload = UploadFile(file=io.BytesIO(content), filename=filename)
    return asyncio.run(document_upload.upload_document_for_customer(db, "C1", "CLM-1", document_type, upload))


def test_rc_copy_is_read_and_the_file_is_kept_with_reduced_text(dirs):
    db = FakeDb()
    content = _pdf(RC_TEXT)
    document = _upload(db, "rc_book", "rc.pdf", content)
    assert document.Document_Type == "RC"
    assert "TN09BX4417" in document.Extracted_Text
    assert "Priya Sharma" not in document.Extracted_Text and "Station Road" not in document.Extracted_Text
    assert document.OCR_Confidence_Score == Decimal("1.0")  # native PDF text, not an OCR guess
    assert document.Verification_Status == "Pending"
    # The file IS kept now, so an assigned surveyor can view it...
    stored = _files(dirs.storage)
    assert len(stored) == 1 and _files(dirs.temp) == []
    assert stored[0].read_bytes() == content
    assert DocumentOut.model_validate(document).Copy_Retained is True
    # ...but under a neutral name, never the customer's own filename.
    assert document.Document_Name == "rc-copy.pdf"


def test_a_filename_carrying_a_name_is_not_stored_for_a_copy(dirs):
    document = _upload(FakeDb(), "driving_licence", "DL_Priya_Sharma.pdf", _pdf(LICENCE_TEXT))
    assert document.Document_Name == "driving-licence-copy.pdf"
    assert "Priya" not in document.Document_Name + document.Extracted_Text


@pytest.mark.parametrize("document_type, filename", [("driving_licence", "dl.pdf"), ("insurance_policy", "pol.pdf")])
def test_licence_and_policy_copies_are_kept_with_reduced_text(dirs, document_type, filename):
    document = _upload(FakeDb(), document_type, filename, _pdf(POLICY_TEXT if "pol" in filename else LICENCE_TEXT))
    assert "Priya Sharma" not in document.Extracted_Text
    assert len(_files(dirs.storage)) == 1 and _files(dirs.temp) == []


def test_temporary_copy_is_removed_when_extraction_fails(dirs, monkeypatch):
    seen = []

    def boom(path):
        seen.append(path.exists())
        raise RuntimeError("OCR crashed")

    monkeypatch.setattr(document_analysis, "extract_document_text", boom)
    with pytest.raises(RuntimeError):
        _upload(FakeDb(), "rc_book", "rc.pdf", _pdf(RC_TEXT))
    assert seen == [True]  # the copy existed while it was being read...
    assert _files(dirs.temp) == [] and _files(dirs.storage) == []  # ...and is gone afterwards


def test_nothing_is_left_when_the_database_write_fails(dirs):
    db = FakeDb(fail_commit=True)
    with pytest.raises(HTTPException) as error:
        _upload(db, "rc_book", "rc.pdf", _pdf(RC_TEXT))
    assert error.value.status_code == 500 and db.rolled_back
    assert _files(dirs.storage) == [] and _files(dirs.temp) == []


def test_unreadable_copy_keeps_no_text_but_the_file_is_still_kept(dirs, monkeypatch):
    monkeypatch.setattr(document_analysis, "_tesseract_available", lambda: False)
    document = _upload(FakeDb(), "rc_book", "rc.jpg", JPEG)
    assert document.Extracted_Text == "" and document.OCR_Confidence_Score == Decimal("0.0")
    # Nothing could be read from it, but the file itself is still stored -
    # a surveyor can still view the image even though nothing was extracted.
    assert len(_files(dirs.storage)) == 1 and _files(dirs.temp) == []


def test_fir_is_claim_evidence_and_is_stored(dirs):
    document = _upload(FakeDb(), "fir_copy", "fir.pdf", _pdf("FIR No: 0418/2026"))
    stored = _files(dirs.storage)
    assert len(stored) == 1 and stored[0].name.startswith("DOC-TEST-000001")
    assert document.Extracted_Text == ""  # analysed later, as before
    assert DocumentOut.model_validate(document).Copy_Retained is True


def test_accident_photo_must_be_an_image(dirs):
    with pytest.raises(HTTPException) as error:
        _upload(FakeDb(), "accident_photos", "photo.pdf", _pdf("not a photo"))
    assert error.value.status_code == 400
    assert _upload(FakeDb(), "accident_photos", "photo.jpg", JPEG).Document_Type == "Accident Photos"


def test_upload_validation_still_applies_to_copies(dirs):
    with pytest.raises(HTTPException) as error:
        _upload(FakeDb(), "rc_book", "rc.pdf", b"not a pdf")
    assert error.value.status_code == 400
    assert _files(dirs.temp) == []


# ---------------------------------------------------------------- re-analysis


class AnalysisDb:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def add(self, _):
        pass

    def refresh(self, _):
        pass


def test_reanalysis_shows_kept_details_and_never_overwrites_them(dirs):
    document = SimpleNamespace(
        Document_ID="DOC-1", Claim_ID="CLM-1", Document_Type="RC", Document_Name="rc.pdf",
        Extracted_Text="Registration No: TN09BX4417", OCR_Confidence_Score=Decimal("1.0000"),
    )
    db = AnalysisDb()
    result = document_analysis.analyze_document(db, document)
    assert result.status == "copy_not_retained"
    assert result.text == "Registration No: TN09BX4417"
    assert db.commits == 0 and document.Extracted_Text == "Registration No: TN09BX4417"


def test_reanalysis_of_a_copy_with_nothing_kept_says_so(dirs):
    document = SimpleNamespace(
        Document_ID="DOC-2", Claim_ID="CLM-1", Document_Type="Driving Licence", Document_Name="dl.pdf",
        Extracted_Text="", OCR_Confidence_Score=Decimal("0.0000"),
    )
    result = document_analysis.analyze_document(AnalysisDb(), document)
    assert result.status == "copy_not_retained" and result.text == ""
    assert any("not kept" in note for note in result.limitations)
