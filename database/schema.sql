-- CI-MICOP database schema
-- Cloud-Native Intelligent Motor Insurance Claims Operations Platform
--
-- Step 2: final 15-table application schema. This file mirrors the
-- SQLAlchemy models under backend/app/db_models/ exactly (it was
-- generated from Base.metadata against the postgresql dialect) and the
-- Alembic migration in backend/alembic/versions/. Do not edit one
-- without the other.
--
-- Tables are created in dependency order: customers -> authentication_users
-- -> vehicles (Policy_ID nullable, no FK yet) -> policies (Vehicle_ID FK)
-- -> claims -> all claim-child tables. The vehicles.Policy_ID <->
-- policies.Vehicle_ID circular relationship is resolved by adding the
-- vehicles.Policy_ID foreign key with a trailing ALTER TABLE, after both
-- tables already exist. See docs/ (Step 2 report) for full rationale,
-- including the two documented spec-vs-dataset discrepancies:
--   1. authentication_users.Insurer_Code has no data in the authoritative
--      dataset file (kept nullable, per spec).
--   2. surveyor_inspections.Surveyor_ID and claim_decision_audit
--      .Claims_Officer_ID reference authentication_users.Employee_ID
--      (not User_ID as literally worded in the spec - Employee_ID is the
--      column whose values actually match).

-- ============================================================
-- 1. customers
-- ============================================================
CREATE TABLE customers (
	"Customer_ID" VARCHAR(30) NOT NULL,
	"Customer_Name" VARCHAR(150) NOT NULL,
	"Date_of_Birth" DATE NOT NULL,
	"Age" INTEGER NOT NULL,
	"Gender" VARCHAR(20) NOT NULL,
	"Phone" VARCHAR(20) NOT NULL,
	"Email" VARCHAR(255) NOT NULL,
	"Address" VARCHAR(255) NOT NULL,
	"City" VARCHAR(100) NOT NULL,
	"State" VARCHAR(100) NOT NULL,
	"Pincode" VARCHAR(10) NOT NULL,
	"Occupation" VARCHAR(50) NOT NULL,
	"Driving_Experience_Years" INTEGER NOT NULL,
	"Customer_Type" VARCHAR(30) NOT NULL,
	"Previous_Claim_Count" INTEGER NOT NULL,
	"Driver_Age_Code" VARCHAR(10) NOT NULL,
	"Driver_Experience_Code" VARCHAR(10) NOT NULL,
	"Driver_Qualification_Code" VARCHAR(10) NOT NULL,
	"Driver_Type_Code" VARCHAR(10) NOT NULL,
	PRIMARY KEY ("Customer_ID")
);

CREATE INDEX "ix_customers_City" ON customers ("City");
CREATE INDEX "ix_customers_State" ON customers ("State");
CREATE INDEX "ix_customers_Pincode" ON customers ("Pincode");

-- ============================================================
-- 2. authentication_users
-- ============================================================
CREATE TABLE authentication_users (
	"User_ID" VARCHAR(30) NOT NULL,
	"Username" VARCHAR(100) NOT NULL,
	"Password_Hash" VARCHAR(255) NOT NULL,
	"Role" VARCHAR(30) NOT NULL,
	"Customer_ID" VARCHAR(30),
	"Employee_ID" VARCHAR(30),
	"Email" VARCHAR(255) NOT NULL,
	"Phone" VARCHAR(20) NOT NULL,
	"Account_Status" VARCHAR(30) NOT NULL,
	"Login_Status" VARCHAR(30) NOT NULL,
	"Last_Login" TIMESTAMP WITHOUT TIME ZONE,
	"Created_Date" DATE NOT NULL,
	"Failed_Login_Count" INTEGER NOT NULL,
	"Permission_Level" INTEGER NOT NULL,
	"Insurer_Code" VARCHAR(30),
	PRIMARY KEY ("User_ID"),
	CONSTRAINT ck_authentication_users_role CHECK ("Role" IN ('Customer', 'Surveyor', 'Claims Officer', 'Admin')),
	FOREIGN KEY ("Customer_ID") REFERENCES customers ("Customer_ID"),
	UNIQUE ("Username"),
	UNIQUE ("Employee_ID")
);

