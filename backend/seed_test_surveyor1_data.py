"""Approved test-data seed: three additional synthetic customers, each with
a distinct vehicle, policy and claim, all assigned to the existing
"Surveyor 1" account.

"Surveyor 1" was identified from the live development database (not
guessed from a display name): Username "dev_surveyor",
Employee_ID "DEV-SURV-001" - the only Surveyor account on file.

This script NEVER modifies or deletes any existing DEV-* record, and
never touches `seed_dev_data.py` or its data. It only ever adds new
TEST-CUST-002/003/004 rows and their dependents.

Mechanism, mirroring the only mechanisms that actually exist in this
project:
- Customer, Vehicle, Policy and AuthenticationUser (login) rows: direct
  ORM inserts via the same idempotent `add_if_missing` pattern
  `seed_dev_data.py` already uses - there is no create endpoint for any
  of these (checked: no POST/PUT/PATCH in routers/customers.py,
  vehicles.py, policies.py or admin.py).
- Claim (+ Accident) creation: the REAL application service,
  `services/claim_creation.create_claim_for_customer`, so the created
  claim goes through the same ownership checks and defaulting a live
  customer's claim would.
- Surveyor assignment: the REAL application service,
  `services/surveyor_assignment.assign_surveyor_to_claim` - this is what
  actually creates the `surveyor_inspections` row; assignment is never
  hand-inserted.

Per the approved plan: all three claims end in the genuine, real
"Assigned" lifecycle state the assignment service itself produces (there
is no real "in-progress inspection" status that can be set without
hand-editing `surveyor_inspections` fields and bypassing
`surveyor_workflow.py`'s server-enforced rules, which this script does
not do). The three claims are differentiated only by which `documents`
rows exist on them:
  - Claim A (test_customer2): no documents yet.
  - Claim B (test_customer3): FIR + RC-verification documents.
  - Claim C (test_customer4): FIR + RC + Repair Estimate documents.
All document rows are metadata-only records with no physical file
behind them - the same already-established convention
`seed_dev_data.py` itself uses for `DEV-DOC-001` - never a fabricated
real file.

Idempotent: every write is individually guarded. Re-running this script
inserts nothing new and never raises - an existing row is left
untouched, an existing claim for one of these three customers is reused
rather than duplicated, and an already-active assignment (which the real
service itself refuses with 409) is detected and treated as "already
done".
"""

from datetime import date, time
from decimal import Decimal

import bcrypt
from fastapi import HTTPException

from app.db.session import SessionLocal
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.customer import Customer
from app.db_models.vehicle import Vehicle
from app.db_models.policy import Policy
from app.db_models.document import Document
from app.crud import claim as crud_claim
from app.schemas.claim import ClaimCreate
from app.services import claim_creation, surveyor_assignment


# ============================================================
# CONSTANTS
# ============================================================

SURVEYOR_1_EMPLOYEE_ID = "DEV-SURV-001"  # verified against the live DB - see conversation
PASSWORD = "CiMicop@123"


