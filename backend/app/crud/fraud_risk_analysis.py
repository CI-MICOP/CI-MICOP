from sqlalchemy.orm import Session

from app.db_models.fraud_risk_analysis import FraudRiskAnalysis


def list_by_claim(db: Session, claim_id: str) -> list[FraudRiskAnalysis]:
    return (
        db.query(FraudRiskAnalysis)
        .filter(FraudRiskAnalysis.Claim_ID == claim_id)
        .order_by(FraudRiskAnalysis.Risk_ID)
        .all()
    )