CREATE INDEX "ix_authentication_users_Role" ON authentication_users ("Role");

-- ============================================================
-- 3. vehicles (Policy_ID nullable; FK added after policies exists)
-- ============================================================
CREATE TABLE vehicles (
	"Vehicle_ID" VARCHAR(30) NOT NULL,
	"Customer_ID" VARCHAR(30) NOT NULL,
	"Policy_ID" VARCHAR(30),
	"Vehicle_Type" VARCHAR(50) NOT NULL,
	"Vehicle_Subtype" VARCHAR(50),
	"Registration_Number" VARCHAR(30) NOT NULL,
	"Chassis_Number" VARCHAR(30) NOT NULL,
	"Engine_Number" VARCHAR(30) NOT NULL,
	"Vehicle_Color" VARCHAR(30) NOT NULL,
	"Make" VARCHAR(50) NOT NULL,
	"Make_Code" VARCHAR(20) NOT NULL,
	"Model" VARCHAR(50) NOT NULL,
	"Variant" VARCHAR(30) NOT NULL,
	"Manufacturing_Year" INTEGER NOT NULL,
	"Registration_Year" INTEGER NOT NULL,
	"Vehicle_Age" INTEGER NOT NULL,
	"Fuel_Type" VARCHAR(20) NOT NULL,
	"Engine_CC" INTEGER NOT NULL,
	"CC_PCC_GVW_Code" VARCHAR(20) NOT NULL,
	"Vehicle_Value" NUMERIC(14, 2) NOT NULL,
	"Usage_Type" VARCHAR(30) NOT NULL,
	"GVW_KG" INTEGER,
	"Load_Capacity_KG" INTEGER,
	"Seating_Capacity" INTEGER NOT NULL,
	"Permit_Code" VARCHAR(20),
	"Nature_of_Goods_Code" VARCHAR(20),
	"Road_Type_Code" VARCHAR(20) NOT NULL,
	"Vehicle_Driven_By_Code" VARCHAR(20) NOT NULL,
	"RTA_Location_Code" VARCHAR(20) NOT NULL,
	"Class_Code" VARCHAR(20) NOT NULL,
	"Zone_Code" VARCHAR(20) NOT NULL,
	"Previous_Claim_Count" INTEGER NOT NULL,
	"Policy_Start_Date" DATE NOT NULL,
	"Policy_End_Date" DATE NOT NULL,
	PRIMARY KEY ("Vehicle_ID"),
	FOREIGN KEY ("Customer_ID") REFERENCES customers ("Customer_ID"),
	UNIQUE ("Registration_Number"),
	UNIQUE ("Chassis_Number"),
	UNIQUE ("Engine_Number")
);

CREATE INDEX "ix_vehicles_Customer_ID" ON vehicles ("Customer_ID");
CREATE INDEX "ix_vehicles_Policy_ID" ON vehicles ("Policy_ID");

