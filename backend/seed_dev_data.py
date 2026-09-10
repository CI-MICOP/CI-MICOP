from datetime import date, datetime, time
from decimal import Decimal

import bcrypt

from app.db.session import SessionLocal
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.customer import Customer
from app.db_models.vehicle import Vehicle
from app.db_models.policy import Policy
from app.db_models.claim import Claim
from app.db_models.accident import Accident
from app.db_models.document import Document
from app.db_models.vehicle_damage import VehicleDamage
from app.db_models.repair_estimate import RepairEstimate
from app.db_models.evidence import Evidence
from app.db_models.surveyor_inspection import SurveyorInspection
from app.db_models.cross_document_consistency import CrossDocumentConsistency
from app.db_models.fraud_risk_analysis import FraudRiskAnalysis
from app.db_models.claim_decision_audit import ClaimDecisionAudit
from app.db_models.tp_claim import TPClaim


# ============================================================
# CI-MICOP DEVELOPMENT SEED DATA
# ============================================================

CUSTOMER_ID = "DEV-CUST-001"
VEHICLE_ID = "DEV-VEH-001"
POLICY_ID = "DEV-POL-001"
CLAIM_ID = "DEV-CLM-001"

SURVEYOR_EMPLOYEE_ID = "DEV-SURV-001"
OFFICER_EMPLOYEE_ID = "DEV-OFF-001"

PASSWORD = "CiMicop@123"


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


# ============================================================
# INSERT ONLY IF RECORD DOES NOT ALREADY EXIST
# ============================================================

def add_if_missing(db, model, pk_field, pk_value, **kwargs):
    obj = (
        db.query(model)
        .filter(getattr(model, pk_field) == pk_value)
        .first()
    )

    if obj:
        return obj

    obj = model(**kwargs)
    db.add(obj)
    return obj


# ============================================================
# MAIN
# ============================================================

