"""One-off operator script: deletes every claim in the ci_micop dev
database and every record exclusively dependent on those claims, while
preserving customer/vehicle/policy/account data and - where a claim's RC,
Driving Licence or Insurance Policy document is also that customer's
master identity document - detaching it from the claim instead of
deleting it (services/document_import.py's Customer_ID/Vehicle_ID/
Policy_ID columns make this possible without fabricating anything).

Run once, reviewed and approved by the project owner before execution.
Not part of the application; not imported by anything else.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: F401,E402  (side effect: registers every model)
from app.db.session import SessionLocal
from app.db_models.accident import Accident
from app.db_models.claim import Claim
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.cross_document_consistency import CrossDocumentConsistency
from app.db_models.document import Document
from app.db_models.evidence import Evidence
from app.db_models.fraud_risk_analysis import FraudRiskAnalysis
from app.db_models.repair_estimate import RepairEstimate
from app.db_models.surveyor_inspection import SurveyorInspection
from app.db_models.tp_claim import TPClaim
from app.db_models.vehicle_damage import VehicleDamage
from app.crud import document as crud_document
from app.services import document_storage, evidence_storage
from app.services.claim_copy_retention import NOT_RETAINED_DOCUMENT_TYPES as IDENTITY_TYPES

db = SessionLocal()
deleted_files: list[str] = []
detached_documents: list[str] = []
deleted_document_rows: list[str] = []

try:
    claims = db.query(Claim).all()
    claim_ids = [c.Claim_ID for c in claims]
    print(f"Claims to delete: {claim_ids}")

    for claim in claims:
        documents = db.query(Document).filter(Document.Claim_ID == claim.Claim_ID).all()
        for doc in documents:
            if doc.Document_Type in IDENTITY_TYPES:
                vehicle_id = claim.Vehicle_ID if doc.Document_Type == "RC" else None
                policy_id = claim.Policy_ID if doc.Document_Type == "Insurance Policy" else None
                existing = crud_document.find_identity_document(
                    db, doc.Document_Type, claim.Customer_ID, vehicle_id, policy_id
                )
                if existing is not None and existing.Document_ID != doc.Document_ID:
                    # A master copy already exists for this customer - this
                    # one is a redundant duplicate, safe to remove with its
                    # claim rather than kept as a second copy.
                    path = document_storage.storage_path_for(claim.Claim_ID, doc.Document_ID, doc.Document_Name)
                    document_storage.delete_file(path)
                    deleted_files.append(str(path))
                    deleted_document_rows.append(doc.Document_ID)
                    db.delete(doc)
                else:
                    old_path = document_storage.storage_path_for(claim.Claim_ID, doc.Document_ID, doc.Document_Name)
                    doc.Claim_ID = None
                    doc.Customer_ID = claim.Customer_ID
                    doc.Vehicle_ID = vehicle_id
                    doc.Policy_ID = policy_id
                    if old_path.exists():
                        new_path = document_storage.storage_path_for(
                            claim.Customer_ID, doc.Document_ID, doc.Document_Name
                        )
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        old_path.rename(new_path)
                    detached_documents.append(doc.Document_ID)
            else:
                path = document_storage.storage_path_for(claim.Claim_ID, doc.Document_ID, doc.Document_Name)
                document_storage.delete_file(path)
                deleted_files.append(str(path))
                deleted_document_rows.append(doc.Document_ID)
                db.delete(doc)

        for ev in db.query(Evidence).filter(Evidence.Claim_ID == claim.Claim_ID).all():
            path = evidence_storage.storage_path_for(claim.Claim_ID, ev.Evidence_ID, ev.File_Name)
            evidence_storage.delete_file(path)
            deleted_files.append(str(path))
            db.delete(ev)

        db.query(Accident).filter(Accident.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(CrossDocumentConsistency).filter(CrossDocumentConsistency.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(FraudRiskAnalysis).filter(FraudRiskAnalysis.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(RepairEstimate).filter(RepairEstimate.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(SurveyorInspection).filter(SurveyorInspection.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(TPClaim).filter(TPClaim.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)
        db.query(VehicleDamage).filter(VehicleDamage.Claim_ID == claim.Claim_ID).delete(synchronize_session=False)

    # Flush every document/evidence/dependent-table change to the database
    # before touching claims themselves - these models have no ORM
    # relationship() to claims, so the unit of work has no FK-aware
    # ordering between them and would otherwise attempt the claim deletes
    # before the documents.Claim_ID updates/deletes land.
    db.flush()

    for claim in claims:
        db.delete(claim)

    db.commit()
    print("COMMIT_OK")
    print("Detached (preserved) identity documents:", detached_documents)
    print("Deleted document rows:", deleted_document_rows)
    print("Deleted files:", deleted_files)

except Exception:
    db.rollback()
    print("ROLLED BACK - no changes were made")
    raise
finally:
    db.close()