-- ============================================================
-- 4. policies
-- ============================================================
CREATE TABLE policies (
	"Policy_ID" VARCHAR(30) NOT NULL,
	"Customer_ID" VARCHAR(30) NOT NULL,
	"Vehicle_ID" VARCHAR(30) NOT NULL,
	"Policy_Number" VARCHAR(30) NOT NULL,
	"Policy_Type" VARCHAR(30) NOT NULL,
	"Policy_Code" VARCHAR(20) NOT NULL,
	"Coverage_Type" VARCHAR(30) NOT NULL,
	"Class_Code" VARCHAR(20) NOT NULL,
	"Policy_Start_Date" DATE NOT NULL,
	"Policy_End_Date" DATE NOT NULL,
	"Policy_Year" VARCHAR(10) NOT NULL,
	"Premium_Amount" NUMERIC(14, 2) NOT NULL,
	"Sum_Insured" NUMERIC(14, 2) NOT NULL,
	"IDV" NUMERIC(14, 2) NOT NULL,
	"Deductible_Amount" NUMERIC(14, 2) NOT NULL,
	"No_Claim_Bonus" NUMERIC(5, 2) NOT NULL,
	"NCB_Flag" BOOLEAN NOT NULL,
	"Policy_Status" VARCHAR(30) NOT NULL,
	"Renewal_Status" VARCHAR(30) NOT NULL,
	"Office_Code" VARCHAR(20) NOT NULL,
	"Endorsement_Flag" BOOLEAN NOT NULL,
	"Endorsement_Number" VARCHAR(30),
	"Anti_Theft_Discount_Flag" BOOLEAN NOT NULL,
	"Auto_Association_Discount_Flag" BOOLEAN NOT NULL,
	"Voluntary_Excess_Discount_Flag" BOOLEAN NOT NULL,
	"Vintage_Car_Discount_Flag" BOOLEAN NOT NULL,
	"Own_Premises_Discount_Flag" BOOLEAN NOT NULL,
	"Special_Design_Discount_Flag" BOOLEAN NOT NULL,
	"Side_Car_Discount_Flag" BOOLEAN NOT NULL,
	"Special_Rating_Discount_Flag" BOOLEAN NOT NULL,
	"TPPD_Statutory_Cover_Flag" BOOLEAN NOT NULL,
	PRIMARY KEY ("Policy_ID"),
	FOREIGN KEY ("Customer_ID") REFERENCES customers ("Customer_ID"),
	FOREIGN KEY ("Vehicle_ID") REFERENCES vehicles ("Vehicle_ID"),
	UNIQUE ("Policy_Number")
);

CREATE INDEX "ix_policies_Customer_ID" ON policies ("Customer_ID");
CREATE INDEX "ix_policies_Vehicle_ID" ON policies ("Vehicle_ID");
CREATE INDEX "ix_policies_Policy_Status" ON policies ("Policy_Status");

-- ============================================================
-- 5. claims
-- ============================================================
CREATE TABLE claims (
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Policy_ID" VARCHAR(30) NOT NULL,
	"Customer_ID" VARCHAR(30) NOT NULL,
	"Vehicle_ID" VARCHAR(30) NOT NULL,
	"Claim_Number" VARCHAR(30) NOT NULL,
	"Claim_Number_Child" VARCHAR(30),
	"Claim_Date" DATE NOT NULL,
	"Claim_Year" VARCHAR(10) NOT NULL,
	"Claim_Type" VARCHAR(30) NOT NULL,
	"Claim_Amount" NUMERIC(14, 2) NOT NULL,
	"Approved_Amount" NUMERIC(14, 2) NOT NULL,
	"Claim_Status" VARCHAR(30) NOT NULL,
	"Claim_Description" TEXT NOT NULL,
	"Claims_History_Code" VARCHAR(10) NOT NULL,
	"Incurred_Claims_Code" VARCHAR(10) NOT NULL,
	"Nature_of_Loss_Code" VARCHAR(10) NOT NULL,
	"Insurer_NOL_Code" VARCHAR(20) NOT NULL,
	"TPPD_Statutory_Cover_Flag" BOOLEAN NOT NULL,
	"Claim_Intimation_Date" DATE NOT NULL,
	"Date_of_Disbursement" DATE NOT NULL,
	"Place_of_Accident" VARCHAR(100) NOT NULL,
	"Accident_Pincode" VARCHAR(10) NOT NULL,
	"Claim_Processing_Days" INTEGER NOT NULL,
	"Repair_Duration_Days" INTEGER NOT NULL,
	"Final_Decision" VARCHAR(30) NOT NULL,
	"Decision_Date" DATE NOT NULL,
	"Decision_Reason" TEXT NOT NULL,
	"TP_Amount_Claimed" NUMERIC(14, 2) NOT NULL,
	"TP_Claims_Paid" NUMERIC(14, 2) NOT NULL,
	"TP_Awards_Paid" NUMERIC(14, 2) NOT NULL,
	"TP_Expenses_Paid" NUMERIC(14, 2) NOT NULL,
	"TP_Interest_Paid" NUMERIC(14, 2) NOT NULL,
	"Wider_Legal_Liability_Amount" NUMERIC(14, 2) NOT NULL,
	"PA_Owner_Driver_Amount" NUMERIC(14, 2) NOT NULL,
	"PA_Others_Amount" NUMERIC(14, 2) NOT NULL,
	"Nature_of_Injury_Code" VARCHAR(10) NOT NULL,
	"Interim_Award_Flag" BOOLEAN NOT NULL,
	"Settlement_Basis_Code" VARCHAR(10) NOT NULL,
	"Fatal_NonFatal_Flag" BOOLEAN NOT NULL,
	"Open_Provision_Main" NUMERIC(14, 2) NOT NULL,
	"Open_Provision_Expenses" NUMERIC(14, 2) NOT NULL,
	"Open_Provision_Interest" NUMERIC(14, 2) NOT NULL,
	"Closing_Provision_Main" NUMERIC(14, 2) NOT NULL,
	"Closing_Provision_Expenses" NUMERIC(14, 2) NOT NULL,
	"Closing_Provision_Interest" NUMERIC(14, 2) NOT NULL,
	PRIMARY KEY ("Claim_ID"),
	FOREIGN KEY ("Policy_ID") REFERENCES policies ("Policy_ID"),
	FOREIGN KEY ("Customer_ID") REFERENCES customers ("Customer_ID"),
	FOREIGN KEY ("Vehicle_ID") REFERENCES vehicles ("Vehicle_ID"),
	UNIQUE ("Claim_Number")
);

