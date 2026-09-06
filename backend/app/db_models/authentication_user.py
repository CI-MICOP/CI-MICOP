from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String

from app.db.base_class import Base


class AuthenticationUser(Base):
    """Login accounts for all roles (Customer, Surveyor, Claims Officer, Admin).

    Source: CI_MICOP_Authentication_Users.xlsx (the authoritative file - see
    Step 2 report for why the older 01_authentication_users.xlsx was not used).
    Employee_ID identifies Surveyor/Claims Officer staff; no separate
    Employee table is created per the approved 15-table design.
    """

    __tablename__ = "authentication_users"

    User_ID = Column(String(30), primary_key=True)
    Username = Column(String(100), unique=True, nullable=False, index=True)
    Password_Hash = Column(String(255), nullable=False)
    Role = Column(String(30), nullable=False, index=True)
    Customer_ID = Column(String(30), ForeignKey("customers.Customer_ID"), nullable=True)
    # Staff identifier for Surveyor/Claims Officer accounts. Unique (when
    # present) so surveyor_inspections.Surveyor_ID and
    # claim_decision_audit.Claims_Officer_ID can reference it. Null for
    # Customer accounts.
    Employee_ID = Column(String(30), unique=True, nullable=True)
    Email = Column(String(255), nullable=False)
    Phone = Column(String(20), nullable=False)
    Account_Status = Column(String(30), nullable=False)
    Login_Status = Column(String(30), nullable=False)
    Last_Login = Column(DateTime, nullable=True)
    Created_Date = Column(Date, nullable=False)
    Failed_Login_Count = Column(Integer, nullable=False, default=0)
    Permission_Level = Column(Integer, nullable=False)
    # Present in the spec and in the older dataset file, but not populated
    # in the authoritative CI_MICOP_Authentication_Users.xlsx - kept
    # nullable for forward compatibility. See Step 2 report.
    Insurer_Code = Column(String(30), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "Role IN ('Customer', 'Surveyor', 'Claims Officer', 'Admin')",
            name="ck_authentication_users_role",
        ),
    )