def main():
    db = SessionLocal()

    try:

        # ====================================================
        # 1. CUSTOMER
        # ====================================================

        customer = add_if_missing(
            db,
            Customer,
            "Customer_ID",
            CUSTOMER_ID,

            Customer_ID=CUSTOMER_ID,
            Customer_Name="Arun Kumar",
            Date_of_Birth=date(1998, 5, 12),
            Age=28,
            Gender="Male",
            Phone="9000000001",
            Email="dev.customer@ci-micop.local",
            Address="Chennai, Tamil Nadu",
            City="Chennai",
            State="Tamil Nadu",
            Pincode="600001",
            Occupation="Software Engineer",
            Driving_Experience_Years=8,
            Customer_Type="Individual",
            Previous_Claim_Count=0,
            Driver_Age_Code="A28",
            Driver_Experience_Code="E08",
            Driver_Qualification_Code="GRAD",
            Driver_Type_Code="OWNER",
        )

        # Force customer INSERT before dependent records.
        db.flush()


        # ====================================================
        # 2. VEHICLE
        # ====================================================
        # Policy_ID is temporarily NULL because Vehicle and
        # Policy have a circular foreign-key relationship.
        # ====================================================

        vehicle = add_if_missing(
            db,
            Vehicle,
            "Vehicle_ID",
            VEHICLE_ID,

            Vehicle_ID=VEHICLE_ID,
            Customer_ID=CUSTOMER_ID,
            Policy_ID=None,

            Vehicle_Type="Private Car",
            Vehicle_Subtype=None,

            Registration_Number="TN01AB0001",
            Chassis_Number="DEVCHASSIS0001",
            Engine_Number="DEVENGINE0001",

            Vehicle_Color="White",

            Make="Hyundai",
            Make_Code="HYU",
            Model="i20",
            Variant="Sportz",

            Manufacturing_Year=2022,
            Registration_Year=2022,
            Vehicle_Age=4,

            Fuel_Type="Petrol",
            Engine_CC=1197,
            CC_PCC_GVW_Code="1197",

            Vehicle_Value=Decimal("750000.00"),

            Usage_Type="Private",

            GVW_KG=None,
            Load_Capacity_KG=None,
            Seating_Capacity=5,

            Permit_Code=None,
            Nature_of_Goods_Code=None,

            Road_Type_Code="URBAN",
            Vehicle_Driven_By_Code="OWNER",
            RTA_Location_Code="TN01",
            Class_Code="PC",
            Zone_Code="A",

            Previous_Claim_Count=0,

            Policy_Start_Date=date(2026, 1, 1),
            Policy_End_Date=date(2027, 1, 1),
        )

        # Force vehicle INSERT.
        db.flush()


        # ====================================================
        # 3. POLICY
        # ====================================================

        policy = add_if_missing(
            db,
            Policy,
            "Policy_ID",
            POLICY_ID,

            Policy_ID=POLICY_ID,
            Customer_ID=CUSTOMER_ID,
            Vehicle_ID=VEHICLE_ID,

            Policy_Number="DEV-POLICY-001",

            Policy_Type="Comprehensive",
            Policy_Code="COMP",
            Coverage_Type="Own Damage + TP",

            Class_Code="PC",

            Policy_Start_Date=date(2026, 1, 1),
            Policy_End_Date=date(2027, 1, 1),

            Policy_Year="2026",

            Premium_Amount=Decimal("18500.00"),
            Sum_Insured=Decimal("700000.00"),
            IDV=Decimal("680000.00"),
            Deductible_Amount=Decimal("1000.00"),

            No_Claim_Bonus=Decimal("20.00"),
            NCB_Flag=True,

            Policy_Status="Active",
            Renewal_Status="Pending",

            Office_Code="CHN001",

            Endorsement_Flag=False,
            Endorsement_Number=None,

            Anti_Theft_Discount_Flag=False,
            Auto_Association_Discount_Flag=False,
            Voluntary_Excess_Discount_Flag=False,
            Vintage_Car_Discount_Flag=False,
            Own_Premises_Discount_Flag=False,
            Special_Design_Discount_Flag=False,
            Side_Car_Discount_Flag=False,
            Special_Rating_Discount_Flag=False,

            TPPD_Statutory_Cover_Flag=True,
        )

        # Complete Vehicle <-> Policy relationship.
        vehicle.Policy_ID = POLICY_ID

        # Force Policy + Vehicle update.
        db.flush()


        # ====================================================
        # 4. CLAIM
        # ====================================================

        claim = add_if_missing(
            db,
            Claim,
            "Claim_ID",
            CLAIM_ID,

            Claim_ID=CLAIM_ID,

            Policy_ID=POLICY_ID,
            Customer_ID=CUSTOMER_ID,
            Vehicle_ID=VEHICLE_ID,

            Claim_Number="DEV-CLAIM-001",
            Claim_Number_Child=None,

            Claim_Date=date(2026, 8, 20),
            Claim_Year="2026",

            Claim_Type="Own Damage",

            Claim_Amount=Decimal("125000.00"),
            Approved_Amount=Decimal("0.00"),

            Claim_Status="Under Review",

            Claim_Description=(
                "Front-side collision damage reported by the customer."
            ),

            Claims_History_Code="C0",
            Incurred_Claims_Code="I1",
            Nature_of_Loss_Code="COL",
            Insurer_NOL_Code="NOL1",

            TPPD_Statutory_Cover_Flag=True,

            Claim_Intimation_Date=date(2026, 8, 20),
            Date_of_Disbursement=date(2026, 8, 25),

            Place_of_Accident="Chennai",
            Accident_Pincode="600001",

            Claim_Processing_Days=5,
            Repair_Duration_Days=7,

            Final_Decision="Pending",

            Decision_Date=date(2026, 8, 25),

            Decision_Reason="Pending human review.",

            TP_Amount_Claimed=Decimal("0.00"),
            TP_Claims_Paid=Decimal("0.00"),
            TP_Awards_Paid=Decimal("0.00"),
            TP_Expenses_Paid=Decimal("0.00"),
            TP_Interest_Paid=Decimal("0.00"),

            Wider_Legal_Liability_Amount=Decimal("0.00"),

            PA_Owner_Driver_Amount=Decimal("0.00"),
            PA_Others_Amount=Decimal("0.00"),

            Nature_of_Injury_Code="NONE",

            Interim_Award_Flag=False,

            Settlement_Basis_Code="PENDING",

            Fatal_NonFatal_Flag=False,

            Open_Provision_Main=Decimal("125000.00"),
            Open_Provision_Expenses=Decimal("0.00"),
            Open_Provision_Interest=Decimal("0.00"),

            Closing_Provision_Main=Decimal("0.00"),
            Closing_Provision_Expenses=Decimal("0.00"),
            Closing_Provision_Interest=Decimal("0.00"),
        )

        # IMPORTANT:
        # Force Claim INSERT before Accident, Document,
        # Evidence, Damage, etc.
        db.flush()


        # ====================================================
        # 5. ACCIDENT
        # ====================================================

        add_if_missing(
            db,
            Accident,
            "Accident_ID",
            "DEV-ACC-001",

            Accident_ID="DEV-ACC-001",
            Claim_ID=CLAIM_ID,

            Accident_Date=date(2026, 8, 20),
            Accident_Time=time(18, 30),

            Accident_Location="Anna Salai, Chennai",
            Accident_City="Chennai",
            Accident_State="Tamil Nadu",
            Accident_Pincode="600002",

            Accident_Type="Collision",

            Accident_Description=(
                "Vehicle collided with another vehicle at an urban intersection."
            ),

            Weather_Condition="Clear",
            Road_Condition="Dry",

            Road_Type_Code="URBAN",

            Police_Report_Available=True,
            FIR_Number="DEV-FIR-001",

            Third_Party_Involved=True,
            Injury_Reported=False,
            Witness_Available=True,
        )

        db.flush()


        # ====================================================
        # 6. DOCUMENT
        # ====================================================

        add_if_missing(
            db,
            Document,
            "Document_ID",
            "DEV-DOC-001",

            Document_ID="DEV-DOC-001",
            Claim_ID=CLAIM_ID,

            Document_Type="FIR",
            Document_Name="DEV-FIR-001.pdf",

            Document_Submitted_Date=date(2026, 8, 21),

            Document_Status="Submitted",

            OCR_Confidence_Score=Decimal("0.96"),

            Extracted_Text=(
                "FIR extract for the reported motor accident."
            ),

            Document_Completeness=Decimal("0.95"),

            Document_Mismatch_Indicator=False,

            Verification_Status="Verified",
        )

        db.flush()


        # ====================================================
        # 7. VEHICLE DAMAGE
        # ====================================================

        add_if_missing(
            db,
            VehicleDamage,
            "Damage_ID",
            "DEV-DMG-001",

            Damage_ID="DEV-DMG-001",
            Claim_ID=CLAIM_ID,
            Vehicle_ID=VEHICLE_ID,

            Damage_Type="Collision",
            Damaged_Part="Front Bumper",
            Damage_Severity="Moderate",
            Damage_Location="Front",

            Estimated_Damage_Cost=Decimal("45000.00"),

            Repair_or_Replace="Replace",

            Photo_Evidence_Available=True,

            Vehicle_Damage_Mismatch_Indicator=False,

            Damage_Description=(
                "Front bumper and adjacent panel damage."
            ),
        )

        db.flush()


        # ====================================================
        # 8. REPAIR ESTIMATE
        # ====================================================

        add_if_missing(
            db,
            RepairEstimate,
            "Estimate_ID",
            "DEV-EST-001",

            Estimate_ID="DEV-EST-001",
            Claim_ID=CLAIM_ID,
            Vehicle_ID=VEHICLE_ID,

            Garage_ID="DEV-GARAGE-001",

            Estimate_Date=date(2026, 8, 22),

            Repair_Estimate=Decimal("120000.00"),
            Repair_Cost=Decimal("112000.00"),

            Parts_Cost=Decimal("70000.00"),
            Labour_Cost=Decimal("22000.00"),
            Painting_Cost=Decimal("20000.00"),

            Replacement_Parts_Count=2,
            Repaired_Parts_Count=3,

            Estimated_Repair_Days=7,
            Actual_Repair_Days=7,

            Excessive_Claim_Amount_Indicator=False,

            Estimate_Anomaly_Score=Decimal("0.1200"),
        )

        db.flush()


        # ====================================================
        # 9. EVIDENCE
        # ====================================================

        add_if_missing(
            db,
            Evidence,
            "Evidence_ID",
            "DEV-EVD-001",

            Evidence_ID="DEV-EVD-001",
            Claim_ID=CLAIM_ID,

            Evidence_Type="Accident Photo",

            File_Name="dev-accident-photo-01.jpg",

            Evidence_Date=date(2026, 8, 20),

            Evidence_Source="Customer",

            Image_Quality=Decimal("0.92"),

            Vehicle_Damage_Detected=True,

            Damage_Severity="Moderate",

            Location_Match=True,

            Duplicate_Evidence_Indicator=False,

            Evidence_Confidence_Score=Decimal("0.91"),

            Verification_Status="Verified",
        )

        db.flush()


        # ====================================================
        # 10. AUTHENTICATION USERS
        # ====================================================
        # SurveyorInspection references AuthenticationUser.Employee_ID,
        # and ClaimDecisionAudit does the same for the Claims Officer.
        # Therefore these users MUST be flushed before inserting those
        # dependent records.

        add_if_missing(
            db, AuthenticationUser, "User_ID", "DEV-USER-CUST",
            User_ID="DEV-USER-CUST", Username="dev_customer",
            Password_Hash=hash_password(PASSWORD), Role="Customer",
            Customer_ID=CUSTOMER_ID, Employee_ID=None,
            Email="dev.customer@ci-micop.local", Phone="9000000001",
            Account_Status="Active", Login_Status="Logged Out",
            Last_Login=None, Created_Date=date(2026, 9, 8),
            Failed_Login_Count=0, Permission_Level=1, Insurer_Code=None,
        )

        add_if_missing(
            db, AuthenticationUser, "User_ID", "DEV-USER-SURV",
            User_ID="DEV-USER-SURV", Username="dev_surveyor",
            Password_Hash=hash_password(PASSWORD), Role="Surveyor",
            Customer_ID=None, Employee_ID=SURVEYOR_EMPLOYEE_ID,
            Email="dev.surveyor@ci-micop.local", Phone="9000000002",
            Account_Status="Active", Login_Status="Logged Out",
            Last_Login=None, Created_Date=date(2026, 9, 8),
            Failed_Login_Count=0, Permission_Level=2, Insurer_Code=None,
        )

        add_if_missing(
            db, AuthenticationUser, "User_ID", "DEV-USER-OFF",
            User_ID="DEV-USER-OFF", Username="dev_officer",
            Password_Hash=hash_password(PASSWORD), Role="Claims Officer",
            Customer_ID=None, Employee_ID=OFFICER_EMPLOYEE_ID,
            Email="dev.officer@ci-micop.local", Phone="9000000003",
            Account_Status="Active", Login_Status="Logged Out",
            Last_Login=None, Created_Date=date(2026, 9, 8),
            Failed_Login_Count=0, Permission_Level=3, Insurer_Code=None,
        )

        add_if_missing(
            db, AuthenticationUser, "User_ID", "DEV-USER-ADM",
            User_ID="DEV-USER-ADM", Username="dev_admin",
            Password_Hash=hash_password(PASSWORD), Role="Admin",
            Customer_ID=None, Employee_ID=None,
            Email="dev.admin@ci-micop.local", Phone="9000000004",
            Account_Status="Active", Login_Status="Logged Out",
            Last_Login=None, Created_Date=date(2026, 9, 8),
            Failed_Login_Count=0, Permission_Level=4, Insurer_Code=None,
        )

        # Critical FK flush: Employee_ID values must exist in
        # authentication_users before SurveyorInspection/Audit rows.
        db.flush()


        # ====================================================
        # 11. SURVEYOR INSPECTION
        # ====================================================

        add_if_missing(
            db,
            SurveyorInspection,
            "Inspection_ID",
            "DEV-INSP-001",

            Inspection_ID="DEV-INSP-001",
            Claim_ID=CLAIM_ID,

            Surveyor_ID=SURVEYOR_EMPLOYEE_ID,

            Inspection_Date=date(2026, 8, 23),

            Inspection_Location="Chennai",

            Vehicle_Condition="Damaged",

            Damage_Observed="Yes",

            Damage_Severity="Moderate",

            Parts_Required=2,

            Repair_Recommendation="Repair",

            Surveyor_Comments=(
                "Damage is consistent with the reported collision."
            ),

            Inspection_Status="Completed",

            Survey_Report_Submitted=True,

            Surveyor_Confidence_Score=Decimal("0.90"),
        )

        db.flush()


        # ====================================================
        # 12. CROSS-DOCUMENT CONSISTENCY
        # ====================================================

        add_if_missing(
            db,
            CrossDocumentConsistency,
            "Consistency_ID",
            "DEV-CON-001",

            Consistency_ID="DEV-CON-001",
            Claim_ID=CLAIM_ID,

            Customer_Statement_Match="Match",
            FIR_Match="Match",
            Surveyor_Report_Match="Match",
            Repair_Estimate_Match="Match",

            Accident_Date_Match="Match",
            Accident_Location_Match="Match",

            Vehicle_Details_Match="Match",
            Damage_Description_Match="Match",

            Claim_Amount_Match="Partial",

            Document_Consistency_Score=Decimal("0.9200"),

            Document_Mismatch_Indicator=False,

            Accident_Details_Mismatch_Indicator=False,

            Vehicle_Damage_Mismatch_Indicator=False,

            Overall_Consistency_Status="Partial",
        )

        db.flush()


        # ====================================================
        # 13. FRAUD RISK ANALYSIS
        # ====================================================

        add_if_missing(
            db,
            FraudRiskAnalysis,
            "Risk_ID",
            "DEV-RISK-001",

            Risk_ID="DEV-RISK-001",
            Claim_ID=CLAIM_ID,

            Duplicate_Claim_Indicator=False,

            Previous_Similar_Claim=False,

            Suspicious_Garage_Indicator=False,

            Claim_Immediately_After_Policy_Indicator=False,

            Excessive_Claim_Amount_Indicator=False,

            Document_Mismatch_Indicator=False,

            Vehicle_Damage_Mismatch_Indicator=False,

            Accident_Details_Mismatch_Indicator=False,

            Evidence_Reuse_Indicator=False,

            Fraud_Risk_Score=Decimal("12.00"),

            Anomaly_Score=Decimal("0.0800"),

            Overall_Risk_Score=Decimal("12.00"),

            Risk_Category="Low",

            Fraud_Label=0,
        )

        db.flush()


        # ====================================================
        # 14. THIRD-PARTY CLAIM
        # ====================================================

        add_if_missing(
            db,
            TPClaim,
            "TP_Claim_ID",
            "DEV-TP-001",

            TP_Claim_ID="DEV-TP-001",
            Claim_ID=CLAIM_ID,

            TP_Amount_Claimed=Decimal("0.00"),
            TP_Claims_Paid=Decimal("0.00"),
            TP_Awards_Paid=Decimal("0.00"),
            TP_Expenses_Paid=Decimal("0.00"),
            TP_Interest_Paid=Decimal("0.00"),

            Wider_Legal_Liability_Amount=Decimal("0.00"),

            PA_Owner_Driver_Amount=Decimal("0.00"),
            PA_Others_Amount=Decimal("0.00"),

            Open_Provision_Main=Decimal("0.00"),
            Open_Provision_Expenses=Decimal("0.00"),
            Open_Provision_Interest=Decimal("0.00"),

            Closing_Provision_Main=Decimal("0.00"),
            Closing_Provision_Expenses=Decimal("0.00"),
            Closing_Provision_Interest=Decimal("0.00"),
        )

        db.flush()


        # ====================================================
        # 15. CLAIM DECISION AUDIT
        # ====================================================

        add_if_missing(
            db,
            ClaimDecisionAudit,
            "Audit_ID",
            "DEV-AUD-001",

            Audit_ID="DEV-AUD-001",

            Claim_ID=CLAIM_ID,

            Claims_Officer_ID=OFFICER_EMPLOYEE_ID,

            AI_Recommendation="Review",

            AI_Confidence_Score=Decimal("0.8200"),

            Human_Review_Required=True,

            Final_Decision="Pending",

            Decision_Reason=(
                "AI signals are advisory; final decision requires officer review."
            ),

            Approved_Amount=Decimal("0.00"),

            Decision_Date=date(2026, 8, 25),

            Escalation_Status="Not Escalated",

            Escalated_To=None,

            Officer_Comments=(
                "Development integration test record."
            ),

            Audit_Action="Created",

            Audit_Timestamp=datetime(
                2026,
                8,
                25,
                10,
                0,
                0,
            ),
        )

        db.flush()


        # ====================================================
        # FINAL COMMIT
        # ====================================================

        db.commit()


        # ====================================================
        # SUCCESS MESSAGE
        # ====================================================

        print()
        print("=" * 60)
        print("CI-MICOP DEVELOPMENT DATA SEEDED SUCCESSFULLY")
        print("=" * 60)

        print()
        print("LOGIN CREDENTIALS")
        print("-" * 60)

        print("Customer       : dev_customer / CiMicop@123")
        print("Surveyor       : dev_surveyor / CiMicop@123")
        print("Claims Officer : dev_officer / CiMicop@123")
        print("Admin          : dev_admin / CiMicop@123")

        print()
        print("TEST CLAIM")
        print("-" * 60)

        print("Claim_ID       : DEV-CLM-001")
        print("Claim_Number   : DEV-CLAIM-001")

        print()
        print("=" * 60)


    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()