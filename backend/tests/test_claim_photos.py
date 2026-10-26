"""Customer camera photos and surveyor evidence photos go through the same
duplicate and quality checks, each keeping its own source label.
Database-free: the CRUD calls are replaced by in-memory records."""

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import claim_photos, document_storage, evidence_duplication, evidence_quality, evidence_storage
from tests.evidence_duplication_corpus import jpeg_bytes, scene


@pytest.fixture()
def stored(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", str(tmp_path / "documents"))
    monkeypatch.setattr(settings, "EVIDENCE_STORAGE_ROOT", str(tmp_path / "evidence"))
    documents, evidence = [], []

    def add_document(claim_id, doc_id, name, content, doc_type="Accident Photos"):
        documents.append(SimpleNamespace(Document_ID=doc_id, Claim_ID=claim_id, Document_Type=doc_type, Document_Name=name))
        document_storage.save_file(document_storage.storage_path_for(claim_id, doc_id, name), content)

    def add_evidence(claim_id, evidence_id, name, content):
        evidence.append(SimpleNamespace(Evidence_ID=evidence_id, Claim_ID=claim_id, Evidence_Type="Damage Photo", File_Name=name))
        path = evidence_storage.storage_path_for(claim_id, evidence_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    crud_doc, crud_ev = claim_photos.crud_document, claim_photos.crud_evidence
    monkeypatch.setattr(crud_doc, "list_by_claim", lambda db, cid: [d for d in documents if d.Claim_ID == cid])
    monkeypatch.setattr(crud_doc, "list_by_type", lambda db, t: [d for d in documents if d.Document_Type == t])
    monkeypatch.setattr(crud_ev, "list_by_claim", lambda db, cid: [e for e in evidence if e.Claim_ID == cid])
    monkeypatch.setattr(crud_ev, "list_all", lambda db: list(evidence))
    return SimpleNamespace(add_document=add_document, add_evidence=add_evidence)


def test_customer_and_surveyor_photos_keep_their_own_labels(stored):
    stored.add_evidence("CLM-1", "EVD-1", "front.jpg", jpeg_bytes(scene(1)))
    stored.add_document("CLM-1", "DOC-1", "accident-photo-1.jpg", jpeg_bytes(scene(2)))
    stored.add_document("CLM-1", "DOC-2", "fir.pdf", b"%PDF-1.4", doc_type="FIR")
    photos = claim_photos.claim_photos(None, "CLM-1")
    assert [(p.Evidence_ID, p.Evidence_Type) for p in photos] == [
        ("EVD-1", "Damage Photo"),
        ("DOC-1", claim_photos.CUSTOMER_PHOTO_LABEL),
    ]


def test_customer_photo_reused_from_a_surveyor_photo_on_another_claim_is_found(stored):
    content = jpeg_bytes(scene(7))
    stored.add_evidence("CLM-2", "EVD-9", "survey.jpg", content)
    stored.add_document("CLM-1", "DOC-1", "accident-photo-1.jpg", content)
    result = evidence_duplication.check_claim_evidence(None, SimpleNamespace(Claim_ID="CLM-1"))
    (photo,) = result.results
    assert photo.evidence_type == claim_photos.CUSTOMER_PHOTO_LABEL
    assert photo.status == evidence_duplication.STATUS_EXACT_DUPLICATE
    assert [m.evidence_id for m in photo.matches] == ["EVD-9"]


def test_different_customer_and_surveyor_photos_are_not_called_a_match(stored):
    stored.add_evidence("CLM-1", "EVD-1", "front.jpg", jpeg_bytes(scene(11)))
    stored.add_document("CLM-1", "DOC-1", "accident-photo-1.jpg", jpeg_bytes(scene(12)))
    result = evidence_duplication.check_claim_evidence(None, SimpleNamespace(Claim_ID="CLM-1"))
    assert {r.status for r in result.results} == {evidence_duplication.STATUS_NO_MATCH_FOUND}
    # "no copy found" is not a statement that both show the same damage
    assert all("does not prove" in r.explanation for r in result.results)


def test_quality_check_reads_customer_camera_photos(stored):
    stored.add_document("CLM-1", "DOC-1", "accident-photo-1.jpg", jpeg_bytes(scene(3).point(lambda v: v * 0.05)))
    result = evidence_quality.check_claim_photo_quality(None, SimpleNamespace(Claim_ID="CLM-1"))
    assert result.photos_checked == 1
    (photo,) = result.results
    assert photo.evidence_type == claim_photos.CUSTOMER_PHOTO_LABEL
    assert photo.status == evidence_quality.STATUS_ISSUES_FOUND


def test_missing_customer_photo_file_is_unavailable(stored):
    stored.add_document("CLM-1", "DOC-1", "accident-photo-1.jpg", jpeg_bytes(scene(4)))
    document_storage.storage_path_for("CLM-1", "DOC-1", "accident-photo-1.jpg").unlink()
    result = evidence_quality.check_claim_photo_quality(None, SimpleNamespace(Claim_ID="CLM-1"))
    assert result.results[0].status == evidence_quality.STATUS_UNAVAILABLE