def hash_password(password: str) -> str:
    """Identical to seed_dev_data.py's own hashing function - the
    application's real bcrypt mechanism, never weakened or bypassed."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def add_if_missing(db, model, pk_field, pk_value, **kwargs):
    """Identical helper to seed_dev_data.py - insert only if a row with
    this primary key does not already exist."""
    obj = db.query(model).filter(getattr(model, pk_field) == pk_value).first()
    if obj:
        return obj, False
    obj = model(**kwargs)
    db.add(obj)
    return obj, True


# ============================================================
# PER-CUSTOMER DEFINITIONS
# ============================================================

CUSTOMERS = [
    {
        "customer_id": "TEST-CUST-002",
        "vehicle_id": "TEST-VEH-002",
        "policy_id": "TEST-POL-002",
        "user_id": "TEST-USER-CUST2",
        "username": "test_customer2",
        "customer": dict(
            Customer_Name="Priya Raman",
            Date_of_Birth=date(1994, 3, 15),
            Age=32,
            Gender="Female",
            Phone="9000000101",
            Email="test.customer2@ci-micop.local",
            Address="RS Puram, Coimbatore, Tamil Nadu",
            City="Coimbatore",
            State="Tamil Nadu",
            Pincode="641001",
            Occupation="Teacher",
            Driving_Experience_Years=6,
            Customer_Type="Individual",
            Previous_Claim_Count=0,
            Driver_Age_Code="A32",
            Driver_Experience_Code="E06",
            Driver_Qualification_Code="GRAD",
            Driver_Type_Code="OWNER",
        ),
        "vehicle": dict(
            Vehicle_Type="Private Car",
            Vehicle_Subtype=None,
            Registration_Number="TN37CD2002",
            Chassis_Number="TESTCHASSIS002",
            Engine_Number="TESTENGINE002",
            Vehicle_Color="Red",
            Make="Maruti Suzuki",
            Make_Code="MSIL",
            Model="Swift",
            Variant="VXI",
            Manufacturing_Year=2021,
            Registration_Year=2021,
            Vehicle_Age=5,
            Fuel_Type="Petrol",
            Engine_CC=1197,
            CC_PCC_GVW_Code="1197",
            Vehicle_Value=Decimal("550000.00"),
            Usage_Type="Private",
            GVW_KG=None,
            Load_Capacity_KG=None,
            Seating_Capacity=5,
            Permit_Code=None,
            Nature_of_Goods_Code=None,
            Road_Type_Code="URBAN",
            Vehicle_Driven_By_Code="OWNER",
            RTA_Location_Code="TN37",
            Class_Code="PC",
            Zone_Code="A",
            Previous_Claim_Count=0,
            Policy_Start_Date=date(2026, 2, 1),
            Policy_End_Date=date(2027, 2, 1),
        ),
        "policy": dict(
            Policy_Number="TEST-POLICY-002",
            Policy_Type="Comprehensive",
            Policy_Code="COMP",
            Coverage_Type="Own Damage + TP",
            Class_Code="PC",
            Policy_Start_Date=date(2026, 2, 1),
            Policy_End_Date=date(2027, 2, 1),
            Policy_Year="2026",
            Premium_Amount=Decimal("16500.00"),
            Sum_Insured=Decimal("550000.00"),
            IDV=Decimal("530000.00"),
            Deductible_Amount=Decimal("1000.00"),
            No_Claim_Bonus=Decimal("15.00"),
            NCB_Flag=True,
            Policy_Status="Active",
            Renewal_Status="Pending",
            Office_Code="CBE001",
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
        ),
        "claim": ClaimCreate(
            Policy_ID="TEST-POL-002",
            Vehicle_ID="TEST-VEH-002",
            Claim_Date=date(2026, 10, 20),
            Claim_Type="Own Damage",
            Claim_Amount=Decimal("85000.00"),
            Claim_Description="Rear bumper and tail-light damage after a minor collision while parking.",
            Place_of_Accident="Coimbatore",
            Accident_Pincode="641001",
            Accident_Time=time(11, 15),
            Third_Party_Involved=False,
            Injury_Reported=False,
            Police_Report_Available=False,
            FIR_Number=None,
        ),
        # Claim A: no documents yet - "newly submitted, awaiting officer
        # review/assignment", then assigned per the approved plan.
        "documents": [],
    },
    {
        "customer_id": "TEST-CUST-003",
        "vehicle_id": "TEST-VEH-003",
        "policy_id": "TEST-POL-003",
        "user_id": "TEST-USER-CUST3",
        "username": "test_customer3",
        "customer": dict(
            Customer_Name="Karthik Subramaniam",
            Date_of_Birth=date(1989, 7, 22),
            Age=37,
            Gender="Male",
            Phone="9000000102",
            Email="test.customer3@ci-micop.local",
            Address="Anna Nagar, Madurai, Tamil Nadu",
            City="Madurai",
            State="Tamil Nadu",
            Pincode="625001",
            Occupation="Business Owner",
            Driving_Experience_Years=14,
            Customer_Type="Individual",
            Previous_Claim_Count=1,
            Driver_Age_Code="A37",
            Driver_Experience_Code="E14",
            Driver_Qualification_Code="GRAD",
            Driver_Type_Code="OWNER",
        ),
        "vehicle": dict(
            Vehicle_Type="Two Wheeler",
            Vehicle_Subtype=None,
            Registration_Number="TN59EF3003",
            Chassis_Number="TESTCHASSIS003",
            Engine_Number="TESTENGINE003",
            Vehicle_Color="Black",
            Make="Honda",
            Make_Code="HOND",
            Model="Activa",
            Variant="6G",
            Manufacturing_Year=2023,
            Registration_Year=2023,
            Vehicle_Age=3,
            Fuel_Type="Petrol",
            Engine_CC=110,
            CC_PCC_GVW_Code="110",
            Vehicle_Value=Decimal("85000.00"),
            Usage_Type="Private",
            GVW_KG=None,
            Load_Capacity_KG=None,
            Seating_Capacity=2,
            Permit_Code=None,
            Nature_of_Goods_Code=None,
            Road_Type_Code="URBAN",
            Vehicle_Driven_By_Code="OWNER",
            RTA_Location_Code="TN59",
            Class_Code="TW",
            Zone_Code="B",
            Previous_Claim_Count=1,
            Policy_Start_Date=date(2026, 1, 15),
            Policy_End_Date=date(2027, 1, 15),
        ),
        "policy": dict(
            Policy_Number="TEST-POLICY-003",
            Policy_Type="Third Party",
            Policy_Code="TP",
            Coverage_Type="Third Party Only",
            Class_Code="TW",
            Policy_Start_Date=date(2026, 1, 15),
            Policy_End_Date=date(2027, 1, 15),
            Policy_Year="2026",
            Premium_Amount=Decimal("1800.00"),
            Sum_Insured=Decimal("85000.00"),
            IDV=Decimal("80000.00"),
            Deductible_Amount=Decimal("500.00"),
            No_Claim_Bonus=Decimal("0.00"),
            NCB_Flag=False,
            Policy_Status="Active",
            Renewal_Status="Pending",
            Office_Code="MDU001",
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
        ),
        "claim": ClaimCreate(
            Policy_ID="TEST-POL-003",
            Vehicle_ID="TEST-VEH-003",
            Claim_Date=date(2026, 10, 22),
            Claim_Type="Third Party",
            Claim_Amount=Decimal("45000.00"),
            Claim_Description="Side collision with a third-party vehicle at a junction; FIR lodged.",
            Place_of_Accident="Madurai",
            Accident_Pincode="625001",
            Accident_Time=time(18, 45),
            Third_Party_Involved=True,
            Injury_Reported=False,
            Police_Report_Available=True,
            FIR_Number="TEST-FIR-003",
        ),
        # Claim B: documents submitted, awaiting surveyor inspection.
        "documents": [
            dict(
                Document_ID="TEST-DOC-003-FIR",
                Document_Type="FIR",
                Document_Name="fir-copy.pdf",
                Document_Submitted_Date=date(2026, 10, 23),
                Document_Status="Submitted",
                OCR_Confidence_Score=Decimal("0.94"),
                Extracted_Text="FIR No: TEST-FIR-003 registered for the reported motor accident.",
                Document_Completeness=Decimal("0.90"),
                Document_Mismatch_Indicator=False,
                Verification_Status="Pending",
            ),
            dict(
                Document_ID="TEST-DOC-003-RC",
                Document_Type="RC",
                Document_Name="rc-copy.pdf",
                Document_Submitted_Date=date(2026, 10, 23),
                Document_Status="Submitted",
                OCR_Confidence_Score=Decimal("0.95"),
                Extracted_Text="Registration Number: TN59EF3003. RC verification record on file.",
                Document_Completeness=Decimal("0.90"),
                Document_Mismatch_Indicator=False,
                Verification_Status="Pending",
            ),
        ],
    },
    {
        "customer_id": "TEST-CUST-004",
        "vehicle_id": "TEST-VEH-004",
        "policy_id": "TEST-POL-004",
        "user_id": "TEST-USER-CUST4",
        "username": "test_customer4",
        "customer": dict(
            Customer_Name="Lakshmi Narayanan",
            Date_of_Birth=date(1997, 11, 2),
            Age=28,
            Gender="Female",
            Phone="9000000103",
            Email="test.customer4@ci-micop.local",
            Address="Thillai Nagar, Trichy, Tamil Nadu",
            City="Trichy",
            State="Tamil Nadu",
            Pincode="620001",
            Occupation="Software Engineer",
            Driving_Experience_Years=7,
            Customer_Type="Individual",
            Previous_Claim_Count=0,
            Driver_Age_Code="A28",
            Driver_Experience_Code="E07",
            Driver_Qualification_Code="GRAD",
            Driver_Type_Code="OWNER",
        ),
        "vehicle": dict(
            Vehicle_Type="Private Car",
            Vehicle_Subtype=None,
            Registration_Number="TN45GH4004",
            Chassis_Number="TESTCHASSIS004",
            Engine_Number="TESTENGINE004",
            Vehicle_Color="Blue",
            Make="Hyundai",
            Make_Code="HYU",
            Model="Venue",
            Variant="SX",
            Manufacturing_Year=2022,
            Registration_Year=2022,
            Vehicle_Age=4,
            Fuel_Type="Petrol",
            Engine_CC=1197,
            CC_PCC_GVW_Code="1197",
            Vehicle_Value=Decimal("900000.00"),
            Usage_Type="Private",
            GVW_KG=None,
            Load_Capacity_KG=None,
            Seating_Capacity=5,
            Permit_Code=None,
            Nature_of_Goods_Code=None,
            Road_Type_Code="URBAN",
            Vehicle_Driven_By_Code="OWNER",
            RTA_Location_Code="TN45",
            Class_Code="PC",
            Zone_Code="A",
            Previous_Claim_Count=0,
            Policy_Start_Date=date(2026, 3, 1),
            Policy_End_Date=date(2027, 3, 1),
        ),
        "policy": dict(
            Policy_Number="TEST-POLICY-004",
            Policy_Type="Comprehensive",
            Policy_Code="COMP",
            Coverage_Type="Own Damage + TP",
            Class_Code="PC",
            Policy_Start_Date=date(2026, 3, 1),
            Policy_End_Date=date(2027, 3, 1),
            Policy_Year="2026",
            Premium_Amount=Decimal("21000.00"),
            Sum_Insured=Decimal("900000.00"),
            IDV=Decimal("870000.00"),
            Deductible_Amount=Decimal("1500.00"),
            No_Claim_Bonus=Decimal("25.00"),
            NCB_Flag=True,
            Policy_Status="Active",
            Renewal_Status="Pending",
            Office_Code="TRY001",
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
        ),
        "claim": ClaimCreate(
            Policy_ID="TEST-POL-004",
            Vehicle_ID="TEST-VEH-004",
            Claim_Date=date(2026, 10, 24),
            Claim_Type="Own Damage",
            Claim_Amount=Decimal("150000.00"),
            Claim_Description="Front-end collision damage after skidding on a wet road; repair estimate obtained.",
            Place_of_Accident="Trichy",
            Accident_Pincode="620001",
            Accident_Time=time(8, 30),
            Third_Party_Involved=False,
            Injury_Reported=False,
            Police_Report_Available=True,
            FIR_Number="TEST-FIR-004",
        ),
        # Claim C: assigned and ready for inspection - fuller documentation
        # than Claim B, still no fabricated inspection progress.
        "documents": [
            dict(
                Document_ID="TEST-DOC-004-FIR",
                Document_Type="FIR",
                Document_Name="fir-copy.pdf",
                Document_Submitted_Date=date(2026, 10, 25),
                Document_Status="Submitted",
                OCR_Confidence_Score=Decimal("0.95"),
                Extracted_Text="FIR No: TEST-FIR-004 registered for the reported motor accident.",
                Document_Completeness=Decimal("0.92"),
                Document_Mismatch_Indicator=False,
                Verification_Status="Pending",
            ),
            dict(
                Document_ID="TEST-DOC-004-RC",
                Document_Type="RC",
                Document_Name="rc-copy.pdf",
                Document_Submitted_Date=date(2026, 10, 25),
                Document_Status="Submitted",
                OCR_Confidence_Score=Decimal("0.96"),
                Extracted_Text="Registration Number: TN45GH4004. RC verification record on file.",
                Document_Completeness=Decimal("0.92"),
                Document_Mismatch_Indicator=False,
                Verification_Status="Pending",
            ),
            dict(
                Document_ID="TEST-DOC-004-REP",
                Document_Type="Repair Estimate",
                Document_Name="repair-estimate.pdf",
                Document_Submitted_Date=date(2026, 10, 25),
                Document_Status="Submitted",
                OCR_Confidence_Score=Decimal("0.93"),
                Extracted_Text="Repair estimate submitted by the garage for vehicle front-end damage.",
                Document_Completeness=Decimal("0.92"),
                Document_Mismatch_Indicator=False,
                Verification_Status="Pending",
            ),
        ],
    },
]


def seed_one_customer(db, spec: dict) -> dict:
    """Creates (or reuses) one customer's full record set. Returns a
    small report dict with every ID created/reused."""
    report = {"customer_id": spec["customer_id"], "username": spec["username"]}

    customer, created = add_if_missing(
        db, Customer, "Customer_ID", spec["customer_id"],
        Customer_ID=spec["customer_id"], **spec["customer"],
    )
    db.flush()
    report["customer_created"] = created

    vehicle, created = add_if_missing(
        db, Vehicle, "Vehicle_ID", spec["vehicle_id"],
        Vehicle_ID=spec["vehicle_id"], Customer_ID=spec["customer_id"], Policy_ID=None,
        **spec["vehicle"],
    )
    db.flush()
    report["vehicle_id"] = spec["vehicle_id"]
    report["vehicle_created"] = created

    policy, created = add_if_missing(
        db, Policy, "Policy_ID", spec["policy_id"],
        Policy_ID=spec["policy_id"], Customer_ID=spec["customer_id"], Vehicle_ID=spec["vehicle_id"],
        **spec["policy"],
    )
    vehicle.Policy_ID = spec["policy_id"]
    db.flush()
    report["policy_id"] = spec["policy_id"]
    report["policy_created"] = created

    _, created = add_if_missing(
        db, AuthenticationUser, "User_ID", spec["user_id"],
        User_ID=spec["user_id"], Username=spec["username"],
        Password_Hash=hash_password(PASSWORD), Role="Customer",
        Customer_ID=spec["customer_id"], Employee_ID=None,
        Email=spec["customer"]["Email"], Phone=spec["customer"]["Phone"],
        Account_Status="Active", Login_Status="Logged Out",
        Last_Login=None, Created_Date=date(2026, 10, 27),
        Failed_Login_Count=0, Permission_Level=1, Insurer_Code=None,
    )
    report["login_created"] = created

    # Commit the base identity records now, before calling the claim
    # service (which runs its own commit/rollback cycle) - isolates this
    # customer's base data from any later failure.
    db.commit()

    # --- Claim (real service) -------------------------------------
    existing_claims = crud_claim.list_by_customer(db, spec["customer_id"])
    if existing_claims:
        claim = existing_claims[0]
        report["claim_created"] = False
    else:
        claim = claim_creation.create_claim_for_customer(db, spec["customer_id"], spec["claim"])
        report["claim_created"] = True
    report["claim_id"] = claim.Claim_ID
    report["claim_number"] = claim.Claim_Number
    report["claim_status"] = claim.Claim_Status

    # --- Documents (plain metadata-only rows, no physical file) ----
    documents_created = []
    for doc_spec in spec["documents"]:
        _, created = add_if_missing(
            db, Document, "Document_ID", doc_spec["Document_ID"],
            Claim_ID=claim.Claim_ID, **doc_spec,
        )
        if created:
            documents_created.append(doc_spec["Document_ID"])
    if spec["documents"]:
        db.commit()
    report["documents_created"] = documents_created
    report["document_ids"] = [d["Document_ID"] for d in spec["documents"]]

    # --- Surveyor assignment (real service) -------------------------
    try:
        assignment = surveyor_assignment.assign_surveyor_to_claim(db, claim.Claim_ID, SURVEYOR_1_EMPLOYEE_ID)
        report["assignment_created"] = True
        report["inspection_id"] = assignment.Inspection_ID
        report["inspection_status"] = assignment.Inspection_Status
    except HTTPException as exc:
        if exc.status_code == 409:
            # Already assigned (to this or another surveyor) - safe to
            # treat as already done; re-running must never raise.
            from app.crud import surveyor_inspection as crud_inspection
            existing = crud_inspection.list_by_claim(db, claim.Claim_ID)
            active = next((i for i in existing if not i.Survey_Report_Submitted), existing[0] if existing else None)
            report["assignment_created"] = False
            report["inspection_id"] = active.Inspection_ID if active else None
            report["inspection_status"] = active.Inspection_Status if active else None
            report["surveyor_id"] = active.Surveyor_ID if active else None
        else:
            raise

    return report


def main():
    db = SessionLocal()
    reports = []
    try:
        for spec in CUSTOMERS:
            reports.append(seed_one_customer(db, spec))
    finally:
        db.close()

    print()
    print("=" * 70)
    print("TEST SURVEYOR-1 SEED DATA - RESULT")
    print("=" * 70)
    for r in reports:
        print()
        print(f"Customer: {r['customer_id']}  (login username: {r['username']})")
        print(f"  Customer row created this run : {r['customer_created']}")
        print(f"  Vehicle  : {r['vehicle_id']} (created this run: {r['vehicle_created']})")
        print(f"  Policy   : {r['policy_id']} (created this run: {r['policy_created']})")
        print(f"  Login account created this run : {r['login_created']}")
        print(f"  Claim    : {r['claim_id']} / {r['claim_number']} (status: {r['claim_status']}, created this run: {r['claim_created']})")
        print(f"  Documents on claim : {r['document_ids']} (created this run: {r['documents_created']})")
        print(f"  Assignment to Surveyor 1 ({SURVEYOR_1_EMPLOYEE_ID}): created this run={r['assignment_created']}, "
              f"Inspection_ID={r['inspection_id']}, Inspection_Status={r['inspection_status']}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