CREATE INDEX "ix_claims_Policy_ID" ON claims ("Policy_ID");
CREATE INDEX "ix_claims_Customer_ID" ON claims ("Customer_ID");
CREATE INDEX "ix_claims_Vehicle_ID" ON claims ("Vehicle_ID");
CREATE INDEX "ix_claims_Claim_Status" ON claims ("Claim_Status");
CREATE INDEX "ix_claims_Claim_Date" ON claims ("Claim_Date");

-- ============================================================
-- 6. accidents (one-to-many with claims; not UNIQUE on Claim_ID)
-- ============================================================
CREATE TABLE accidents (
	"Accident_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Accident_Date" DATE NOT NULL,
	"Accident_Time" TIME WITHOUT TIME ZONE NOT NULL,
	"Accident_Location" TEXT NOT NULL,
	"Accident_City" VARCHAR(100) NOT NULL,
	"Accident_State" VARCHAR(100) NOT NULL,
	"Accident_Pincode" VARCHAR(10) NOT NULL,
	"Accident_Type" VARCHAR(50) NOT NULL,
	"Accident_Description" TEXT NOT NULL,
	"Weather_Condition" VARCHAR(30) NOT NULL,
	"Road_Condition" VARCHAR(30) NOT NULL,
	"Road_Type_Code" VARCHAR(20) NOT NULL,
	"Police_Report_Available" BOOLEAN NOT NULL,
	"FIR_Number" VARCHAR(30),
	"Third_Party_Involved" BOOLEAN NOT NULL,
	"Injury_Reported" BOOLEAN NOT NULL,
	"Witness_Available" BOOLEAN NOT NULL,
	PRIMARY KEY ("Accident_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID")
);

CREATE INDEX "ix_accidents_Claim_ID" ON accidents ("Claim_ID");

-- ============================================================
-- 7. documents (one-to-many with claims)
-- ============================================================
CREATE TABLE documents (
	"Document_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Document_Type" VARCHAR(50) NOT NULL,
	"Document_Name" VARCHAR(255) NOT NULL,
	"Document_Submitted_Date" DATE NOT NULL,
	"Document_Status" VARCHAR(30) NOT NULL,
	"OCR_Confidence_Score" NUMERIC(5, 4) NOT NULL,
	"Extracted_Text" TEXT NOT NULL,
	"Document_Completeness" NUMERIC(5, 4) NOT NULL,
	"Document_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Verification_Status" VARCHAR(30) NOT NULL,
	PRIMARY KEY ("Document_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID")
);

