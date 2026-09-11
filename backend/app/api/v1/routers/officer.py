from fastapi import APIRouter, Depends, Query, status
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
from app.schemas.officer import AssignSurveyorRequest, DecisionCreate, SurveyorSummaryOut
from app.schemas.surveyor import SurveyorInspectionOut
from app.services import ai_analysis, ai_pipeline, claim_decision, surveyor_assignment
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
