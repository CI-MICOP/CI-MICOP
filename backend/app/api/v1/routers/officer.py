from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_claims_officer_employee_id, require_roles
from app.crud import authentication_user as crud_user
from app.crud import claim as crud_claim
from app.crud import claim_decision_audit as crud_audit
from app.crud import cross_document_consistency as crud_consistency
from app.crud import document as crud_document
from app.crud import fraud_risk_analysis as crud_fraud
from app.crud import repair_estimate as crud_repair_estimate
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.claim import ClaimOut, ClaimSummaryOut
from app.schemas.claim_detail import (
    ClaimDecisionAuditOut,
    CrossDocumentConsistencyOut,
    FraudRiskAnalysisOut,
    RepairEstimateOut,
    VehicleDamageOut,
)
from app.schemas.ai_analysis import AiClaimAnalysisOut
from app.schemas.ai_pipeline import LiveAiAnalysisRunOut
from app.schemas.document import DocumentOut
from app.schemas.document_analysis import ClaimDocumentAnalysisOut, DocumentAnalysisOut, DocumentCompletenessOut
from app.schemas.document_consistency import DocumentConsistencyOut, EntityConsistencyOut
from app.schemas.entity_extraction import EntityCandidateOut, EntityExtractionResultOut
from app.schemas.evidence_duplication import ClaimEvidenceDuplicationOut, EvidenceDuplicationOut, EvidenceMatchOut
from app.schemas.evidence_quality import ClaimPhotoQualityOut, PhotoMeasurementsOut, PhotoQualityOut
from app.schemas.officer import AssignSurveyorRequest, DecisionCreate, SurveyorSummaryOut
from app.schemas.semantic_consistency import ClaimSemanticConsistencyOut, DocumentRefOut, SemanticConsistencyOut
from app.schemas.surveyor import SurveyorInspectionOut
from app.services import (
    ai_analysis,
    ai_pipeline,
    claim_decision,
    document_analysis,
    document_consistency,
    entity_extraction,
    evidence_duplication,
    evidence_quality,
    semantic_consistency,
    surveyor_assignment,
)
from app.services.claim_access import get_claim_or_403

router = APIRouter(prefix="/officer", tags=["officer"])

_officer_or_admin = require_roles("Claims Officer", "Admin")


