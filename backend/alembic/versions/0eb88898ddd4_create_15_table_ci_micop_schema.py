"""create 15 table ci-micop schema

Revision ID: 0eb88898ddd4
Revises:
Create Date: 2026-09-06

Creates the complete Step 2 application schema: all 15 CI-MICOP tables,
their primary keys, foreign keys, unique constraints, and indexes.

Tables are created in dependency order so every FK target already exists
at creation time, except for the vehicles <-> policies circular
reference: vehicles.Policy_ID is created without its foreign key, and
that constraint is added afterward via a trailing ALTER TABLE (mirrors
SQLAlchemy's use_alter=True behavior on Vehicle.Policy_ID). See
database/schema.sql and backend/app/db_models/ for the same schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0eb88898ddd4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------
    # 1. customers
    # ------------------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("Customer_ID", sa.String(30), primary_key=True),
        sa.Column("Customer_Name", sa.String(150), nullable=False),
        sa.Column("Date_of_Birth", sa.Date(), nullable=False),
        sa.Column("Age", sa.Integer(), nullable=False),
        sa.Column("Gender", sa.String(20), nullable=False),
        sa.Column("Phone", sa.String(20), nullable=False),
        sa.Column("Email", sa.String(255), nullable=False),
        sa.Column("Address", sa.String(255), nullable=False),
        sa.Column("City", sa.String(100), nullable=False),
        sa.Column("State", sa.String(100), nullable=False),
        sa.Column("Pincode", sa.String(10), nullable=False),
        sa.Column("Occupation", sa.String(50), nullable=False),
        sa.Column("Driving_Experience_Years", sa.Integer(), nullable=False),
        sa.Column("Customer_Type", sa.String(30), nullable=False),
        sa.Column("Previous_Claim_Count", sa.Integer(), nullable=False),
        sa.Column("Driver_Age_Code", sa.String(10), nullable=False),
        sa.Column("Driver_Experience_Code", sa.String(10), nullable=False),
        sa.Column("Driver_Qualification_Code", sa.String(10), nullable=False),
        sa.Column("Driver_Type_Code", sa.String(10), nullable=False),
    )
    op.create_index("ix_customers_City", "customers", ["City"])
    op.create_index("ix_customers_State", "customers", ["State"])
    op.create_index("ix_customers_Pincode", "customers", ["Pincode"])

    # ------------------------------------------------------------
    # 2. authentication_users
    # ------------------------------------------------------------
    op.create_table(
        "authentication_users",
        sa.Column("User_ID", sa.String(30), primary_key=True),
        sa.Column("Username", sa.String(100), nullable=False, unique=True),
        sa.Column("Password_Hash", sa.String(255), nullable=False),
        sa.Column("Role", sa.String(30), nullable=False),
        sa.Column("Customer_ID", sa.String(30), sa.ForeignKey("customers.Customer_ID"), nullable=True),
        sa.Column("Employee_ID", sa.String(30), nullable=True, unique=True),
        sa.Column("Email", sa.String(255), nullable=False),
        sa.Column("Phone", sa.String(20), nullable=False),
        sa.Column("Account_Status", sa.String(30), nullable=False),
        sa.Column("Login_Status", sa.String(30), nullable=False),
        sa.Column("Last_Login", sa.DateTime(), nullable=True),
        sa.Column("Created_Date", sa.Date(), nullable=False),
        sa.Column("Failed_Login_Count", sa.Integer(), nullable=False),
        sa.Column("Permission_Level", sa.Integer(), nullable=False),
        sa.Column("Insurer_Code", sa.String(30), nullable=True),
        sa.CheckConstraint(
            "\"Role\" IN ('Customer', 'Surveyor', 'Claims Officer', 'Admin')",
            name="ck_authentication_users_role",
        ),
    )
    op.create_index("ix_authentication_users_Role", "authentication_users", ["Role"])

    # ------------------------------------------------------------
    # 3. vehicles (Policy_ID nullable, FK added after policies exists)
    # ------------------------------------------------------------
    op.create_table(
        "vehicles",
        sa.Column("Vehicle_ID", sa.String(30), primary_key=True),
        sa.Column("Customer_ID", sa.String(30), sa.ForeignKey("customers.Customer_ID"), nullable=False),
        sa.Column("Policy_ID", sa.String(30), nullable=True),
        sa.Column("Vehicle_Type", sa.String(50), nullable=False),
        sa.Column("Vehicle_Subtype", sa.String(50), nullable=True),
        sa.Column("Registration_Number", sa.String(30), nullable=False, unique=True),
        sa.Column("Chassis_Number", sa.String(30), nullable=False, unique=True),
        sa.Column("Engine_Number", sa.String(30), nullable=False, unique=True),
        sa.Column("Vehicle_Color", sa.String(30), nullable=False),
        sa.Column("Make", sa.String(50), nullable=False),
        sa.Column("Make_Code", sa.String(20), nullable=False),
        sa.Column("Model", sa.String(50), nullable=False),
        sa.Column("Variant", sa.String(30), nullable=False),
        sa.Column("Manufacturing_Year", sa.Integer(), nullable=False),
        sa.Column("Registration_Year", sa.Integer(), nullable=False),
        sa.Column("Vehicle_Age", sa.Integer(), nullable=False),
        sa.Column("Fuel_Type", sa.String(20), nullable=False),
        sa.Column("Engine_CC", sa.Integer(), nullable=False),
        sa.Column("CC_PCC_GVW_Code", sa.String(20), nullable=False),
        sa.Column("Vehicle_Value", sa.Numeric(14, 2), nullable=False),
        sa.Column("Usage_Type", sa.String(30), nullable=False),
        sa.Column("GVW_KG", sa.Integer(), nullable=True),
        sa.Column("Load_Capacity_KG", sa.Integer(), nullable=True),
        sa.Column("Seating_Capacity", sa.Integer(), nullable=False),
        sa.Column("Permit_Code", sa.String(20), nullable=True),
        sa.Column("Nature_of_Goods_Code", sa.String(20), nullable=True),
        sa.Column("Road_Type_Code", sa.String(20), nullable=False),
        sa.Column("Vehicle_Driven_By_Code", sa.String(20), nullable=False),
        sa.Column("RTA_Location_Code", sa.String(20), nullable=False),
        sa.Column("Class_Code", sa.String(20), nullable=False),
        sa.Column("Zone_Code", sa.String(20), nullable=False),
        sa.Column("Previous_Claim_Count", sa.Integer(), nullable=False),
        sa.Column("Policy_Start_Date", sa.Date(), nullable=False),
        sa.Column("Policy_End_Date", sa.Date(), nullable=False),
    )
    op.create_index("ix_vehicles_Customer_ID", "vehicles", ["Customer_ID"])
    op.create_index("ix_vehicles_Policy_ID", "vehicles", ["Policy_ID"])

    # ------------------------------------------------------------
    # 4. policies
    # ------------------------------------------------------------
    op.create_table(
        "policies",
        sa.Column("Policy_ID", sa.String(30), primary_key=True),
        sa.Column("Customer_ID", sa.String(30), sa.ForeignKey("customers.Customer_ID"), nullable=False),
        sa.Column("Vehicle_ID", sa.String(30), sa.ForeignKey("vehicles.Vehicle_ID"), nullable=False),
        sa.Column("Policy_Number", sa.String(30), nullable=False, unique=True),
        sa.Column("Policy_Type", sa.String(30), nullable=False),
        sa.Column("Policy_Code", sa.String(20), nullable=False),
        sa.Column("Coverage_Type", sa.String(30), nullable=False),
        sa.Column("Class_Code", sa.String(20), nullable=False),
        sa.Column("Policy_Start_Date", sa.Date(), nullable=False),
        sa.Column("Policy_End_Date", sa.Date(), nullable=False),
        sa.Column("Policy_Year", sa.String(10), nullable=False),
        sa.Column("Premium_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("Sum_Insured", sa.Numeric(14, 2), nullable=False),
        sa.Column("IDV", sa.Numeric(14, 2), nullable=False),
        sa.Column("Deductible_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("No_Claim_Bonus", sa.Numeric(5, 2), nullable=False),
        sa.Column("NCB_Flag", sa.Boolean(), nullable=False),
        sa.Column("Policy_Status", sa.String(30), nullable=False),
        sa.Column("Renewal_Status", sa.String(30), nullable=False),
        sa.Column("Office_Code", sa.String(20), nullable=False),
        sa.Column("Endorsement_Flag", sa.Boolean(), nullable=False),
        sa.Column("Endorsement_Number", sa.String(30), nullable=True),
        sa.Column("Anti_Theft_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Auto_Association_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Voluntary_Excess_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Vintage_Car_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Own_Premises_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Special_Design_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Side_Car_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("Special_Rating_Discount_Flag", sa.Boolean(), nullable=False),
        sa.Column("TPPD_Statutory_Cover_Flag", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_policies_Customer_ID", "policies", ["Customer_ID"])
    op.create_index("ix_policies_Vehicle_ID", "policies", ["Vehicle_ID"])
    op.create_index("ix_policies_Policy_Status", "policies", ["Policy_Status"])

    # ------------------------------------------------------------
    # 5. claims
    # ------------------------------------------------------------
    op.create_table(
        "claims",
        sa.Column("Claim_ID", sa.String(30), primary_key=True),
        sa.Column("Policy_ID", sa.String(30), sa.ForeignKey("policies.Policy_ID"), nullable=False),
        sa.Column("Customer_ID", sa.String(30), sa.ForeignKey("customers.Customer_ID"), nullable=False),
        sa.Column("Vehicle_ID", sa.String(30), sa.ForeignKey("vehicles.Vehicle_ID"), nullable=False),
        sa.Column("Claim_Number", sa.String(30), nullable=False, unique=True),
        sa.Column("Claim_Number_Child", sa.String(30), nullable=True),
        sa.Column("Claim_Date", sa.Date(), nullable=False),
        sa.Column("Claim_Year", sa.String(10), nullable=False),
        sa.Column("Claim_Type", sa.String(30), nullable=False),
        sa.Column("Claim_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("Approved_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("Claim_Status", sa.String(30), nullable=False),
        sa.Column("Claim_Description", sa.Text(), nullable=False),
        sa.Column("Claims_History_Code", sa.String(10), nullable=False),
        sa.Column("Incurred_Claims_Code", sa.String(10), nullable=False),
        sa.Column("Nature_of_Loss_Code", sa.String(10), nullable=False),
        sa.Column("Insurer_NOL_Code", sa.String(20), nullable=False),
        sa.Column("TPPD_Statutory_Cover_Flag", sa.Boolean(), nullable=False),
        sa.Column("Claim_Intimation_Date", sa.Date(), nullable=False),
        sa.Column("Date_of_Disbursement", sa.Date(), nullable=False),
        sa.Column("Place_of_Accident", sa.String(100), nullable=False),
        sa.Column("Accident_Pincode", sa.String(10), nullable=False),
        sa.Column("Claim_Processing_Days", sa.Integer(), nullable=False),
        sa.Column("Repair_Duration_Days", sa.Integer(), nullable=False),
        sa.Column("Final_Decision", sa.String(30), nullable=False),
        sa.Column("Decision_Date", sa.Date(), nullable=False),
        sa.Column("Decision_Reason", sa.Text(), nullable=False),
        sa.Column("TP_Amount_Claimed", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Claims_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Awards_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Expenses_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Interest_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("Wider_Legal_Liability_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("PA_Owner_Driver_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("PA_Others_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("Nature_of_Injury_Code", sa.String(10), nullable=False),
        sa.Column("Interim_Award_Flag", sa.Boolean(), nullable=False),
        sa.Column("Settlement_Basis_Code", sa.String(10), nullable=False),
        sa.Column("Fatal_NonFatal_Flag", sa.Boolean(), nullable=False),
        sa.Column("Open_Provision_Main", sa.Numeric(14, 2), nullable=False),
        sa.Column("Open_Provision_Expenses", sa.Numeric(14, 2), nullable=False),
        sa.Column("Open_Provision_Interest", sa.Numeric(14, 2), nullable=False),
        sa.Column("Closing_Provision_Main", sa.Numeric(14, 2), nullable=False),
        sa.Column("Closing_Provision_Expenses", sa.Numeric(14, 2), nullable=False),
        sa.Column("Closing_Provision_Interest", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_claims_Policy_ID", "claims", ["Policy_ID"])
    op.create_index("ix_claims_Customer_ID", "claims", ["Customer_ID"])
    op.create_index("ix_claims_Vehicle_ID", "claims", ["Vehicle_ID"])
    op.create_index("ix_claims_Claim_Status", "claims", ["Claim_Status"])
    op.create_index("ix_claims_Claim_Date", "claims", ["Claim_Date"])

    # ------------------------------------------------------------
    # 6. accidents
    # ------------------------------------------------------------
    op.create_table(
        "accidents",
        sa.Column("Accident_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Accident_Date", sa.Date(), nullable=False),
        sa.Column("Accident_Time", sa.Time(), nullable=False),
        sa.Column("Accident_Location", sa.Text(), nullable=False),
        sa.Column("Accident_City", sa.String(100), nullable=False),
        sa.Column("Accident_State", sa.String(100), nullable=False),
        sa.Column("Accident_Pincode", sa.String(10), nullable=False),
        sa.Column("Accident_Type", sa.String(50), nullable=False),
        sa.Column("Accident_Description", sa.Text(), nullable=False),
        sa.Column("Weather_Condition", sa.String(30), nullable=False),
        sa.Column("Road_Condition", sa.String(30), nullable=False),
        sa.Column("Road_Type_Code", sa.String(20), nullable=False),
        sa.Column("Police_Report_Available", sa.Boolean(), nullable=False),
        sa.Column("FIR_Number", sa.String(30), nullable=True),
        sa.Column("Third_Party_Involved", sa.Boolean(), nullable=False),
        sa.Column("Injury_Reported", sa.Boolean(), nullable=False),
        sa.Column("Witness_Available", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_accidents_Claim_ID", "accidents", ["Claim_ID"])

    # ------------------------------------------------------------
    # 7. documents
    # ------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("Document_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Document_Type", sa.String(50), nullable=False),
        sa.Column("Document_Name", sa.String(255), nullable=False),
        sa.Column("Document_Submitted_Date", sa.Date(), nullable=False),
        sa.Column("Document_Status", sa.String(30), nullable=False),
        sa.Column("OCR_Confidence_Score", sa.Numeric(5, 4), nullable=False),
        sa.Column("Extracted_Text", sa.Text(), nullable=False),
        sa.Column("Document_Completeness", sa.Numeric(5, 4), nullable=False),
        sa.Column("Document_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Verification_Status", sa.String(30), nullable=False),
    )
    op.create_index("ix_documents_Claim_ID", "documents", ["Claim_ID"])

    # ------------------------------------------------------------
    # 8. vehicle_damage
    # ------------------------------------------------------------
    op.create_table(
        "vehicle_damage",
        sa.Column("Damage_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Vehicle_ID", sa.String(30), sa.ForeignKey("vehicles.Vehicle_ID"), nullable=False),
        sa.Column("Damage_Type", sa.String(50), nullable=False),
        sa.Column("Damaged_Part", sa.String(50), nullable=False),
        sa.Column("Damage_Severity", sa.String(30), nullable=False),
        sa.Column("Damage_Location", sa.String(30), nullable=False),
        sa.Column("Estimated_Damage_Cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("Repair_or_Replace", sa.String(20), nullable=False),
        sa.Column("Photo_Evidence_Available", sa.Boolean(), nullable=False),
        sa.Column("Vehicle_Damage_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Damage_Description", sa.Text(), nullable=False),
    )
    op.create_index("ix_vehicle_damage_Claim_ID", "vehicle_damage", ["Claim_ID"])
    op.create_index("ix_vehicle_damage_Vehicle_ID", "vehicle_damage", ["Vehicle_ID"])

    # ------------------------------------------------------------
    # 9. repair_estimates
    # ------------------------------------------------------------
    op.create_table(
        "repair_estimates",
        sa.Column("Estimate_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Vehicle_ID", sa.String(30), sa.ForeignKey("vehicles.Vehicle_ID"), nullable=False),
        sa.Column("Garage_ID", sa.String(30), nullable=False),
        sa.Column("Estimate_Date", sa.Date(), nullable=False),
        sa.Column("Repair_Estimate", sa.Numeric(14, 2), nullable=False),
        sa.Column("Repair_Cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("Parts_Cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("Labour_Cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("Painting_Cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("Replacement_Parts_Count", sa.Integer(), nullable=False),
        sa.Column("Repaired_Parts_Count", sa.Integer(), nullable=False),
        sa.Column("Estimated_Repair_Days", sa.Integer(), nullable=False),
        sa.Column("Actual_Repair_Days", sa.Integer(), nullable=False),
        sa.Column("Excessive_Claim_Amount_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Estimate_Anomaly_Score", sa.Numeric(8, 4), nullable=False),
    )
    op.create_index("ix_repair_estimates_Claim_ID", "repair_estimates", ["Claim_ID"])
    op.create_index("ix_repair_estimates_Vehicle_ID", "repair_estimates", ["Vehicle_ID"])
    op.create_index("ix_repair_estimates_Garage_ID", "repair_estimates", ["Garage_ID"])

    # ------------------------------------------------------------
    # 10. evidence
    # ------------------------------------------------------------
    op.create_table(
        "evidence",
        sa.Column("Evidence_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Evidence_Type", sa.String(50), nullable=False),
        sa.Column("File_Name", sa.String(255), nullable=False),
        sa.Column("Evidence_Date", sa.Date(), nullable=False),
        sa.Column("Evidence_Source", sa.String(30), nullable=False),
        sa.Column("Image_Quality", sa.Numeric(5, 4), nullable=False),
        sa.Column("Vehicle_Damage_Detected", sa.Boolean(), nullable=False),
        sa.Column("Damage_Severity", sa.String(30), nullable=False),
        sa.Column("Location_Match", sa.Boolean(), nullable=False),
        sa.Column("Duplicate_Evidence_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Evidence_Confidence_Score", sa.Numeric(5, 4), nullable=False),
        sa.Column("Verification_Status", sa.String(30), nullable=False),
    )
    op.create_index("ix_evidence_Claim_ID", "evidence", ["Claim_ID"])

    # ------------------------------------------------------------
    # 11. surveyor_inspections
    # ------------------------------------------------------------
    op.create_table(
        "surveyor_inspections",
        sa.Column("Inspection_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column(
            "Surveyor_ID",
            sa.String(30),
            sa.ForeignKey("authentication_users.Employee_ID"),
            nullable=False,
        ),
        sa.Column("Inspection_Date", sa.Date(), nullable=False),
        sa.Column("Inspection_Location", sa.Text(), nullable=False),
        sa.Column("Vehicle_Condition", sa.String(30), nullable=False),
        sa.Column("Damage_Observed", sa.String(10), nullable=False),
        sa.Column("Damage_Severity", sa.String(30), nullable=False),
        sa.Column("Parts_Required", sa.Integer(), nullable=False),
        sa.Column("Repair_Recommendation", sa.String(30), nullable=False),
        sa.Column("Surveyor_Comments", sa.Text(), nullable=False),
        sa.Column("Inspection_Status", sa.String(30), nullable=False),
        sa.Column("Survey_Report_Submitted", sa.Boolean(), nullable=False),
        sa.Column("Surveyor_Confidence_Score", sa.Numeric(5, 4), nullable=False),
    )
    op.create_index("ix_surveyor_inspections_Claim_ID", "surveyor_inspections", ["Claim_ID"])
    op.create_index("ix_surveyor_inspections_Surveyor_ID", "surveyor_inspections", ["Surveyor_ID"])

    # ------------------------------------------------------------
    # 12. cross_document_consistency
    # ------------------------------------------------------------
    op.create_table(
        "cross_document_consistency",
        sa.Column("Consistency_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Customer_Statement_Match", sa.String(20), nullable=False),
        sa.Column("FIR_Match", sa.String(20), nullable=False),
        sa.Column("Surveyor_Report_Match", sa.String(20), nullable=False),
        sa.Column("Repair_Estimate_Match", sa.String(20), nullable=False),
        sa.Column("Accident_Date_Match", sa.String(20), nullable=False),
        sa.Column("Accident_Location_Match", sa.String(20), nullable=False),
        sa.Column("Vehicle_Details_Match", sa.String(20), nullable=False),
        sa.Column("Damage_Description_Match", sa.String(20), nullable=False),
        sa.Column("Claim_Amount_Match", sa.String(20), nullable=False),
        sa.Column("Document_Consistency_Score", sa.Numeric(5, 4), nullable=False),
        sa.Column("Document_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Accident_Details_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Vehicle_Damage_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Overall_Consistency_Status", sa.String(20), nullable=False),
    )
    op.create_index(
        "ix_cross_document_consistency_Claim_ID", "cross_document_consistency", ["Claim_ID"]
    )

    # ------------------------------------------------------------
    # 13. fraud_risk_analysis
    # ------------------------------------------------------------
    op.create_table(
        "fraud_risk_analysis",
        sa.Column("Risk_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("Duplicate_Claim_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Previous_Similar_Claim", sa.Boolean(), nullable=False),
        sa.Column("Suspicious_Garage_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Claim_Immediately_After_Policy_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Excessive_Claim_Amount_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Document_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Vehicle_Damage_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Accident_Details_Mismatch_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Evidence_Reuse_Indicator", sa.Boolean(), nullable=False),
        sa.Column("Fraud_Risk_Score", sa.Numeric(6, 2), nullable=False),
        sa.Column("Anomaly_Score", sa.Numeric(8, 4), nullable=False),
        sa.Column("Overall_Risk_Score", sa.Numeric(6, 2), nullable=False),
        sa.Column("Risk_Category", sa.String(20), nullable=False),
        sa.Column("Fraud_Label", sa.Integer(), nullable=False),
    )
    op.create_index("ix_fraud_risk_analysis_Claim_ID", "fraud_risk_analysis", ["Claim_ID"])
    op.create_index("ix_fraud_risk_analysis_Risk_Category", "fraud_risk_analysis", ["Risk_Category"])

    # ------------------------------------------------------------
    # 14. claim_decision_audit
    # ------------------------------------------------------------
    op.create_table(
        "claim_decision_audit",
        sa.Column("Audit_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column(
            "Claims_Officer_ID",
            sa.String(30),
            sa.ForeignKey("authentication_users.Employee_ID"),
            nullable=False,
        ),
        sa.Column("AI_Recommendation", sa.String(30), nullable=False),
        sa.Column("AI_Confidence_Score", sa.Numeric(5, 4), nullable=False),
        sa.Column("Human_Review_Required", sa.Boolean(), nullable=False),
        sa.Column("Final_Decision", sa.String(30), nullable=False),
        sa.Column("Decision_Reason", sa.Text(), nullable=False),
        sa.Column("Approved_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("Decision_Date", sa.Date(), nullable=False),
        sa.Column("Escalation_Status", sa.String(30), nullable=False),
        sa.Column("Escalated_To", sa.String(30), nullable=True),
        sa.Column("Officer_Comments", sa.Text(), nullable=False),
        sa.Column("Audit_Action", sa.String(30), nullable=False),
        sa.Column("Audit_Timestamp", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_claim_decision_audit_Claim_ID", "claim_decision_audit", ["Claim_ID"])
    op.create_index(
        "ix_claim_decision_audit_Claims_Officer_ID", "claim_decision_audit", ["Claims_Officer_ID"]
    )

    # ------------------------------------------------------------
    # 15. tp_claims
    # ------------------------------------------------------------
    op.create_table(
        "tp_claims",
        sa.Column("TP_Claim_ID", sa.String(30), primary_key=True),
        sa.Column("Claim_ID", sa.String(30), sa.ForeignKey("claims.Claim_ID"), nullable=False),
        sa.Column("TP_Amount_Claimed", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Claims_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Awards_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Expenses_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("TP_Interest_Paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("Wider_Legal_Liability_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("PA_Owner_Driver_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("PA_Others_Amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("Open_Provision_Main", sa.Numeric(14, 2), nullable=False),
        sa.Column("Open_Provision_Expenses", sa.Numeric(14, 2), nullable=False),
        sa.Column("Open_Provision_Interest", sa.Numeric(14, 2), nullable=False),
        sa.Column("Closing_Provision_Main", sa.Numeric(14, 2), nullable=False),
        sa.Column("Closing_Provision_Expenses", sa.Numeric(14, 2), nullable=False),
        sa.Column("Closing_Provision_Interest", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_tp_claims_Claim_ID", "tp_claims", ["Claim_ID"])

    # ------------------------------------------------------------
    # Circular FK: vehicles.Policy_ID -> policies.Policy_ID
    # Added last, now that both tables exist.
    # ------------------------------------------------------------
    op.create_foreign_key(
        "fk_vehicles_policy_id",
        "vehicles",
        "policies",
        ["Policy_ID"],
        ["Policy_ID"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_vehicles_policy_id", "vehicles", type_="foreignkey")
    op.drop_table("tp_claims")
    op.drop_table("claim_decision_audit")
    op.drop_table("fraud_risk_analysis")
    op.drop_table("cross_document_consistency")
    op.drop_table("surveyor_inspections")
    op.drop_table("evidence")
    op.drop_table("repair_estimates")
    op.drop_table("vehicle_damage")
    op.drop_table("documents")
    op.drop_table("accidents")
    op.drop_table("claims")
    op.drop_table("policies")
    op.drop_table("vehicles")
    op.drop_table("authentication_users")
    op.drop_table("customers")
