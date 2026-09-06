from sqlalchemy import Column, ForeignKey, Numeric, String

from app.db.base_class import Base


class TPClaim(Base):
    """Third-party claim financials. The current dataset has exactly one
    row per referenced Claim_ID (186 rows / 186 distinct claims), but
    Claim_ID is intentionally NOT unique here so a claim can carry more
    than one TP record in the future (e.g. amended TP claims)."""

    __tablename__ = "tp_claims"

    TP_Claim_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    TP_Amount_Claimed = Column(Numeric(14, 2), nullable=False)
    TP_Claims_Paid = Column(Numeric(14, 2), nullable=False)
    TP_Awards_Paid = Column(Numeric(14, 2), nullable=False)
    TP_Expenses_Paid = Column(Numeric(14, 2), nullable=False)
    TP_Interest_Paid = Column(Numeric(14, 2), nullable=False)
    Wider_Legal_Liability_Amount = Column(Numeric(14, 2), nullable=False)
    PA_Owner_Driver_Amount = Column(Numeric(14, 2), nullable=False)
    PA_Others_Amount = Column(Numeric(14, 2), nullable=False)
    Open_Provision_Main = Column(Numeric(14, 2), nullable=False)
    Open_Provision_Expenses = Column(Numeric(14, 2), nullable=False)
    Open_Provision_Interest = Column(Numeric(14, 2), nullable=False)
    Closing_Provision_Main = Column(Numeric(14, 2), nullable=False)
    Closing_Provision_Expenses = Column(Numeric(14, 2), nullable=False)
    Closing_Provision_Interest = Column(Numeric(14, 2), nullable=False)