CREATE INDEX "ix_documents_Claim_ID" ON documents ("Claim_ID");

-- ============================================================
-- 8. vehicle_damage
-- ============================================================
CREATE TABLE vehicle_damage (
	"Damage_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Vehicle_ID" VARCHAR(30) NOT NULL,
	"Damage_Type" VARCHAR(50) NOT NULL,
	"Damaged_Part" VARCHAR(50) NOT NULL,
	"Damage_Severity" VARCHAR(30) NOT NULL,
	"Damage_Location" VARCHAR(30) NOT NULL,
	"Estimated_Damage_Cost" NUMERIC(14, 2) NOT NULL,
	"Repair_or_Replace" VARCHAR(20) NOT NULL,
	"Photo_Evidence_Available" BOOLEAN NOT NULL,
	"Vehicle_Damage_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Damage_Description" TEXT NOT NULL,
	PRIMARY KEY ("Damage_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID"),
	FOREIGN KEY ("Vehicle_ID") REFERENCES vehicles ("Vehicle_ID")
);

CREATE INDEX "ix_vehicle_damage_Claim_ID" ON vehicle_damage ("Claim_ID");
CREATE INDEX "ix_vehicle_damage_Vehicle_ID" ON vehicle_damage ("Vehicle_ID");

-- ============================================================
-- 9. repair_estimates
-- ============================================================
CREATE TABLE repair_estimates (
	"Estimate_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Vehicle_ID" VARCHAR(30) NOT NULL,
	"Garage_ID" VARCHAR(30) NOT NULL,
	"Estimate_Date" DATE NOT NULL,
	"Repair_Estimate" NUMERIC(14, 2) NOT NULL,
	"Repair_Cost" NUMERIC(14, 2) NOT NULL,
	"Parts_Cost" NUMERIC(14, 2) NOT NULL,
	"Labour_Cost" NUMERIC(14, 2) NOT NULL,
	"Painting_Cost" NUMERIC(14, 2) NOT NULL,
	"Replacement_Parts_Count" INTEGER NOT NULL,
	"Repaired_Parts_Count" INTEGER NOT NULL,
	"Estimated_Repair_Days" INTEGER NOT NULL,
	"Actual_Repair_Days" INTEGER NOT NULL,
	"Excessive_Claim_Amount_Indicator" BOOLEAN NOT NULL,
	"Estimate_Anomaly_Score" NUMERIC(8, 4) NOT NULL,
	PRIMARY KEY ("Estimate_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID"),
	FOREIGN KEY ("Vehicle_ID") REFERENCES vehicles ("Vehicle_ID")
);

CREATE INDEX "ix_repair_estimates_Claim_ID" ON repair_estimates ("Claim_ID");
CREATE INDEX "ix_repair_estimates_Vehicle_ID" ON repair_estimates ("Vehicle_ID");
CREATE INDEX "ix_repair_estimates_Garage_ID" ON repair_estimates ("Garage_ID");

-- ============================================================
-- 10. evidence (one-to-many with claims)
-- ============================================================
CREATE TABLE evidence (
	"Evidence_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Evidence_Type" VARCHAR(50) NOT NULL,
	"File_Name" VARCHAR(255) NOT NULL,
	"Evidence_Date" DATE NOT NULL,
	"Evidence_Source" VARCHAR(30) NOT NULL,
	"Image_Quality" NUMERIC(5, 4) NOT NULL,
	"Vehicle_Damage_Detected" BOOLEAN NOT NULL,
	"Damage_Severity" VARCHAR(30) NOT NULL,
	"Location_Match" BOOLEAN NOT NULL,
	"Duplicate_Evidence_Indicator" BOOLEAN NOT NULL,
	"Evidence_Confidence_Score" NUMERIC(5, 4) NOT NULL,
	"Verification_Status" VARCHAR(30) NOT NULL,
	PRIMARY KEY ("Evidence_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID")
);

