"""Shared test fixtures.

Per project rules (PostgreSQL only, no SQLite/mocks for the DB layer),
these tests run against the real database configured in backend/.env.
A small, clearly-prefixed set of rows is inserted before the test
session and deleted afterward, regardless of test outcome.
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db_models.authentication_user import AuthenticationUser
from app.db_models.claim import Claim
from app.db_models.customer import Customer
from app.db_models.policy import Policy
from app.db_models.surveyor_inspection import SurveyorInspection
from app.db_models.vehicle import Vehicle
from app.main import app

TEST_PASSWORD = "TestPass123!"

IDS = {
    "customer1": "TEST-CUST-0001",
    "customer2": "TEST-CUST-0002",
    "vehicle1": "TEST-VEH-0001",
    "policy1": "TEST-POL-0001",
    "claim1": "TEST-CLM-0001",
    "inspection1": "TEST-INS-0001",
    "user_customer1": "TEST-USER-CUST1",
    "user_customer2": "TEST-USER-CUST2",
    "user_surveyor": "TEST-USER-SURV1",
    "user_officer": "TEST-USER-OFF1",
    "user_admin": "TEST-USER-ADMIN1",
    "employee_surveyor": "TEST-EMP-SURV1",
    "employee_officer": "TEST-EMP-OFF1",
}


def _make_customer(customer_id: str, name: str) -> Customer:
    return Customer(
        Customer_ID=customer_id,
        Customer_Name=name,
        Date_of_Birth=date(1990, 1, 1),
        Age=35,
        Gender="Female",
        Phone="9990000001",
        Email=f"{customer_id.lower()}@example.com",
        Address="1 Test Street",
        City="TestCity",
        State="TestState",
        Pincode="123456",
        Occupation="Salaried",
        Driving_Experience_Years=10,
        Customer_Type="Individual",
        Previous_Claim_Count=0,
        Driver_Age_Code="DA01",
        Driver_Experience_Code="DE01",
        Driver_Qualification_Code="DQ01",
        Driver_Type_Code="DT01",
    )


@pytest.fixture(scope="session")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="session", autouse=True)
def seed_data(db):
    customer1 = _make_customer(IDS["customer1"], "Test Customer One")
    customer2 = _make_customer(IDS["customer2"], "Test Customer Two")

    vehicle1 = Vehicle(
        Vehicle_ID=IDS["vehicle1"],
        Customer_ID=IDS["customer1"],
        Policy_ID=None,
        Vehicle_Type="Car - Sedan",
        Vehicle_Subtype=None,
        Registration_Number="TEST-REG-0001",
        Chassis_Number="TEST-CHS-0001",
        Engine_Number="TEST-ENG-0001",
        Vehicle_Color="White",
        Make="TestMake",
        Make_Code="MC001",
        Model="TestModel",
        Variant="Base",
        Manufacturing_Year=2022,
        Registration_Year=2022,
        Vehicle_Age=3,
        Fuel_Type="Petrol",
        Engine_CC=1200,
        CC_PCC_GVW_Code="CC01",
        Vehicle_Value=Decimal("1000000.00"),
        Usage_Type="Private",
        GVW_KG=None,
        Load_Capacity_KG=None,
        Seating_Capacity=5,
        Permit_Code=None,
        Nature_of_Goods_Code=None,
        Road_Type_Code="RT01",
        Vehicle_Driven_By_Code="DB01",
        RTA_Location_Code="RTA001",
        Class_Code="CL01",
        Zone_Code="Z01",
        Previous_Claim_Count=0,
        Policy_Start_Date=date(2025, 1, 1),
        Policy_End_Date=date(2026, 1, 1),
    )

    policy1 = Policy(
        Policy_ID=IDS["policy1"],
        Customer_ID=IDS["customer1"],
        Vehicle_ID=IDS["vehicle1"],
        Policy_Number="TEST-POLNUM-0001",
        Policy_Type="Comprehensive",
        Policy_Code="PC01",
        Coverage_Type="Standard",
        Class_Code="CL01",
        Policy_Start_Date=date(2025, 1, 1),
        Policy_End_Date=date(2026, 1, 1),
        Policy_Year="2025-26",
        Premium_Amount=Decimal("15000.00"),
        Sum_Insured=Decimal("1000000.00"),
        IDV=Decimal("950000.00"),
        Deductible_Amount=Decimal("1000.00"),
        No_Claim_Bonus=Decimal("20.00"),
        NCB_Flag=True,
        Policy_Status="Active",
        Renewal_Status="Renewed",
        Office_Code="OFF001",
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
        TPPD_Statutory_Cover_Flag=False,
    )

    claim1 = Claim(
        Claim_ID=IDS["claim1"],
        Policy_ID=IDS["policy1"],
        Customer_ID=IDS["customer1"],
        Vehicle_ID=IDS["vehicle1"],
        Claim_Number="TEST-CLMNUM-0001",
        Claim_Number_Child=None,
        Claim_Date=date(2025, 6, 1),
        Claim_Year="2025-26",
        Claim_Type="Own Damage",
        Claim_Amount=Decimal("50000.00"),
        Approved_Amount=Decimal("45000.00"),
        Claim_Status="Under Investigation",
        Claim_Description="Test claim for automated tests.",
        Claims_History_Code="CH01",
        Incurred_Claims_Code="IC01",
        Nature_of_Loss_Code="NOL01",
        Insurer_NOL_Code="INOL001",
        TPPD_Statutory_Cover_Flag=False,
        Claim_Intimation_Date=date(2025, 6, 2),
        Date_of_Disbursement=date(2025, 6, 20),
        Place_of_Accident="TestCity",
        Accident_Pincode="123456",
        Claim_Processing_Days=18,
        Repair_Duration_Days=10,
        Final_Decision="Approved",
        Decision_Date=date(2025, 6, 15),
        Decision_Reason="Test decision reason.",
        TP_Amount_Claimed=Decimal("0.00"),
        TP_Claims_Paid=Decimal("0.00"),
        TP_Awards_Paid=Decimal("0.00"),
        TP_Expenses_Paid=Decimal("0.00"),
        TP_Interest_Paid=Decimal("0.00"),
        Wider_Legal_Liability_Amount=Decimal("0.00"),
        PA_Owner_Driver_Amount=Decimal("0.00"),
        PA_Others_Amount=Decimal("0.00"),
        Nature_of_Injury_Code="NI01",
        Interim_Award_Flag=False,
        Settlement_Basis_Code="SB01",
        Fatal_NonFatal_Flag=False,
        Open_Provision_Main=Decimal("0.00"),
        Open_Provision_Expenses=Decimal("0.00"),
        Open_Provision_Interest=Decimal("0.00"),
        Closing_Provision_Main=Decimal("0.00"),
        Closing_Provision_Expenses=Decimal("0.00"),
        Closing_Provision_Interest=Decimal("0.00"),
    )

    password_hash = hash_password(TEST_PASSWORD)

    users = [
        AuthenticationUser(
            User_ID=IDS["user_customer1"],
            Username="test_customer1",
            Password_Hash=password_hash,
            Role="Customer",
            Customer_ID=IDS["customer1"],
            Employee_ID=None,
            Email="test_customer1@example.com",
            Phone="9990000001",
            Account_Status="Active",
            Login_Status="Active",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=1,
            Insurer_Code=None,
        ),
        AuthenticationUser(
            User_ID=IDS["user_customer2"],
            Username="test_customer2",
            Password_Hash=password_hash,
            Role="Customer",
            Customer_ID=IDS["customer2"],
            Employee_ID=None,
            Email="test_customer2@example.com",
            Phone="9990000002",
            Account_Status="Active",
            Login_Status="Active",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=1,
            Insurer_Code=None,
        ),
        AuthenticationUser(
            User_ID=IDS["user_surveyor"],
            Username="test_surveyor",
            Password_Hash=password_hash,
            Role="Surveyor",
            Customer_ID=None,
            Employee_ID=IDS["employee_surveyor"],
            Email="test_surveyor@example.com",
            Phone="9990000003",
            Account_Status="Active",
            Login_Status="Active",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=2,
            Insurer_Code=None,
        ),
        AuthenticationUser(
            User_ID=IDS["user_officer"],
            Username="test_officer",
            Password_Hash=password_hash,
            Role="Claims Officer",
            Customer_ID=None,
            Employee_ID=IDS["employee_officer"],
            Email="test_officer@example.com",
            Phone="9990000004",
            Account_Status="Active",
            Login_Status="Active",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=3,
            Insurer_Code=None,
        ),
        AuthenticationUser(
            User_ID=IDS["user_admin"],
            Username="test_admin",
            Password_Hash=password_hash,
            Role="Admin",
            Customer_ID=None,
            Employee_ID=None,
            Email="test_admin@example.com",
            Phone="9990000005",
            Account_Status="Active",
            Login_Status="Active",
            Last_Login=None,
            Created_Date=date(2025, 1, 1),
            Failed_Login_Count=0,
            Permission_Level=9,
            Insurer_Code=None,
        ),
    ]

    inspection1 = SurveyorInspection(
        Inspection_ID=IDS["inspection1"],
        Claim_ID=IDS["claim1"],
        Surveyor_ID=IDS["employee_surveyor"],
        Inspection_Date=date(2025, 6, 5),
        Inspection_Location="Test Garage",
        Vehicle_Condition="Fair",
        Damage_Observed="Yes",
        Damage_Severity="Moderate",
        Parts_Required=2,
        Repair_Recommendation="Repair",
        Surveyor_Comments="Initial test comment.",
        Inspection_Status="Completed",
        Survey_Report_Submitted=True,
        Surveyor_Confidence_Score=Decimal("0.9000"),
    )

    db.add(customer1)
    db.add(customer2)
    db.commit()
    db.add(vehicle1)
    db.commit()
    db.add(policy1)
    db.commit()
    db.query(Vehicle).filter(Vehicle.Vehicle_ID == IDS["vehicle1"]).update({"Policy_ID": IDS["policy1"]})
    db.add(claim1)
    db.add_all(users)
    db.commit()
    db.add(inspection1)
    db.commit()

    yield IDS

    # Teardown: delete everything created above, reverse dependency order.
    db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == IDS["inspection1"]).delete()
    db.query(AuthenticationUser).filter(
        AuthenticationUser.User_ID.in_(
            [
                IDS["user_customer1"],
                IDS["user_customer2"],
                IDS["user_surveyor"],
                IDS["user_officer"],
                IDS["user_admin"],
            ]
        )
    ).delete(synchronize_session=False)
    db.query(Claim).filter(Claim.Claim_ID == IDS["claim1"]).delete()
    # vehicles.Policy_ID -> policies.Policy_ID must be cleared before the
    # policy row can be deleted (same circular FK handled in the Step 2
    # migration).
    db.query(Vehicle).filter(Vehicle.Vehicle_ID == IDS["vehicle1"]).update({"Policy_ID": None})
    db.commit()
    db.query(Policy).filter(Policy.Policy_ID == IDS["policy1"]).delete()
    db.query(Vehicle).filter(Vehicle.Vehicle_ID == IDS["vehicle1"]).delete()
    db.query(Customer).filter(Customer.Customer_ID.in_([IDS["customer1"], IDS["customer2"]])).delete(
        synchronize_session=False
    )
    db.commit()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def get_token(client: TestClient, username: str, password: str = TEST_PASSWORD) -> str:
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def customer1_token(client, seed_data):
    return get_token(client, "test_customer1")


@pytest.fixture(scope="session")
def customer2_token(client, seed_data):
    return get_token(client, "test_customer2")


@pytest.fixture(scope="session")
def surveyor_token(client, seed_data):
    return get_token(client, "test_surveyor")


@pytest.fixture(scope="session")
def officer_token(client, seed_data):
    return get_token(client, "test_officer")


@pytest.fixture(scope="session")
def admin_token(client, seed_data):
    return get_token(client, "test_admin")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_bare_claim(claim_id: str, claim_number: str, seed_data: dict, description: str) -> Claim:
    """A minimal, valid Claim row for assignment-boundary tests (Steps
    5.8.5/5.8.6) - shared here so every test module that needs an
    "unassigned" or "someone else's" claim uses the same shape."""
    return Claim(
        Claim_ID=claim_id,
        Policy_ID=seed_data["policy1"],
        Customer_ID=seed_data["customer1"],
        Vehicle_ID=seed_data["vehicle1"],
        Claim_Number=claim_number,
        Claim_Number_Child=None,
        Claim_Date=date(2026, 1, 1),
        Claim_Year="2026",
        Claim_Type="Own Damage",
        Claim_Amount=Decimal("10000.00"),
        Approved_Amount=Decimal("0.00"),
        Claim_Status="Under Review",
        Claim_Description=description,
        Claims_History_Code="CH01",
        Incurred_Claims_Code="IC01",
        Nature_of_Loss_Code="NOL01",
        Insurer_NOL_Code="INOL001",
        TPPD_Statutory_Cover_Flag=False,
        Claim_Intimation_Date=date(2026, 1, 1),
        Date_of_Disbursement=date(2026, 1, 1),
        Place_of_Accident="TestCity",
        Accident_Pincode="123456",
        Claim_Processing_Days=0,
        Repair_Duration_Days=0,
        Final_Decision="Pending",
        Decision_Date=date(2026, 1, 1),
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
        Open_Provision_Main=Decimal("10000.00"),
        Open_Provision_Expenses=Decimal("0.00"),
        Open_Provision_Interest=Decimal("0.00"),
        Closing_Provision_Main=Decimal("0.00"),
        Closing_Provision_Expenses=Decimal("0.00"),
        Closing_Provision_Interest=Decimal("0.00"),
    )


@pytest.fixture(scope="module")
def unassigned_claim(seed_data):
    """A claim nobody has ever inspected - the "brand new customer claim"
    scenario the surveyor-assignment gap applies to (Steps 5.8.5/5.8.6)."""
    db = SessionLocal()
    claim_id = "TEST-CLM-UNASSIGNED"
    db.add(_make_bare_claim(claim_id, "TEST-CLMNUM-UNASSIGNED", seed_data, "Unassigned test claim."))
    db.commit()
    db.close()

    yield claim_id

    db = SessionLocal()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def other_surveyor_claim(seed_data):
    """A second surveyor with their own claim+inspection, used to prove
    surveyor1 cannot touch surveyor2's assigned claim, inspection,
    damage, or evidence (Steps 5.8.5/5.8.6)."""
    db = SessionLocal()
    employee_id = "TEST-EMP-SURV2"
    user_id = "TEST-USER-SURV2"
    claim_id = "TEST-CLM-SURV2"
    inspection_id = "TEST-INS-SURV2"

    user = AuthenticationUser(
        User_ID=user_id,
        Username="test_surveyor2",
        Password_Hash=hash_password(TEST_PASSWORD),
        Role="Surveyor",
        Customer_ID=None,
        Employee_ID=employee_id,
        Email="test_surveyor2@example.com",
        Phone="9990000006",
        Account_Status="Active",
        Login_Status="Active",
        Last_Login=None,
        Created_Date=date(2025, 1, 1),
        Failed_Login_Count=0,
        Permission_Level=2,
        Insurer_Code=None,
    )

    claim = _make_bare_claim(claim_id, "TEST-CLMNUM-SURV2", seed_data, "Claim assigned to a second surveyor only.")

    inspection = SurveyorInspection(
        Inspection_ID=inspection_id,
        Claim_ID=claim_id,
        Surveyor_ID=employee_id,
        Inspection_Date=date(2026, 1, 2),
        Inspection_Location="TestCity",
        Vehicle_Condition="Good",
        Damage_Observed="No",
        Damage_Severity="Pending",
        Parts_Required=0,
        Repair_Recommendation="Repair",
        Surveyor_Comments="",
        Inspection_Status="In Progress",
        Survey_Report_Submitted=False,
        Surveyor_Confidence_Score=Decimal("0.0000"),
    )

    db.add(user)
    db.add(claim)
    db.commit()
    db.add(inspection)
    db.commit()
    db.close()

    yield {"employee_id": employee_id, "claim_id": claim_id, "inspection_id": inspection_id}

    db = SessionLocal()
    db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == inspection_id).delete()
    db.query(Claim).filter(Claim.Claim_ID == claim_id).delete()
    db.query(AuthenticationUser).filter(AuthenticationUser.User_ID == user_id).delete()
    db.commit()
    db.close()