@router.get("/surveyors", response_model=list[SurveyorSummaryOut])
def list_eligible_surveyors(
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Active Surveyor accounts eligible for claim assignment."""
    return crud_user.list_active_surveyors(db)


@router.post(
    "/claims/{claim_id}/assign-surveyor",
    response_model=SurveyorInspectionOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_surveyor(
    claim_id: str,
    payload: AssignSurveyorRequest,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Claims Officer/Admin assigns a Surveyor to a claim by creating the
    claim's first surveyor_inspections row - see
    services/surveyor_assignment.py for the full rule set."""
    return surveyor_assignment.assign_surveyor_to_claim(db, claim_id, payload.surveyor_employee_id)


@router.post(
    "/claims/{claim_id}/decision",
    response_model=ClaimDecisionAuditOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_decision(
    claim_id: str,
    payload: DecisionCreate,
    employee_id: str = Depends(require_claims_officer_employee_id),
    db: Session = Depends(get_db),
):
    """Claims Officer records the claim's final decision. Admin is
    intentionally not permitted here - see
    api/v1/deps.py::require_claims_officer_employee_id for why. The
    decision is always the human officer's own selection - AI signals, if
    any genuinely exist, are carried forward as supporting information
    only (see services/claim_decision.py)."""
    return claim_decision.record_decision_for_officer(db, employee_id, claim_id, payload)


@router.get("/claims", response_model=list[ClaimSummaryOut])
def list_claims_for_processing(
    claim_status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    return crud_claim.list_all(db, skip, limit, claim_status)


@router.get("/claims/{claim_id}")
def read_claim_processing_detail(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Aggregated claim-processing view: the claim plus documents,
    damage, repair estimates, surveyor findings, cross-document
    consistency, fraud risk, and prior decision audit history."""
    claim = get_claim_or_403(db, claim_id, current_user)
    return {
        "claim": ClaimOut.model_validate(claim),
        "documents": [DocumentOut.model_validate(d) for d in crud_document.list_by_claim(db, claim_id)],
        "vehicle_damage": [
            VehicleDamageOut.model_validate(d) for d in crud_vehicle_damage.list_by_claim(db, claim_id)
        ],
        "repair_estimates": [
            RepairEstimateOut.model_validate(r) for r in crud_repair_estimate.list_by_claim(db, claim_id)
        ],
        "surveyor_inspections": [
            SurveyorInspectionOut.model_validate(i) for i in crud_inspection.list_by_claim(db, claim_id)
        ],
        "cross_document_consistency": [
            CrossDocumentConsistencyOut.model_validate(c)
            for c in crud_consistency.list_by_claim(db, claim_id)
        ],
        "fraud_risk_analysis": [
            FraudRiskAnalysisOut.model_validate(r) for r in crud_fraud.list_by_claim(db, claim_id)
        ],
        "decision_audit": [
            ClaimDecisionAuditOut.model_validate(a) for a in crud_audit.list_by_claim(db, claim_id)
        ],
    }


@router.get("/claims/{claim_id}/ai-analysis", response_model=AiClaimAnalysisOut)
def read_ai_analysis(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Read-only aggregation of existing AI/ML artifacts for this claim -
    the Step 5.4 risk-fusion research prototype plus the fraud_risk_analysis/
    cross_document_consistency/repair_estimates tables. Computes nothing
    live and has no write path - see services/ai_analysis.py and
    docs/project_documentation/AI_BACKEND_INTEGRATION.md."""
    return ai_analysis.get_ai_analysis_for_claim(db, claim_id)


@router.post("/claims/{claim_id}/ai-analysis/run", response_model=LiveAiAnalysisRunOut)
def run_live_ai_analysis(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """On-demand live AI analysis for THIS claim's actual current data -
    the "NEW/LIVE CLAIM DATA -> AI processing -> AI result" pipeline that
    the read-only GET /ai-analysis endpoint (Step 5.8.10) does not
    provide. Analyze-only: has no write path, cannot touch
    Claim.Final_Decision/Approved_Amount, and its result is never
    persisted - see services/ai_pipeline.py and
    docs/project_documentation/LIVE_AI_PIPELINE.md."""
    return ai_pipeline.run_claim_ai_analysis(db, claim_id)


@router.post("/claims/{claim_id}/documents/analyze", response_model=ClaimDocumentAnalysisOut)
def analyze_claim_documents(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Step 5.8.12: OCRs every document currently on this claim and
    persists ONE claim-level document-completeness ratio onto each of
    those Document rows (the schema has no claim-level completeness
    column - see services/document_analysis.py and
    docs/project_documentation/DOCUMENT_COMPLETENESS_AND_OCR.md).
    Analysis-only: never touches Final_Decision, Approved_Amount, or
    claim_decision_audit, and never approves/rejects a claim."""
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    documents, results, completeness = document_analysis.analyze_claim_documents(db, claim)

    # Step 5.8.13-B: computed once for the whole claim - re-reads every
    # relevant document's already-persisted Extracted_Text (all just
    # written above), never re-runs OCR itself.
    consistency = document_consistency.compare_claim_documents(db, claim)

    def _consistency_out() -> DocumentConsistencyOut:
        return DocumentConsistencyOut(
            registration=EntityConsistencyOut(
                status=consistency.registration.status,
                structured_value=consistency.registration.structured_value,
                extracted_value=consistency.registration.extracted_value,
                matched_document_type=consistency.registration.matched_document_type,
                matched_document_id=consistency.registration.matched_document_id,
                explanation=consistency.registration.explanation,
            ),
            policy=EntityConsistencyOut(
                status=consistency.policy.status,
                structured_value=consistency.policy.structured_value,
                extracted_value=consistency.policy.extracted_value,
                matched_document_type=consistency.policy.matched_document_type,
                matched_document_id=consistency.policy.matched_document_id,
                explanation=consistency.policy.explanation,
            ),
        )

    def _entities_out(document, result) -> EntityExtractionResultOut:
        # Step 5.8.13-A: best-effort, deterministic, read-time-only - never
        # persisted, never compared against the claim's structured data.
        entities = entity_extraction.extract_entities(
            result.text, document_type=document.Document_Type, ocr_confidence=result.confidence
        )
        return EntityExtractionResultOut(
            status=entities.status,
            entities=[
                EntityCandidateOut(
                    entity_type=e.entity_type,
                    value=e.value,
                    normalized_value=e.normalized_value,
                    confidence=e.confidence,
                    source=e.source,
                    reason=e.reason,
                )
                for e in entities.entities
            ],
            limitations=entities.limitations,
        )

    return ClaimDocumentAnalysisOut(
        Claim_ID=claim_id,
        documents_analyzed=len(documents),
        documents=[
            DocumentAnalysisOut(
                Document_ID=document.Document_ID,
                Document_Type=document.Document_Type,
                extraction_status=result.status,
                extracted_text=result.text,
                ocr_confidence=result.confidence,
                mismatch_indicator=document.Document_Mismatch_Indicator,
                completeness=DocumentCompletenessOut(
                    available=completeness.available,
                    required_document_types=completeness.required,
                    present_document_types=completeness.present,
                    missing_document_types=completeness.missing,
                    completeness_ratio=completeness.ratio,
                    explanation=completeness.explanation,
                ),
                entities=_entities_out(document, result),
                consistency=_consistency_out(),
                limitations=result.limitations,
            )
            for document, result in zip(documents, results)
        ],
        completeness=DocumentCompletenessOut(
            available=completeness.available,
            required_document_types=completeness.required,
            present_document_types=completeness.present,
            missing_document_types=completeness.missing,
            completeness_ratio=completeness.ratio,
            explanation=completeness.explanation,
        ),
        consistency=_consistency_out(),
    )


@router.post("/claims/{claim_id}/documents/semantic-consistency", response_model=ClaimSemanticConsistencyOut)
def analyze_claim_semantic_consistency(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Step 5.8.13-C: read-only semantic narrative-consistency RESEARCH
    PROTOTYPE - compares this claim's FIR and Survey Report narrative text
    for a stated-location agreement/disagreement signal only (see
    services/semantic_consistency.py and
    docs/project_documentation/SEMANTIC_DOCUMENT_CONSISTENCY.md). This is
    NOT fraud detection, NOT a risk score, and is NOT wired into
    ai_pipeline.py - an investigative signal for a Claims Officer only.
    The existing Step 5.8.13-B deterministic registration/policy result is
    returned alongside it, UNCHANGED and un-merged, so neither dimension
    can silently override the other. Analysis-only: never touches
    Final_Decision, Approved_Amount, or claim_decision_audit, and never
    approves/rejects a claim."""
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    narrative = semantic_consistency.compare_claim_narrative(db, claim)
    deterministic = document_consistency.compare_claim_documents(db, claim)

    def _ref_out(ref):
        if ref is None:
            return None
        return DocumentRefOut(document_id=ref.document_id, document_type=ref.document_type)

    return ClaimSemanticConsistencyOut(
        Claim_ID=claim_id,
        narrative=SemanticConsistencyOut(
            document_a=_ref_out(narrative.document_a),
            document_b=_ref_out(narrative.document_b),
            relationship=narrative.relationship,
            confidence=narrative.confidence,
            explanation=narrative.explanation,
            limitations=narrative.limitations,
        ),
        deterministic=DocumentConsistencyOut(
            registration=EntityConsistencyOut(
                status=deterministic.registration.status,
                structured_value=deterministic.registration.structured_value,
                extracted_value=deterministic.registration.extracted_value,
                matched_document_type=deterministic.registration.matched_document_type,
                matched_document_id=deterministic.registration.matched_document_id,
                explanation=deterministic.registration.explanation,
            ),
            policy=EntityConsistencyOut(
                status=deterministic.policy.status,
                structured_value=deterministic.policy.structured_value,
                extracted_value=deterministic.policy.extracted_value,
                matched_document_type=deterministic.policy.matched_document_type,
                matched_document_id=deterministic.policy.matched_document_id,
                explanation=deterministic.policy.explanation,
            ),
        ),
    )


@router.post("/claims/{claim_id}/evidence/duplication-check", response_model=ClaimEvidenceDuplicationOut)
def check_claim_evidence_duplication(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Step 5.8.14: read-only evidence duplication / reuse check - compares
    each photo on this claim with every other stored evidence photo (this
    claim and other claims) using SHA-256 and a 64-bit difference hash (see
    services/evidence_duplication.py and
    docs/project_documentation/EVIDENCE_DUPLICATION.md). This is NOT fraud
    detection, NOT a risk score, and is NOT wired into ai_pipeline.py.
    Analysis-only: never writes Evidence.Duplicate_Evidence_Indicator,
    never touches Final_Decision, Approved_Amount, or claim_decision_audit."""
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    result = evidence_duplication.check_claim_evidence(db, claim)
    return ClaimEvidenceDuplicationOut(
        Claim_ID=claim_id,
        photos_checked=result.photos_checked,
        photos_compared_against=result.photos_compared_against,
        results=[
            EvidenceDuplicationOut(
                evidence_id=r.evidence_id,
                evidence_type=r.evidence_type,
                file_name=r.file_name,
                status=r.status,
                matches=[
                    EvidenceMatchOut(
                        evidence_id=m.evidence_id,
                        claim_id=m.claim_id,
                        same_claim=m.same_claim,
                        match_type=m.match_type,
                        hash_distance=m.hash_distance,
                    )
                    for m in r.matches
                ],
                explanation=r.explanation,
            )
            for r in result.results
        ],
        limitations=result.limitations,
    )


@router.post("/claims/{claim_id}/evidence/quality-check", response_model=ClaimPhotoQualityOut)
def check_claim_photo_quality(
    claim_id: str,
    current_user: AuthenticationUser = Depends(_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Step 5.8.15: read-only evidence photo quality check - measures each
    photo on this claim for resolution, brightness, contrast and blur and
    reports plain flags (see services/evidence_quality.py and
    docs/project_documentation/EVIDENCE_PHOTO_QUALITY.md). NOT fraud
    detection, NOT a risk score, NOT wired into ai_pipeline.py.
    Analysis-only: never writes Evidence.Image_Quality, never touches
    Final_Decision, Approved_Amount, or claim_decision_audit."""
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    result = evidence_quality.check_claim_photo_quality(db, claim)
    return ClaimPhotoQualityOut(
        Claim_ID=claim_id,
        photos_checked=result.photos_checked,
        results=[
            PhotoQualityOut(
                evidence_id=r.evidence_id,
                evidence_type=r.evidence_type,
                file_name=r.file_name,
                status=r.status,
                flags=r.flags,
                measurements=(
                    PhotoMeasurementsOut(
                        width=r.measurements.width,
                        height=r.measurements.height,
                        brightness=r.measurements.brightness,
                        contrast=r.measurements.contrast,
                        reblur_ratio=r.measurements.reblur_ratio,
                    )
                    if r.measurements
                    else None
                ),
                explanation=r.explanation,
            )
            for r in result.results
        ],
        limitations=result.limitations,
    )