CREATE INDEX "ix_evidence_Claim_ID" ON evidence ("Claim_ID");

-- ============================================================
-- 11. surveyor_inspections
-- Surveyor_ID -> authentication_users.Employee_ID (see header note)
-- ============================================================
CREATE TABLE surveyor_inspections (
	"Inspection_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Surveyor_ID" VARCHAR(30) NOT NULL,
	"Inspection_Date" DATE NOT NULL,
	"Inspection_Location" TEXT NOT NULL,
	"Vehicle_Condition" VARCHAR(30) NOT NULL,
	"Damage_Observed" VARCHAR(10) NOT NULL,
	"Damage_Severity" VARCHAR(30) NOT NULL,
	"Parts_Required" INTEGER NOT NULL,
	"Repair_Recommendation" VARCHAR(30) NOT NULL,
	"Surveyor_Comments" TEXT NOT NULL,
	"Inspection_Status" VARCHAR(30) NOT NULL,
	"Survey_Report_Submitted" BOOLEAN NOT NULL,
	"Surveyor_Confidence_Score" NUMERIC(5, 4) NOT NULL,
	PRIMARY KEY ("Inspection_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID"),
	FOREIGN KEY ("Surveyor_ID") REFERENCES authentication_users ("Employee_ID")
);

CREATE INDEX "ix_surveyor_inspections_Claim_ID" ON surveyor_inspections ("Claim_ID");
CREATE INDEX "ix_surveyor_inspections_Surveyor_ID" ON surveyor_inspections ("Surveyor_ID");

-- ============================================================
-- 12. cross_document_consistency
-- ============================================================
CREATE TABLE cross_document_consistency (
	"Consistency_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Customer_Statement_Match" VARCHAR(20) NOT NULL,
	"FIR_Match" VARCHAR(20) NOT NULL,
	"Surveyor_Report_Match" VARCHAR(20) NOT NULL,
	"Repair_Estimate_Match" VARCHAR(20) NOT NULL,
	"Accident_Date_Match" VARCHAR(20) NOT NULL,
	"Accident_Location_Match" VARCHAR(20) NOT NULL,
	"Vehicle_Details_Match" VARCHAR(20) NOT NULL,
	"Damage_Description_Match" VARCHAR(20) NOT NULL,
	"Claim_Amount_Match" VARCHAR(20) NOT NULL,
	"Document_Consistency_Score" NUMERIC(5, 4) NOT NULL,
	"Document_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Accident_Details_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Vehicle_Damage_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Overall_Consistency_Status" VARCHAR(20) NOT NULL,
	PRIMARY KEY ("Consistency_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID")
);

CREATE INDEX "ix_cross_document_consistency_Claim_ID" ON cross_document_consistency ("Claim_ID");

-- ============================================================
-- 13. fraud_risk_analysis
-- ============================================================
CREATE TABLE fraud_risk_analysis (
	"Risk_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Duplicate_Claim_Indicator" BOOLEAN NOT NULL,
	"Previous_Similar_Claim" BOOLEAN NOT NULL,
	"Suspicious_Garage_Indicator" BOOLEAN NOT NULL,
	"Claim_Immediately_After_Policy_Indicator" BOOLEAN NOT NULL,
	"Excessive_Claim_Amount_Indicator" BOOLEAN NOT NULL,
	"Document_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Vehicle_Damage_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Accident_Details_Mismatch_Indicator" BOOLEAN NOT NULL,
	"Evidence_Reuse_Indicator" BOOLEAN NOT NULL,
	"Fraud_Risk_Score" NUMERIC(6, 2) NOT NULL,
	"Anomaly_Score" NUMERIC(8, 4) NOT NULL,
	"Overall_Risk_Score" NUMERIC(6, 2) NOT NULL,
	"Risk_Category" VARCHAR(20) NOT NULL,
	"Fraud_Label" INTEGER NOT NULL,
	PRIMARY KEY ("Risk_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID")
);

