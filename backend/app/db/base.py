"""Imports every ORM model so Base.metadata contains all 15 application
tables. Import this module (not app.db.base_class directly) wherever the
full metadata is needed - Alembic's env.py and test setup/teardown.
"""

from app.db.base_class import Base  # noqa: F401
from app.db_models.accident import Accident  # noqa: F401
from app.db_models.authentication_user import AuthenticationUser  # noqa: F401
from app.db_models.claim import Claim  # noqa: F401
from app.db_models.claim_decision_audit import ClaimDecisionAudit  # noqa: F401
from app.db_models.cross_document_consistency import CrossDocumentConsistency  # noqa: F401
from app.db_models.customer import Customer  # noqa: F401
from app.db_models.document import Document  # noqa: F401
from app.db_models.evidence import Evidence  # noqa: F401
from app.db_models.fraud_risk_analysis import FraudRiskAnalysis  # noqa: F401
from app.db_models.policy import Policy  # noqa: F401
from app.db_models.repair_estimate import RepairEstimate  # noqa: F401
from app.db_models.surveyor_inspection import SurveyorInspection  # noqa: F401
from app.db_models.tp_claim import TPClaim  # noqa: F401
from app.db_models.vehicle import Vehicle  # noqa: F401
from app.db_models.vehicle_damage import VehicleDamage  # noqa: F401