CREATE INDEX "ix_fraud_risk_analysis_Claim_ID" ON fraud_risk_analysis ("Claim_ID");
CREATE INDEX "ix_fraud_risk_analysis_Risk_Category" ON fraud_risk_analysis ("Risk_Category");

-- ============================================================
-- 14. claim_decision_audit (append-only; Claim_ID not unique)
-- Claims_Officer_ID -> authentication_users.Employee_ID (see header note)
-- Escalated_To has no FK - no Manager table in the 15-table design.
-- ============================================================
CREATE TABLE claim_decision_audit (
	"Audit_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"Claims_Officer_ID" VARCHAR(30) NOT NULL,
	"AI_Recommendation" VARCHAR(30) NOT NULL,
	"AI_Confidence_Score" NUMERIC(5, 4) NOT NULL,
	"Human_Review_Required" BOOLEAN NOT NULL,
	"Final_Decision" VARCHAR(30) NOT NULL,
	"Decision_Reason" TEXT NOT NULL,
	"Approved_Amount" NUMERIC(14, 2) NOT NULL,
	"Decision_Date" DATE NOT NULL,
	"Escalation_Status" VARCHAR(30) NOT NULL,
	"Escalated_To" VARCHAR(30),
	"Officer_Comments" TEXT NOT NULL,
	"Audit_Action" VARCHAR(30) NOT NULL,
	"Audit_Timestamp" TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY ("Audit_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID"),
	FOREIGN KEY ("Claims_Officer_ID") REFERENCES authentication_users ("Employee_ID")
);

CREATE INDEX "ix_claim_decision_audit_Claim_ID" ON claim_decision_audit ("Claim_ID");
CREATE INDEX "ix_claim_decision_audit_Claims_Officer_ID" ON claim_decision_audit ("Claims_Officer_ID");

-- ============================================================
-- 15. tp_claims (Claim_ID not unique - allows future one-to-many)
-- ============================================================
CREATE TABLE tp_claims (
	"TP_Claim_ID" VARCHAR(30) NOT NULL,
	"Claim_ID" VARCHAR(30) NOT NULL,
	"TP_Amount_Claimed" NUMERIC(14, 2) NOT NULL,
	"TP_Claims_Paid" NUMERIC(14, 2) NOT NULL,
	"TP_Awards_Paid" NUMERIC(14, 2) NOT NULL,
	"TP_Expenses_Paid" NUMERIC(14, 2) NOT NULL,
	"TP_Interest_Paid" NUMERIC(14, 2) NOT NULL,
	"Wider_Legal_Liability_Amount" NUMERIC(14, 2) NOT NULL,
	"PA_Owner_Driver_Amount" NUMERIC(14, 2) NOT NULL,
	"PA_Others_Amount" NUMERIC(14, 2) NOT NULL,
	"Open_Provision_Main" NUMERIC(14, 2) NOT NULL,
	"Open_Provision_Expenses" NUMERIC(14, 2) NOT NULL,
	"Open_Provision_Interest" NUMERIC(14, 2) NOT NULL,
	"Closing_Provision_Main" NUMERIC(14, 2) NOT NULL,
	"Closing_Provision_Expenses" NUMERIC(14, 2) NOT NULL,
	"Closing_Provision_Interest" NUMERIC(14, 2) NOT NULL,
	PRIMARY KEY ("TP_Claim_ID"),
	FOREIGN KEY ("Claim_ID") REFERENCES claims ("Claim_ID")
);

CREATE INDEX "ix_tp_claims_Claim_ID" ON tp_claims ("Claim_ID");

-- ============================================================
-- Circular FK: vehicles.Policy_ID -> policies.Policy_ID
-- Added last, after both tables exist.
-- ============================================================
ALTER TABLE vehicles
	ADD CONSTRAINT fk_vehicles_policy_id
	FOREIGN KEY ("Policy_ID") REFERENCES policies ("Policy_ID");
