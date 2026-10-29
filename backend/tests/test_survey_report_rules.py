"""Database-free tests for the surveyor workflow: schedule restriction,
step order, write locks, camera-capture evidence, submission, finality,
active/history lists and the survey report endpoints.

The crud layer is replaced by an in-memory store (FakeStore) and the auth
dependency is overridden, so the real access checks, workflow rules,
capture validation and routers run - but a guard makes any attempt to open
a database connection fail the test. Evidence files go to pytest's tmp_path.
Run with `pytest --noconftest tests/test_survey_report_rules.py`.

These prove the application logic, not database persistence: the
database-backed equivalents are in tests/test_survey_report.py (deferred
until a test database is available).
"""

import asyncio
import io
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import fitz
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.engine import Engine
from starlette.datastructures import UploadFile

from app.api.v1 import deps
from app.core.config import settings
from app.crud import accident as crud_accident
from app.crud import claim as crud_claim
from app.crud import customer as crud_customer
from app.crud import document as crud_document
from app.crud import evidence as crud_evidence
from app.crud import policy as crud_policy
from app.crud import repair_estimate as crud_repair_estimate
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle as crud_vehicle
from app.crud import vehicle_damage as crud_vehicle_damage
from app.main import app
from app.services import (
    document_storage,
    document_upload,
    evidence_capture,
    evidence_storage,
    evidence_upload,
    survey_report,
    surveyor_workflow,
    workflow_state,
)
from app.services.surveyor_workflow import IST

EMPLOYEE = "EMP-1"
TODAY = datetime.now(IST).date()


def _jpeg(size=(80, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (30, 90, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def no_database(monkeypatch, tmp_path):
    def _refuse(*args, **kwargs):
        raise AssertionError("This test must not connect to a database")

    monkeypatch.setattr(Engine, "connect", _refuse)
    monkeypatch.setattr(Engine, "raw_connection", _refuse)
    monkeypatch.setattr(settings, "EVIDENCE_STORAGE_ROOT", str(tmp_path / "evidence"))
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", str(tmp_path / "documents"))


def _inspection(**overrides):
    values = {
        "Inspection_ID": "INSP-1",
        "Claim_ID": "CLM-1",
        "Surveyor_ID": EMPLOYEE,
        "Inspection_Date": TODAY,
        "Inspection_Location": "Chennai",
        "Vehicle_Condition": "Fair",
        "Damage_Observed": "Yes",
        "Damage_Severity": "Minor",
        "Parts_Required": 2,
        "Repair_Recommendation": "Repair",
        "Surveyor_Comments": "",
        "Inspection_Status": "In Progress",
        "Survey_Report_Submitted": False,
        "Surveyor_Confidence_Score": Decimal("0.0000"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _damage(part="Rear Bumper", cost="15000.00"):
    return SimpleNamespace(
        Damage_ID=f"DMG-{part}",
        Claim_ID="CLM-1",
        Vehicle_ID="VEH-1",
        Damage_Type="Rear Damage",
        Damaged_Part=part,
        Damage_Severity="Minor",
        Damage_Location="Rear",
        Estimated_Damage_Cost=Decimal(cost),
        Repair_or_Replace="Repair",
        Photo_Evidence_Available=True,
        Vehicle_Damage_Mismatch_Indicator=False,
        Damage_Description="Cracked.",
    )


def _evidence(evidence_id="EVD-1", source="Surveyor", status="Pending", name="rear.jpg"):
    return SimpleNamespace(
        Evidence_ID=evidence_id,
        Claim_ID="CLM-1",
        Evidence_Type="Damage Photo",
        Evidence_Date=TODAY,
        Evidence_Source=source,
        File_Name=name,
        Verification_Status=status,
        Image_Quality=Decimal("0.8200"),
        Vehicle_Damage_Detected=True,
        Damage_Severity="Minor",
        Location_Match=True,
        Duplicate_Evidence_Indicator=False,
        Evidence_Confidence_Score=Decimal("0.9100"),
    )


def _capture(inspection_id="INSP-1", surveyor=EMPLOYEE, location_status="captured"):
    return {
        "capture_method": evidence_capture.CAPTURE_METHOD,
        "client": {"captured_at": "2026-10-28T10:00:00+05:30", "latitude": 13.0827, "longitude": 80.2707, "accuracy_m": 12.0},
        "server": {
            "role": "surveyor",
            "received_at": "2026-10-28T10:00:05+05:30",
            "surveyor_employee_id": surveyor,
            "inspection_id": inspection_id,
        },
        "checks": {"location_status": location_status, "max_accuracy_m": 100.0, "client_time_status": "consistent"},
    }


CLAIM = SimpleNamespace(
    Claim_ID="CLM-1",
    Claim_Number="CLM-2026-AAAA",
    Policy_ID="POL-1",
    Customer_ID="CUST-1",
    Vehicle_ID="VEH-1",
    Claim_Date=date(2026, 9, 1),
    Claim_Intimation_Date=date(2026, 9, 2),
    Claim_Type="Own Damage",
    Claim_Status="Under Review",
    Claim_Amount=Decimal("50000.00"),
    Approved_Amount=Decimal("0.00"),
    Final_Decision="Pending",
    Claim_Description="Rear-ended at a signal.",
)
CUSTOMER = SimpleNamespace(
    Customer_ID="CUST-1",
    Customer_Name="Asha R",
    Date_of_Birth=date(1990, 1, 1),
    Phone="9990000001",
    Email="asha@example.com",
    Address="1 Private Street",
)
VEHICLE = SimpleNamespace(Registration_Number="TN01AB1234", Make="Maruti", Model="Swift", Manufacturing_Year=2021)
POLICY = SimpleNamespace(Policy_Number="POL-NUM-1", Policy_Type="Comprehensive")
ACCIDENT = SimpleNamespace(
    Accident_ID="ACC-1",
    Claim_ID="CLM-1",
    Accident_Date=date(2026, 8, 30),
    Accident_Time=time(18, 5),
    Accident_Type="Collision",
    Accident_Location="Anna Salai",
    Accident_City="Chennai",
    Accident_State="Tamil Nadu",
    Accident_Pincode="600002",
    Accident_Description="Hit from behind.",
    Weather_Condition="Clear",
    Road_Condition="Dry",
    Road_Type_Code="RT01",
    Police_Report_Available=True,
    FIR_Number=None,
    Third_Party_Involved=True,
    Injury_Reported=False,
    Witness_Available=False,
)


class FakeStore:
    """In-memory stand-ins for every crud call the surveyor code makes."""

    def __init__(self, monkeypatch, inspections=None, damages=None, evidence=None, captures=None):
        self.inspections = inspections if inspections is not None else [_inspection()]
        self.damages = damages if damages is not None else []
        self.evidence = evidence if evidence is not None else []
        self.captures = captures if captures is not None else {}
        self.updates = []
        self.created = []
        self.documents = []
        self._ids = iter(range(100, 1000))

        def assigned(db, claim_id, employee_id):
            return any(i.Claim_ID == claim_id and i.Surveyor_ID == employee_id for i in self.inspections)

        def update(db, inspection, data):
            self.updates.append(dict(data))
            for field, value in data.items():
                setattr(inspection, field, value)
            return inspection

        def create(kind):
            def _create(db, row):
                self.created.append(row)
                (self.damages if kind == "damage" else self.evidence).append(row)
                return row

            return _create

        patches = [
            (crud_claim, "get", lambda db, claim_id: CLAIM if claim_id == CLAIM.Claim_ID else None),
            (crud_claim, "surveyor_is_assigned", assigned),
            (crud_customer, "get", lambda db, customer_id: CUSTOMER),
            (crud_vehicle, "get", lambda db, vehicle_id: VEHICLE),
            (crud_policy, "get", lambda db, policy_id: POLICY),
            (crud_accident, "list_by_claim", lambda db, claim_id: [ACCIDENT]),
            (crud_repair_estimate, "list_by_claim", lambda db, claim_id: []),
            (crud_inspection, "list_by_claim", lambda db, claim_id: [i for i in self.inspections if i.Claim_ID == claim_id]),
            (crud_inspection, "list_by_surveyor", lambda db, employee_id: [i for i in self.inspections if i.Surveyor_ID == employee_id]),
            (crud_inspection, "get", lambda db, inspection_id: next((i for i in self.inspections if i.Inspection_ID == inspection_id), None)),
            (crud_inspection, "update", update),
            (crud_vehicle_damage, "list_by_claim", lambda db, claim_id: list(self.damages)),
            (crud_vehicle_damage, "create", create("damage")),
            (crud_vehicle_damage, "generate_damage_id", lambda db: f"DMG-{next(self._ids)}"),
            (crud_evidence, "list_by_claim", lambda db, claim_id: list(self.evidence)),
            (crud_evidence, "create", create("evidence")),
            (crud_evidence, "generate_evidence_id", lambda db: f"EVD-{next(self._ids)}"),
            (crud_evidence, "get", lambda db, evidence_id: next((e for e in self.evidence if e.Evidence_ID == evidence_id), None)),
            (crud_document, "list_by_claim", lambda db, claim_id: list(self.documents)),
            (crud_document, "get", lambda db, document_id: next((d for d in self.documents if d.Document_ID == document_id), None)),
            (crud_document, "create", self._create_document),
            (crud_document, "generate_document_id", lambda db: f"DOC-{next(self._ids)}"),
            (evidence_capture, "read_metadata", self._read_metadata),
        ]
        for module, name, value in patches:
            monkeypatch.setattr(module, name, value)
        self._real_read_metadata = FakeStore._real_read

    _real_read = staticmethod(evidence_capture.read_metadata)

    def _create_document(self, db, row):
        self.documents.append(row)
        return row

    def _read_metadata(self, evidence):
        if evidence.Evidence_ID in self.captures:
            return self.captures[evidence.Evidence_ID]
        return FakeStore._real_read(evidence)  # photos stored by the capture service in tmp_path


class FakeSession:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.rolled_back = False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self):
        self.rolled_back = True

    def refresh(self, row):
        pass


def complete_store(monkeypatch, **overrides):
    """All steps complete: damage observed and recorded, one qualifying photo."""
    params = {"damages": [_damage()], "evidence": [_evidence()], "captures": {"EVD-1": _capture()}}
    params.update(overrides)
    return FakeStore(monkeypatch, **params)


# ---------------------------------------------------------------- rules and schedule


def test_own_inspection_prefers_the_active_one_and_ignores_other_surveyors():
    submitted = _inspection(Inspection_ID="INSP-1", Survey_Report_Submitted=True)
    active = _inspection(Inspection_ID="INSP-2")
    other = _inspection(Inspection_ID="INSP-3", Surveyor_ID="EMP-2")
    assert surveyor_workflow.own_inspection([submitted, active, other], EMPLOYEE) is active
    assert surveyor_workflow.own_inspection([submitted, other], EMPLOYEE) is submitted
    assert surveyor_workflow.own_inspection([other], EMPLOYEE) is None


def test_incomplete_inspection_fields():
    complete = vars(_inspection())
    assert surveyor_workflow.incomplete_inspection_fields(complete) == []
    assert surveyor_workflow.incomplete_inspection_fields({**complete, "Damage_Severity": "Pending"}) == ["Damage_Severity"]
    assert surveyor_workflow.incomplete_inspection_fields({**complete, "Damage_Observed": "No", "Damage_Severity": "Pending"}) == []
    assert surveyor_workflow.incomplete_inspection_fields({**complete, "Vehicle_Condition": "Damaged"}) == ["Vehicle_Condition"]


def test_schedule_opens_at_midnight_ist_on_the_scheduled_date():
    inspection = _inspection(Inspection_Date=date(2026, 10, 28))
    start = surveyor_workflow.scheduled_start(inspection)
    assert start.isoformat() == "2026-10-28T00:00:00+05:30"
    assert not surveyor_workflow.schedule_reached(inspection, start - timedelta(seconds=1))
    assert surveyor_workflow.schedule_reached(inspection, start)
    # The same instant expressed in UTC is judged identically.
    from datetime import timezone

    assert surveyor_workflow.schedule_reached(inspection, datetime(2026, 10, 27, 18, 30, tzinfo=timezone.utc))
    info = surveyor_workflow.schedule_info(inspection, start - timedelta(hours=1))
    assert info["reached"] is False and info["has_time"] is False
    assert "28 October 2026" in info["message"]


def test_qualifying_photo_needs_the_capture_record_not_just_the_source():
    inspection = _inspection()
    assert not evidence_capture.qualifies_for_inspection(None, inspection)  # source "Surveyor" alone
    assert not evidence_capture.qualifies_for_inspection(_capture(surveyor="EMP-2"), inspection)
    assert not evidence_capture.qualifies_for_inspection(_capture(inspection_id="INSP-OLD"), inspection)
    assert not evidence_capture.qualifies_for_inspection(_capture(location_status="unavailable"), inspection)
    assert not evidence_capture.qualifies_for_inspection(_capture(location_status="accuracy_insufficient"), inspection)
    assert evidence_capture.qualifies_for_inspection(_capture(), inspection)


def test_missing_records(monkeypatch):
    store = FakeStore(monkeypatch, evidence=[_evidence(source="Surveyor")])  # uploaded, no capture record
    inspection = store.inspections[0]
    problems = surveyor_workflow.missing_records(None, inspection, "Yes")
    assert len(problems) == 2
    store.damages = [_damage()]
    store.captures = {"EVD-1": _capture()}
    assert surveyor_workflow.missing_records(None, inspection, "Yes") == []


def test_workflow_summary(monkeypatch):
    store = FakeStore(monkeypatch)
    summary = surveyor_workflow.workflow_summary(None, store.inspections[0])
    assert summary["inspection_complete"] is True
    assert summary["damage_required"] is True and summary["damage_complete"] is False
    assert summary["evidence_complete"] is False and summary["report_available"] is False
    assert summary["schedule"]["reached"] is True


# ---------------------------------------------------------------- write locks


def test_writes_are_refused_before_the_scheduled_date(monkeypatch):
    FakeStore(monkeypatch, inspections=[_inspection(Inspection_Date=TODAY + timedelta(days=2), Inspection_Status="Scheduled")])
    with pytest.raises(HTTPException) as error:
        surveyor_workflow.require_writable_step(None, "CLM-1", EMPLOYEE, surveyor_workflow.STEP_DAMAGE)
    assert error.value.status_code == 409
    assert "will become available on" in error.value.detail


def test_writes_are_refused_after_submission(monkeypatch):
    FakeStore(monkeypatch, inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed")])
    with pytest.raises(HTTPException) as error:
        surveyor_workflow.require_writable_step(None, "CLM-1", EMPLOYEE, surveyor_workflow.STEP_EVIDENCE)
    assert error.value.status_code == 409
    assert "already been submitted" in error.value.detail


def test_steps_cannot_be_skipped(monkeypatch):
    store = FakeStore(monkeypatch, inspections=[_inspection(Repair_Recommendation="Pending")])
    with pytest.raises(HTTPException) as error:
        surveyor_workflow.require_writable_step(None, "CLM-1", EMPLOYEE, surveyor_workflow.STEP_DAMAGE)
    assert "Complete and save the Inspection step first" in error.value.detail

    store.inspections[0].Repair_Recommendation = "Repair"
    surveyor_workflow.require_writable_step(None, "CLM-1", EMPLOYEE, surveyor_workflow.STEP_DAMAGE)  # now fine
    with pytest.raises(HTTPException) as error:
        surveyor_workflow.require_writable_step(None, "CLM-1", EMPLOYEE, surveyor_workflow.STEP_EVIDENCE)
    assert "save at least one vehicle damage record" in error.value.detail


def test_unassigned_surveyor_cannot_write(monkeypatch):
    FakeStore(monkeypatch)
    with pytest.raises(HTTPException) as error:
        surveyor_workflow.require_writable_step(None, "CLM-1", "EMP-2", surveyor_workflow.STEP_DAMAGE)
    assert error.value.status_code == 403


# ---------------------------------------------------------------- camera capture service


def _capture_call(db, content=None, **overrides):
    params = {
        "claim_id": "CLM-1",
        "evidence_type": "Vehicle Damage Close-up",
        "captured_at": datetime.now(IST).isoformat(),
        "latitude": 13.0827,
        "longitude": 80.2707,
        "accuracy_m": 15.0,
        "location_error": None,
    }
    params.update(overrides)
    photo = UploadFile(file=io.BytesIO(_jpeg() if content is None else content), filename="client-name.exe")
    return asyncio.run(evidence_upload.capture_evidence_for_surveyor(db, EMPLOYEE, photo=photo, **params))


def test_capture_stores_the_photo_with_server_established_metadata(monkeypatch, tmp_path):
    store = FakeStore(monkeypatch, damages=[_damage()])
    evidence, metadata = _capture_call(FakeSession())

    assert evidence.Evidence_Source == "Surveyor"  # set by the server
    assert evidence.Verification_Status == "Pending"  # no AI analysis claimed
    assert evidence.File_Name.startswith("camera-capture-") and evidence.File_Name.endswith(".jpg")
    assert metadata["server"]["surveyor_employee_id"] == EMPLOYEE  # from the JWT path, not the request
    assert metadata["server"]["inspection_id"] == "INSP-1"
    assert metadata["server"]["image_format"] == "JPEG" and metadata["server"]["width"] == 80
    assert metadata["checks"]["location_status"] == "captured"
    assert metadata["checks"]["client_time_status"] == "consistent"
    assert datetime.fromisoformat(metadata["server"]["received_at"]).tzinfo is not None

    # The photo and its capture record are on disk; the record makes it qualify.
    assert evidence_capture.read_metadata(evidence) == metadata
    assert surveyor_workflow.qualifying_photo_count(None, store.inspections[0]) == 1


@pytest.mark.parametrize(
    "content, message",
    [
        (b"\xff\xd8\xff" + b"garbage" * 10, "could not be read as an image"),
        (b"%PDF-1.7 not an image", "must be a JPEG or PNG"),
        (b"", "empty"),
    ],
)
def test_capture_rejects_invalid_image_content(monkeypatch, content, message):
    store = FakeStore(monkeypatch, damages=[_damage()])
    with pytest.raises(HTTPException) as error:
        _capture_call(FakeSession(), content=content)
    assert error.value.status_code == 400 and message in error.value.detail
    assert store.created == []


def test_capture_accepts_png_and_rejects_oversized_photos(monkeypatch):
    FakeStore(monkeypatch, damages=[_damage()])
    evidence, metadata = _capture_call(FakeSession(), content=_png())
    assert evidence.File_Name.endswith(".png") and metadata["server"]["image_format"] == "PNG"

    monkeypatch.setattr(settings, "EVIDENCE_MAX_UPLOAD_BYTES", 100)
    with pytest.raises(HTTPException) as error:
        _capture_call(FakeSession())
    assert error.value.status_code == 400 and "maximum allowed size" in error.value.detail


def test_missing_or_poor_location_is_stored_but_flagged_and_does_not_qualify(monkeypatch):
    store = FakeStore(monkeypatch, damages=[_damage()])
    _, missing = _capture_call(FakeSession(), latitude=None, longitude=None, accuracy_m=None, location_error="permission_denied")
    assert missing["checks"]["location_status"] == "unavailable"
    assert missing["client"]["error"] == "permission_denied"

    _, poor = _capture_call(FakeSession(), accuracy_m=850.0)
    assert poor["checks"]["location_status"] == "accuracy_insufficient"

    assert surveyor_workflow.qualifying_photo_count(None, store.inspections[0]) == 0


def test_capture_flags_implausible_client_time_and_rejects_invalid_coordinates(monkeypatch):
    FakeStore(monkeypatch, damages=[_damage()])
    _, metadata = _capture_call(FakeSession(), captured_at="2020-01-01T00:00:00+05:30")
    assert metadata["checks"]["client_time_status"] == "inconsistent"
    _, metadata = _capture_call(FakeSession(), captured_at=None)
    assert metadata["checks"]["client_time_status"] == "missing"
    with pytest.raises(HTTPException) as error:
        _capture_call(FakeSession(), latitude=123.0)
    assert error.value.status_code == 400


def test_capture_is_refused_before_the_schedule_and_cleans_up_after_a_failed_save(monkeypatch, tmp_path):
    store = FakeStore(monkeypatch, damages=[_damage()], inspections=[_inspection(Inspection_Date=TODAY + timedelta(days=1))])
    with pytest.raises(HTTPException) as error:
        _capture_call(FakeSession())
    assert error.value.status_code == 409

    store.inspections[0].Inspection_Date = TODAY
    with pytest.raises(HTTPException) as error:
        _capture_call(FakeSession(fail_commit=True))
    assert error.value.status_code == 500
    assert list((tmp_path / "evidence").rglob("*")) == [] or all(p.is_dir() for p in (tmp_path / "evidence").rglob("*"))


# ---------------------------------------------------------------- report builder


def test_report_is_refused_while_the_workflow_is_incomplete(monkeypatch):
    FakeStore(monkeypatch, damages=[_damage()], evidence=[_evidence()])  # uploaded photo, no capture record
    with pytest.raises(HTTPException) as error:
        survey_report.build_survey_report(None, "CLM-1", EMPLOYEE)
    assert error.value.status_code == 409
    assert "in-app camera" in error.value.detail


def test_draft_report_contents(monkeypatch):
    complete_store(
        monkeypatch,
        damages=[_damage(), _damage("Tail Lamp", "2500.50")],
        evidence=[_evidence(), _evidence("EVD-2", source="Customer", status="Verified", name="front.png")],
    )
    report = survey_report.build_survey_report(None, "CLM-1", EMPLOYEE)

    assert report["report_status"] == "Draft"
    assert report["customer"] == {"Customer_ID": "CUST-1", "Customer_Name": "Asha R"}
    assert report["policy"] == {"Policy_Number": "POL-NUM-1", "Policy_Type": "Comprehensive"}
    assert [d["Damaged_Part"] for d in report["vehicle_damage"]] == ["Rear Bumper", "Tail Lamp"]
    assert report["total_estimated_damage_cost"] == Decimal("17500.50")
    # Only the surveyor's own capture - the customer's photo is not part of the report.
    (captured,) = report["evidence"]
    assert captured["Evidence_ID"] == "EVD-1"
    assert captured["analysis"] is None and captured["qualifying_capture"] is True
    assert captured["capture"]["client"]["accuracy_m"] == 12.0
    flat = repr(report)
    for private in ("Date_of_Birth", "9990000001", "asha@example.com", "1 Private Street"):
        assert private not in flat


def test_submitted_report_stays_available_and_flags_invalid_stored_values(monkeypatch):
    FakeStore(
        monkeypatch,
        inspections=[_inspection(Vehicle_Condition="Damaged", Survey_Report_Submitted=True, Inspection_Status="Completed")],
    )
    report = survey_report.build_survey_report(None, "CLM-1", EMPLOYEE)
    assert report["report_status"] == "Submitted"
    assert report["invalid_values"] == [{"field": "Vehicle_Condition", "label": "Vehicle Condition", "value": "Damaged"}]


# ---------------------------------------------------------------- routers (auth and the crud layer faked)


@pytest.fixture()
def client():
    user = SimpleNamespace(Role="Surveyor", Employee_ID=EMPLOYEE, Customer_ID=None, Account_Status="Active")
    app.dependency_overrides[deps.get_current_user] = lambda: user
    app.dependency_overrides[deps.get_db] = lambda: FakeSession()
    yield TestClient(app), user
    app.dependency_overrides.clear()


def _patch(test_client, body, inspection_id="INSP-1"):
    return test_client.patch(f"/api/v1/surveyor/inspections/{inspection_id}", json=body)


def test_claim_detail_carries_the_authoritative_workflow(client, monkeypatch):
    test_client, _ = client
    complete_store(monkeypatch)
    body = test_client.get("/api/v1/surveyor/claims/CLM-1").json()
    workflow = body["workflow"]
    assert workflow["inspection_id"] == "INSP-1"
    assert workflow["evidence_complete"] is True and workflow["report_available"] is True
    assert workflow["schedule"]["reached"] is True
    assert body["evidence"][0]["qualifying_capture"] is True
    assert body["evidence"][0]["capture"]["checks"]["location_status"] == "captured"


def test_inspection_updates_are_refused_before_the_scheduled_date(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch, inspections=[_inspection(Inspection_Date=TODAY + timedelta(days=3), Inspection_Status="Scheduled")])
    response = _patch(test_client, {"Vehicle_Condition": "Good"})
    assert response.status_code == 409 and "will become available on" in response.json()["detail"]
    assert _patch(test_client, {"Survey_Report_Submitted": True}).status_code == 409
    assert store.updates == []


def test_saving_findings_starts_the_inspection_and_completed_is_reserved_for_submission(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch, inspections=[_inspection(Inspection_Status="Assigned")])
    assert _patch(test_client, {"Vehicle_Condition": "Good"}).status_code == 200
    assert store.updates[-1] == {"Vehicle_Condition": "Good", "Inspection_Status": "In Progress"}

    response = _patch(test_client, {"Inspection_Status": "Completed"})
    assert response.status_code == 400


def test_invalid_inspection_values_are_rejected(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch)
    for body in ({"Vehicle_Condition": "Damaged"}, {"Parts_Required": -1}, {"Damage_Observed": "Maybe"}):
        assert _patch(test_client, body).status_code == 422
    assert store.updates == []


def test_inspection_date_and_location_are_ignored_and_nulls_are_not_written(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch)
    response = _patch(
        test_client,
        {"Inspection_Date": "2020-01-01", "Inspection_Location": "Elsewhere", "Vehicle_Condition": None, "Parts_Required": 3},
    )
    assert response.status_code == 200
    assert store.updates == [{"Parts_Required": 3}]


def test_submission_needs_a_camera_captured_photo_not_just_a_surveyor_source(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch, damages=[_damage()], evidence=[_evidence(source="Surveyor")])
    response = _patch(test_client, {"Survey_Report_Submitted": True})
    assert response.status_code == 400
    assert "in-app camera" in response.json()["detail"]
    assert store.updates == []


def test_submission_needs_a_damage_record_when_damage_was_observed(client, monkeypatch):
    test_client, _ = client
    complete_store(monkeypatch, damages=[])
    response = _patch(test_client, {"Survey_Report_Submitted": True})
    assert response.status_code == 400 and "no vehicle damage record" in response.json()["detail"]


def test_complete_submission_is_final(client, monkeypatch):
    test_client, user = client
    store = complete_store(monkeypatch)
    response = _patch(test_client, {"Survey_Report_Submitted": True})
    assert response.status_code == 200
    assert store.updates == [{"Survey_Report_Submitted": True, "Inspection_Status": "Completed"}]

    for role in ("Surveyor", "Admin"):
        user.Role = role
        for body in ({"Survey_Report_Submitted": False}, {"Vehicle_Condition": "Poor"}, {"Surveyor_Comments": "x"}):
            assert _patch(test_client, body).status_code == 409
    assert len(store.updates) == 1


def test_admin_cannot_submit_a_surveyors_report(client, monkeypatch):
    test_client, user = client
    user.Role = "Admin"
    user.Employee_ID = None
    store = complete_store(monkeypatch)
    assert _patch(test_client, {"Survey_Report_Submitted": True}).status_code == 403
    assert store.updates == []


def test_damage_and_evidence_writes_are_refused_after_submission(client, monkeypatch):
    test_client, _ = client
    store = complete_store(monkeypatch, inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed")])
    damage = test_client.post(
        "/api/v1/surveyor/vehicle-damage",
        json={
            "Claim_ID": "CLM-1",
            "Damage_Type": "Rear Damage",
            "Damaged_Part": "Door",
            "Damage_Severity": "Minor",
            "Damage_Location": "Rear",
            "Estimated_Damage_Cost": "100",
            "Repair_or_Replace": "Repair",
            "Damage_Description": "Dent.",
        },
    )
    assert damage.status_code == 409
    capture = test_client.post(
        "/api/v1/surveyor/evidence/capture",
        data={"claim_id": "CLM-1", "evidence_type": "Vehicle Damage Close-up", "latitude": "13.08", "longitude": "80.27", "accuracy_m": "10"},
        files={"photo": ("capture.jpg", _jpeg(), "image/jpeg")},
    )
    assert capture.status_code == 409
    upload = test_client.post(
        "/api/v1/surveyor/evidence",
        data={"claim_id": "CLM-1", "evidence_type": "Damage Photo", "evidence_date": str(TODAY), "evidence_source": "Surveyor"},
        files={"file": ("photo.jpg", _jpeg(), "image/jpeg")},
    )
    assert upload.status_code == 410  # the file-upload path is retired for everyone
    assert store.created == []


def test_capture_endpoint_saves_a_qualifying_photo(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch, damages=[_damage()])
    response = test_client.post(
        "/api/v1/surveyor/evidence/capture",
        data={
            "claim_id": "CLM-1",
            "evidence_type": "Vehicle Damage Close-up",
            "captured_at": datetime.now(IST).isoformat(),
            "latitude": "13.0827",
            "longitude": "80.2707",
            "accuracy_m": "9.5",
            # A forged identity in the form is simply ignored.
            "surveyor_employee_id": "EMP-FORGED",
        },
        files={"photo": ("capture.jpg", _jpeg(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["Evidence_Source"] == "Surveyor"
    assert body["qualifying_capture"] is True
    assert body["capture"]["server"]["surveyor_employee_id"] == EMPLOYEE
    assert len(store.created) == 1


def test_active_inspections_and_history_are_split_by_submission(client, monkeypatch):
    test_client, _ = client
    FakeStore(
        monkeypatch,
        inspections=[
            _inspection(Inspection_ID="INSP-OLD", Survey_Report_Submitted=True, Inspection_Status="Completed"),
            _inspection(Inspection_ID="INSP-NEW"),
            _inspection(Inspection_ID="INSP-OTHER", Surveyor_ID="EMP-2"),
        ],
    )
    active = test_client.get("/api/v1/surveyor/active-inspections").json()
    history = test_client.get("/api/v1/surveyor/survey-reports").json()
    assert [row["inspection"]["Inspection_ID"] for row in active] == ["INSP-NEW"]
    assert [row["inspection"]["Inspection_ID"] for row in history] == ["INSP-OLD"]
    assert active[0]["claim"]["Claim_Number"] == "CLM-2026-AAAA"
    assert active[0]["schedule"]["reached"] is True


def test_history_report_endpoints_enforce_ownership_and_submission(client, monkeypatch):
    test_client, _ = client
    FakeStore(
        monkeypatch,
        inspections=[
            _inspection(Inspection_ID="INSP-DONE", Survey_Report_Submitted=True, Inspection_Status="Completed"),
            _inspection(Inspection_ID="INSP-DRAFT"),
            _inspection(Inspection_ID="INSP-THEIRS", Surveyor_ID="EMP-2", Survey_Report_Submitted=True),
        ],
    )
    ok = test_client.get("/api/v1/surveyor/survey-reports/INSP-DONE/report")
    assert ok.status_code == 200 and ok.json()["report_status"] == "Submitted"
    pdf = test_client.get("/api/v1/surveyor/survey-reports/INSP-DONE/report.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert test_client.get("/api/v1/surveyor/survey-reports/INSP-DRAFT/report").status_code == 409
    assert test_client.get("/api/v1/surveyor/survey-reports/INSP-THEIRS/report.pdf").status_code == 403
    assert test_client.get("/api/v1/surveyor/survey-reports/INSP-NONE/report").status_code == 404


def test_report_endpoints_return_the_same_data_and_never_change_anything(client, monkeypatch):
    test_client, _ = client
    store = complete_store(monkeypatch, damages=[_damage("Tail Lamp")])
    body = test_client.get("/api/v1/surveyor/claims/CLM-1/report").json()
    pdf = test_client.get("/api/v1/surveyor/claims/CLM-1/report.pdf")
    assert pdf.headers["content-type"] == "application/pdf"
    assert 'filename="survey-report-CLM-2026-AAAA.pdf"' in pdf.headers["content-disposition"]
    text = " ".join(page.get_text() for page in fitz.open("pdf", pdf.content)).replace("\n", " ")
    for value in (
        body["claim"]["Claim_Number"],
        body["customer"]["Customer_Name"],
        body["vehicle"]["Registration_Number"],
        body["inspection"]["Inspection_ID"],
        "Tail Lamp",
        "In-app camera",
        "13.082700, 80.270700",
        "Location captured",
        "Not analysed yet",
    ):
        assert value in text, value
    assert store.updates == [] and store.created == []


@pytest.mark.parametrize("role", ["Customer", "Claims Officer", "Admin"])
def test_only_surveyors_can_read_reports(client, monkeypatch, role):
    test_client, user = client
    user.Role = role
    complete_store(monkeypatch)
    for path in ("/api/v1/surveyor/claims/CLM-1/report", "/api/v1/surveyor/claims/CLM-1/report.pdf", "/api/v1/surveyor/survey-reports"):
        assert test_client.get(path).status_code == 403


def test_unassigned_surveyor_gets_403(client, monkeypatch):
    test_client, user = client
    user.Employee_ID = "EMP-2"
    complete_store(monkeypatch)
    for path in ("/api/v1/surveyor/claims/CLM-1", "/api/v1/surveyor/claims/CLM-1/report", "/api/v1/surveyor/claims/CLM-1/report.pdf"):
        assert test_client.get(path).status_code == 403



# ---------------------------------------------------------------- schedule boundary


def test_schedule_unlocks_exactly_at_midnight_ist_and_names_the_date(monkeypatch):
    inspection = _inspection(Inspection_Date=date(2026, 10, 28))
    from datetime import timezone

    # 27 Oct 18:29:59 UTC = 27 Oct 23:59:59 IST - one second before.
    assert not surveyor_workflow.schedule_reached(inspection, datetime(2026, 10, 27, 18, 29, 59, tzinfo=timezone.utc))
    assert surveyor_workflow.schedule_reached(inspection, datetime(2026, 10, 27, 18, 30, 0, tzinfo=timezone.utc))
    assert surveyor_workflow.schedule_message(inspection).startswith("This inspection will become available on 28 October 2026")


def test_premature_requests_are_rejected_and_allowed_on_the_date(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch, inspections=[_inspection(Inspection_Date=TODAY + timedelta(days=1))])
    assert _patch(test_client, {"Vehicle_Condition": "Good"}).status_code == 409
    store.inspections[0].Inspection_Date = TODAY
    assert _patch(test_client, {"Vehicle_Condition": "Good"}).status_code == 200


# ---------------------------------------------------------------- separation: the surveyor side


def test_surveyor_views_contain_only_their_own_camera_captures(client, monkeypatch):
    test_client, _ = client
    complete_store(
        monkeypatch,
        evidence=[
            _evidence("EVD-1"),  # this surveyor's capture for this inspection
            _evidence("EVD-CUST", source="Customer", name="customer.jpg"),  # dataset row marked Customer
            _evidence("EVD-UPLOAD", source="Surveyor", name="upload.jpg"),  # "Surveyor" source but no capture record
            _evidence("EVD-OTHER", name="other.jpg"),  # another surveyor's capture
            _evidence("EVD-OLD", name="old.jpg"),  # an earlier inspection's capture
        ],
        captures={
            "EVD-1": _capture(),
            "EVD-OTHER": _capture(surveyor="EMP-2"),
            "EVD-OLD": _capture(inspection_id="INSP-OLD"),
        },
    )
    detail = test_client.get("/api/v1/surveyor/claims/CLM-1").json()
    assert [e["Evidence_ID"] for e in detail["evidence"]] == ["EVD-1"]
    report = test_client.get("/api/v1/surveyor/claims/CLM-1/report").json()
    assert [e["Evidence_ID"] for e in report["evidence"]] == ["EVD-1"]
    pdf_text = " ".join(page.get_text() for page in fitz.open("pdf", test_client.get("/api/v1/surveyor/claims/CLM-1/report.pdf").content))
    assert "customer.jpg" not in pdf_text and "upload.jpg" not in pdf_text


def test_customer_photos_never_satisfy_the_surveyor_photo_requirement(client, monkeypatch):
    test_client, _ = client
    customer_record = {**_capture(), "server": {"role": "customer", "customer_id": "CUST-1", "claim_id": "CLM-1"}}
    store = FakeStore(
        monkeypatch,
        damages=[_damage()],
        evidence=[_evidence("EVD-CUST", source="Customer"), _evidence("EVD-CUSTCAP")],
        captures={"EVD-CUSTCAP": customer_record},
    )
    response = _patch(test_client, {"Survey_Report_Submitted": True})
    assert response.status_code == 400 and "in-app camera" in response.json()["detail"]
    assert store.updates == []


def test_submitted_claim_with_customer_photos_does_not_show_them(client, monkeypatch):
    test_client, _ = client
    FakeStore(
        monkeypatch,
        inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed")],
        evidence=[_evidence("EVD-CUST", source="Customer", status="Verified")],
    )
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").json()["evidence"] == []
    assert test_client.get("/api/v1/surveyor/claims/CLM-1/report").json()["evidence"] == []


def test_evidence_image_endpoint_serves_only_the_surveyors_own_captures(client, monkeypatch):
    test_client, user = client
    store = FakeStore(monkeypatch, damages=[_damage()], evidence=[_evidence("EVD-CUST", source="Customer")])
    evidence, _ = _capture_call(FakeSession())
    store.evidence.append(evidence)

    image = test_client.get(f"/api/v1/surveyor/evidence/{evidence.Evidence_ID}/image")
    assert image.status_code == 200 and image.content.startswith(b"\xff\xd8\xff")
    assert test_client.get("/api/v1/surveyor/evidence/EVD-CUST/image").status_code == 404
    assert test_client.get("/api/v1/surveyor/evidence/EVD-NONE/image").status_code == 404

    user.Employee_ID = "EMP-2"  # another surveyor (not assigned here)
    assert test_client.get(f"/api/v1/surveyor/evidence/{evidence.Evidence_ID}/image").status_code == 404
    user.Role, user.Employee_ID, user.Customer_ID = "Customer", None, "CUST-1"
    assert test_client.get(f"/api/v1/surveyor/evidence/{evidence.Evidence_ID}/image").status_code == 403
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").status_code == 403


def test_capture_evidence_date_is_per_photo_and_validated(monkeypatch):
    FakeStore(monkeypatch, damages=[_damage()], inspections=[_inspection(Inspection_Date=TODAY - timedelta(days=3))])
    evidence, _ = _capture_call(FakeSession(), evidence_date=str(TODAY - timedelta(days=1)), evidence_type="Accident Scene / Surroundings")
    assert evidence.Evidence_Date == TODAY - timedelta(days=1)
    assert evidence.Evidence_Type == "Accident Scene / Surroundings"
    for bad in (str(TODAY + timedelta(days=1)), str(TODAY - timedelta(days=10)), "not-a-date"):
        with pytest.raises(HTTPException) as error:
            _capture_call(FakeSession(), evidence_date=bad)
        assert error.value.status_code == 400
    with pytest.raises(HTTPException):
        _capture_call(FakeSession(), evidence_type="Damage Photo")  # dataset types are not capture types


# ---------------------------------------------------------------- separation: the customer side


def test_customer_accident_photos_never_become_surveyor_evidence(client, monkeypatch):
    test_client, user = client
    user.Role, user.Employee_ID, user.Customer_ID = "Customer", None, "CUST-1"
    store = FakeStore(monkeypatch, damages=[_damage()])

    pdf = test_client.post(
        "/api/v1/documents",
        data={"claim_id": "CLM-1", "document_type": "accident_photos"},
        files={"file": ("photo.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert pdf.status_code == 400  # an accident photo is an image from the camera, never a PDF

    photo = test_client.post(
        "/api/v1/documents",
        data={"claim_id": "CLM-1", "document_type": "accident_photos"},
        files={"file": ("photo.jpg", _jpeg(), "image/jpeg")},
    )
    assert photo.status_code == 201, photo.text
    assert store.documents[-1].Document_Type == "Accident Photos"
    assert store.evidence == []  # a customer document, not an evidence row

    user.Role, user.Employee_ID, user.Customer_ID = "Surveyor", EMPLOYEE, None
    workflow = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]
    assert workflow["capture_count"] == 0 and workflow["qualifying_photo_count"] == 0
    assert _patch(test_client, {"Survey_Report_Submitted": True}).status_code == 400


def test_surveyors_cannot_see_customer_accident_photo_documents(client, monkeypatch):
    test_client, user = client
    store = FakeStore(monkeypatch)
    photo = SimpleNamespace(
        Document_ID="DOC-PHOTO", Claim_ID="CLM-1", Document_Type="Accident Photos", Document_Name="p.jpg",
        Document_Submitted_Date=TODAY, Document_Status="Submitted", OCR_Confidence_Score=Decimal("0"), Extracted_Text="",
        Document_Completeness=Decimal("0"), Document_Mismatch_Indicator=False, Verification_Status="Pending",
    )
    fir = SimpleNamespace(**{**vars(photo), "Document_ID": "DOC-FIR", "Document_Type": "FIR", "Document_Name": "fir.pdf"})
    store.documents = [photo, fir]

    listed = test_client.get("/api/v1/documents?claim_id=CLM-1").json()
    assert [d["Document_ID"] for d in listed] == ["DOC-FIR"]
    assert test_client.get("/api/v1/documents/DOC-PHOTO").status_code == 404
    assert test_client.post("/api/v1/documents/DOC-PHOTO/analyze").status_code == 404

    user.Role, user.Employee_ID, user.Customer_ID = "Customer", None, "CUST-1"
    assert test_client.get("/api/v1/documents/DOC-PHOTO").status_code == 200
    assert {d["Document_ID"] for d in test_client.get("/api/v1/documents?claim_id=CLM-1").json()} == {"DOC-PHOTO", "DOC-FIR"}


# ---------------------------------------------------------------- correction mode on the server


def test_locked_steps_change_only_inside_a_server_side_correction(client, monkeypatch):
    test_client, _ = client
    store = complete_store(monkeypatch)  # damage and a surveyor photo saved: Inspection and Damage are locked

    response = _patch(test_client, {"Vehicle_Condition": "Poor"})
    assert response.status_code == 409 and "Open a correction" in response.json()["detail"]
    damage = test_client.post(
        "/api/v1/surveyor/vehicle-damage",
        json={"Claim_ID": "CLM-1", "Damage_Type": "Rear Damage", "Damaged_Part": "Door", "Damage_Severity": "Minor",
              "Damage_Location": "Rear", "Estimated_Damage_Cost": "100", "Repair_or_Replace": "Repair", "Damage_Description": "Dent."},
    )
    assert damage.status_code == 409
    assert store.updates == [] and store.created == []

    # A client-supplied "correction" flag is ignored; only the server's record counts.
    assert _patch(test_client, {"Vehicle_Condition": "Poor", "correction_mode": True}).status_code == 409

    opened = test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"})
    assert opened.status_code == 200 and opened.json()["open_corrections"]["inspection"] is True
    assert _patch(test_client, {"Vehicle_Condition": "Poor"}).status_code == 200
    # Saving the correction ends it; the step is locked again.
    assert _patch(test_client, {"Vehicle_Condition": "Good"}).status_code == 409


def test_corrections_need_a_completed_step_and_block_submission_until_closed(client, monkeypatch):
    test_client, _ = client
    FakeStore(monkeypatch, inspections=[_inspection(Repair_Recommendation="Pending")])
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"}).status_code == 409
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "report"}).status_code == 400

    complete_store(monkeypatch)
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "damage"}).status_code == 200
    response = _patch(test_client, {"Survey_Report_Submitted": True})
    assert response.status_code == 409 and "Finish the open correction" in response.json()["detail"]
    closed = test_client.delete("/api/v1/surveyor/inspections/INSP-1/corrections/damage")
    assert closed.json()["open_corrections"]["damage"] is False
    assert _patch(test_client, {"Survey_Report_Submitted": True}).status_code == 200


def test_correcting_an_earlier_step_revalidates_later_steps(client, monkeypatch):
    test_client, _ = client
    # No damage observed, one surveyor photo: everything complete.
    store = complete_store(
        monkeypatch, damages=[], inspections=[_inspection(Damage_Observed="No", Damage_Severity="Pending")]
    )
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]["report_available"] is True

    test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"})
    assert _patch(test_client, {"Damage_Observed": "Yes", "Damage_Severity": "Moderate"}).status_code == 200

    workflow = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]
    assert workflow["damage_complete"] is False and workflow["evidence_complete"] is False
    assert workflow["report_available"] is False
    assert test_client.get("/api/v1/surveyor/claims/CLM-1/report").status_code == 409
    response = _patch(test_client, {"Survey_Report_Submitted": True})
    assert response.status_code == 400 and "no vehicle damage record" in response.json()["detail"]
    assert len(store.updates) == 1


def test_capturing_evidence_closes_open_corrections(client, monkeypatch):
    test_client, _ = client
    complete_store(monkeypatch)
    test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "damage"})
    response = test_client.post(
        "/api/v1/surveyor/evidence/capture",
        data={"claim_id": "CLM-1", "evidence_type": "Overall Vehicle Condition", "latitude": "13.08", "longitude": "80.27", "accuracy_m": "10"},
        files={"photo": ("capture.jpg", _jpeg(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]["open_corrections"]["damage"] is False


def test_no_correction_after_submission_or_before_the_schedule_or_by_others(client, monkeypatch):
    test_client, user = client
    FakeStore(monkeypatch, inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed")])
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"}).status_code == 409
    FakeStore(monkeypatch, inspections=[_inspection(Inspection_Date=TODAY + timedelta(days=2))])
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"}).status_code == 409
    complete_store(monkeypatch)
    user.Employee_ID = "EMP-2"  # another surveyor: answered like a missing inspection
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"}).status_code == 404
    assert test_client.delete("/api/v1/surveyor/inspections/INSP-1/corrections/inspection").status_code == 404
    user.Role, user.Employee_ID = "Admin", None
    assert test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"}).status_code == 403


# ---------------------------------------------------------------- integrity of capture records (fail closed)


def _stored_capture(monkeypatch):
    store = FakeStore(monkeypatch, damages=[_damage()])
    evidence, _ = _capture_call(FakeSession())
    photo = evidence_storage.storage_path_for(evidence.Claim_ID, evidence.Evidence_ID, evidence.File_Name)
    return store, evidence, photo


def test_a_replaced_photo_is_no_longer_a_verified_capture(client, monkeypatch):
    test_client, _ = client
    store, evidence, photo = _stored_capture(monkeypatch)
    assert evidence_capture.read_metadata(evidence) is not None
    photo.write_bytes(_jpeg(size=(81, 60)))  # same name, different image

    assert evidence_capture.read_metadata(evidence) is None
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").json()["evidence"] == []
    assert test_client.get(f"/api/v1/surveyor/evidence/{evidence.Evidence_ID}/image").status_code == 404
    assert surveyor_workflow.qualifying_photo_count(None, store.inspections[0]) == 0


def test_a_capture_record_only_counts_for_its_own_row_and_source(monkeypatch):
    _, evidence, photo = _stored_capture(monkeypatch)
    record = evidence_capture.metadata_path_for(photo)

    # Relabelled as a customer row: never surveyor evidence, whatever the record says.
    assert evidence_capture.read_metadata(SimpleNamespace(**{**vars(evidence), "Evidence_Source": "Customer"})) is None

    # The photo and its record copied next to another row.
    other = SimpleNamespace(**{**vars(evidence), "Evidence_ID": "EVD-COPY"})
    other_photo = evidence_storage.storage_path_for(other.Claim_ID, other.Evidence_ID, other.File_Name)
    other_photo.write_bytes(photo.read_bytes())
    evidence_capture.metadata_path_for(other_photo).write_text(record.read_text(encoding="utf-8"), encoding="utf-8")
    assert evidence_capture.read_metadata(other) is None


@pytest.mark.parametrize(
    "damage",
    [
        lambda data: "{ not json",
        lambda data: json.dumps({**data, "version": 1}),
        lambda data: json.dumps({**data, "server": {**data["server"], "role": "officer"}}),
        lambda data: json.dumps({**data, "server": {**data["server"], "sha256": "0" * 64}}),
        lambda data: json.dumps({key: value for key, value in data.items() if key != "checks"}),
    ],
    ids=["unparseable", "unknown-version", "unknown-role", "hash-mismatch", "missing-checks"],
)
def test_missing_corrupted_or_altered_records_are_not_verified(monkeypatch, damage):
    _, evidence, photo = _stored_capture(monkeypatch)
    record = evidence_capture.metadata_path_for(photo)
    record.write_text(damage(json.loads(record.read_text(encoding="utf-8"))), encoding="utf-8")
    assert evidence_capture.read_metadata(evidence) is None
    record.unlink()
    assert evidence_capture.read_metadata(evidence) is None


def test_capture_records_are_written_once_and_atomically(tmp_path):
    photo = tmp_path / "evidence" / "CLM-1" / "EVD-1_x.jpg"
    evidence_capture.write_metadata(photo, {"a": 1})
    with pytest.raises(FileExistsError):
        evidence_capture.write_metadata(photo, {"a": 2})
    assert json.loads(evidence_capture.metadata_path_for(photo).read_text(encoding="utf-8")) == {"a": 1}
    assert [p.name for p in photo.parent.iterdir()] == [evidence_capture.metadata_path_for(photo).name]  # no temp files


def test_a_failed_write_leaves_the_previous_file_intact(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    evidence_capture.atomic_write_json(target, {"v": 1})

    def broken_replace(*args):
        raise OSError("disk full")

    monkeypatch.setattr(evidence_capture.os, "replace", broken_replace)
    with pytest.raises(OSError):
        evidence_capture.atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]  # the temporary file was removed


# ---------------------------------------------------------------- correction state (fail closed, audited)


def test_corrupted_correction_state_pauses_corrections_and_submission_without_overwriting(client, monkeypatch):
    test_client, _ = client
    store = complete_store(monkeypatch)
    inspection = store.inspections[0]
    path = workflow_state._path_for(inspection)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ truncated", encoding="utf-8")

    workflow = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]
    assert workflow["correction_state_error"] is True
    assert workflow["open_corrections"] == {"inspection": False, "damage": False}

    opened = test_client.post("/api/v1/surveyor/inspections/INSP-1/corrections", json={"step": "inspection"})
    assert opened.status_code == 503
    assert _patch(test_client, {"Damage_Severity": "Severe"}).status_code == 503  # the locked step stays locked
    assert _patch(test_client, {"Survey_Report_Submitted": True}).status_code == 503
    assert inspection.Survey_Report_Submitted is False and store.updates == []
    assert path.read_text(encoding="utf-8") == "{ truncated"  # the audit file is never overwritten


def test_correction_history_is_audited_and_survives_concurrent_requests(monkeypatch):
    import threading

    store = complete_store(monkeypatch)
    inspection = store.inspections[0]

    def cycle(n):
        workflow_state.open_correction(inspection, "inspection", f"EMP-{n}", f"t{n}")
        workflow_state.close_corrections(inspection, ("inspection",), f"EMP-{n}", f"t{n}", "saved")

    threads = [threading.Thread(target=cycle, args=(n,)) for n in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    state = workflow_state.read_state(inspection)
    assert state["open_corrections"] == {}
    events = [(entry["event"], entry["step"]) for entry in state["history"]]
    assert events.count(("opened", "inspection")) >= 1
    assert events.count(("opened", "inspection")) == events.count(("closed", "inspection"))
    assert all({"by", "at"} <= entry.keys() for entry in state["history"])


def test_correction_state_cannot_be_set_by_the_client(client, monkeypatch):
    test_client, _ = client
    store = complete_store(monkeypatch)
    response = _patch(test_client, {"Damage_Severity": "Severe", "open_corrections": {"inspection": True}, "correction": True})
    assert response.status_code == 409  # still locked: only the server records a correction
    assert store.updates == []
    assert test_client.delete("/api/v1/surveyor/inspections/INSP-1/corrections/evidence").status_code == 400


# ---------------------------------------------------------------- historical submissions


def test_an_older_submission_without_surveyor_captures_is_flagged_not_rewritten(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(
        monkeypatch,
        inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed", Vehicle_Condition="Poor")],
        damages=[_damage()],
        evidence=[_evidence("EVD-CUST", source="Customer", status="Verified", name="customer.jpg")],
    )

    workflow = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]
    assert workflow["submitted"] is True and workflow["evidence_complete"] is False
    review = workflow["submission_review"]
    assert review["meets_current_requirements"] is False
    assert any("in-app camera" in problem for problem in review["problems"])

    report = test_client.get("/api/v1/surveyor/survey-reports/INSP-1/report").json()
    assert report["report_status"] == "Submitted" and report["evidence"] == []
    assert report["submission_review"] == review

    pdf = test_client.get("/api/v1/surveyor/survey-reports/INSP-1/report.pdf")
    text = " ".join("".join(page.get_text() for page in fitz.open(stream=pdf.content, filetype="pdf")).split())
    assert "do not meet the current submission requirements" in text

    # Nothing was reverted, re-verified or resubmitted.
    assert store.updates == [] and store.created == []
    assert store.inspections[0].Survey_Report_Submitted is True
    assert store.evidence[0].Verification_Status == "Verified"
    assert _patch(test_client, {"Survey_Report_Submitted": False}).status_code == 409


def test_a_compliant_submission_is_reported_as_meeting_the_rules(client, monkeypatch):
    test_client, _ = client
    complete_store(monkeypatch, inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed")])
    review = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]["submission_review"]
    assert review["meets_current_requirements"] is True and review["problems"] == []
    assert test_client.get("/api/v1/surveyor/survey-reports/INSP-1/report").json()["submission_review"] == review


def test_draft_workflow_has_no_submission_review(client, monkeypatch):
    test_client, _ = client
    complete_store(monkeypatch)
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]["submission_review"] is None


# ---------------------------------------------------------------- claim documents for the assigned surveyor


def _document(document_id, document_type, claim_id="CLM-1"):
    return SimpleNamespace(
        Document_ID=document_id,
        Claim_ID=claim_id,
        Document_Type=document_type,
        Document_Name=f"{document_id}.pdf",
        Document_Submitted_Date=TODAY,
        Document_Status="Submitted",
        OCR_Confidence_Score=Decimal("0.0000"),
        Extracted_Text="",
        Document_Completeness=Decimal("0.0000"),
        Document_Mismatch_Indicator=False,
        Verification_Status="Pending",
    )


CLAIM_DOCUMENTS = [
    _document("DOC-RC", "RC"),
    _document("DOC-DL", "Driving Licence"),
    _document("DOC-POL", "Insurance Policy"),
    _document("DOC-FIR", "FIR"),
    _document("DOC-PHOTO", "Accident Photos"),
]


def test_assigned_surveyor_sees_the_claims_documents_except_customer_accident_photos(client, monkeypatch):
    test_client, _ = client
    store = FakeStore(monkeypatch)
    store.documents.extend(CLAIM_DOCUMENTS)

    listed = test_client.get("/api/v1/documents?claim_id=CLM-1")
    assert listed.status_code == 200
    assert {d["Document_ID"] for d in listed.json()} == {"DOC-RC", "DOC-DL", "DOC-POL", "DOC-FIR"}
    for document_id in ("DOC-RC", "DOC-DL", "DOC-POL", "DOC-FIR"):
        assert test_client.get(f"/api/v1/documents/{document_id}").status_code == 200
    assert test_client.get("/api/v1/documents/DOC-PHOTO").status_code == 404
    assert test_client.post("/api/v1/documents/DOC-PHOTO/analyze").status_code == 404


def test_document_ids_on_other_claims_are_answered_like_missing_documents(client, monkeypatch):
    test_client, user = client
    store = FakeStore(monkeypatch)
    store.documents.extend(CLAIM_DOCUMENTS)

    user.Employee_ID = "EMP-2"  # a surveyor not assigned to CLM-1
    for path in ("/api/v1/documents/DOC-RC", "/api/v1/documents/NO-SUCH-DOC"):
        response = test_client.get(path)
        assert (response.status_code, response.json()) == (404, {"detail": "Document not found"})
    assert test_client.post("/api/v1/documents/DOC-FIR/analyze").status_code == 404
    assert test_client.get("/api/v1/documents?claim_id=CLM-1").status_code == 403

    user.Role, user.Employee_ID, user.Customer_ID = "Customer", None, "CUST-OTHER"
    assert test_client.get("/api/v1/documents/DOC-RC").status_code == 404
    user.Customer_ID = "CUST-1"  # the claim's own customer still sees everything, photos included
    assert test_client.get("/api/v1/documents/DOC-PHOTO").status_code == 200
    assert len(test_client.get("/api/v1/documents?claim_id=CLM-1").json()) == len(CLAIM_DOCUMENTS)


def test_surveyor_document_completeness_does_not_disclose_accident_photos():
    from app.api.v1.routers import documents as documents_router
    from app.services.document_analysis import CompletenessResult

    full = CompletenessResult(
        available=True,
        required=["Accident Photos", "FIR", "RC"],
        present=["Accident Photos", "RC"],
        missing=["FIR"],
        ratio=2 / 3,
        explanation="2 of 3 required document type(s) are present for this 'Own Damage' claim.",
    )
    shown = documents_router._without_accident_photos(full, "Own Damage")
    assert "Accident Photos" not in shown.required + shown.present + shown.missing
    assert shown.ratio == 0.5 and "1 of 2" in shown.explanation


def test_customers_cannot_reach_surveyor_evidence(client, monkeypatch):
    test_client, user = client
    _, evidence, _ = _stored_capture(monkeypatch)
    user.Role, user.Employee_ID, user.Customer_ID = "Customer", None, "CUST-1"
    assert test_client.get(f"/api/v1/surveyor/evidence/{evidence.Evidence_ID}/image").status_code == 403
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").status_code == 403
    assert test_client.get("/api/v1/surveyor/claims/CLM-1/report").status_code == 403
    assert test_client.get(f"/api/v1/documents/{evidence.Evidence_ID}").status_code == 404


def test_retired_upload_endpoint_cannot_store_a_file(client, monkeypatch):
    test_client, _ = client
    store = complete_store(monkeypatch)
    response = test_client.post(
        "/api/v1/surveyor/evidence",
        data={"claim_id": "CLM-1", "evidence_type": "Damage Photo", "evidence_source": "Surveyor", "evidence_date": str(TODAY)},
        files={"file": ("gallery.jpg", _jpeg(), "image/jpeg")},
    )
    assert response.status_code == 410
    assert store.created == [] and not hasattr(evidence_upload, "upload_evidence_for_surveyor")


# ---------------------------------------------------------------- Claim Documents viewer (services/surveyor_documents.py)

PDF = b"%PDF-1.7\n% claim document\n%%EOF"
DOCS_URL = "/api/v1/surveyor/claims/CLM-1/documents"


def _stored_document(store, document_id, document_type, name, content=None, claim_id="CLM-1", verification="Pending"):
    document = SimpleNamespace(**{**vars(_document(document_id, document_type, claim_id)), "Document_Name": name})
    document.Verification_Status = verification
    store.documents.append(document)
    if content is not None:
        path = document_storage.storage_path_for(claim_id, document_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return document


def viewer_store(monkeypatch, **overrides):
    store = FakeStore(monkeypatch, **overrides)
    _stored_document(store, "DOC-RC", "RC", "rc-copy.pdf", PDF)  # now stored like any other document
    _stored_document(store, "DOC-POL", "Insurance Policy", "policy-copy.png", _png(), verification="Verified")
    # Both excluded from this panel (FIR by type, Accident Photos always) -
    # kept here only to assert they never appear.
    _stored_document(store, "DOC-FIR", "FIR", "fir.pdf", PDF)
    _stored_document(store, "DOC-PHOTO", "Accident Photos", "photo.jpg", _jpeg())
    return store


def _content(test_client, document_id, claim_id="CLM-1"):
    return test_client.get(f"/api/v1/surveyor/claims/{claim_id}/documents/{document_id}/content")


def test_assigned_surveyor_sees_each_documents_real_availability(client, monkeypatch):
    test_client, _ = client
    viewer_store(monkeypatch)
    response = test_client.get(DOCS_URL)
    assert response.status_code == 200
    items = {item["document_type"]: item for item in response.json()["documents"]}

    # Only RC, Driving Licence and Insurance Policy are ever in this panel -
    # FIR and customer accident photos (both present on this claim) never are.
    assert set(items) == {"RC", "Driving Licence", "Insurance Policy"}
    assert items["RC"]["availability"] == "available" and items["RC"]["media_type"] == "application/pdf"
    assert items["RC"]["verification_status"] == "Pending"
    assert items["Insurance Policy"]["availability"] == "available" and items["Insurance Policy"]["media_type"] == "image/png"
    assert items["Insurance Policy"]["verification_status"] == "Verified"  # as recorded, not inferred
    assert items["Driving Licence"] == {
        "document_id": None, "document_type": "Driving Licence", "submitted_date": None,
        "availability": "not_uploaded", "media_type": None, "verification_status": None,
    }
    assert [item["document_type"] for item in response.json()["documents"]] == [
        "RC", "Driving Licence", "Insurance Policy",
    ]
    assert "path" not in response.text.lower() and "storage" not in response.text.lower()
    assert "FIR" not in response.text and "Accident Photos" not in response.text


def test_documents_can_be_opened_repeatedly_without_changing_anything(client, monkeypatch):
    test_client, _ = client
    store = viewer_store(monkeypatch, damages=[_damage()])
    inspection = store.inspections[0]
    before = dict(vars(inspection))

    for _ in range(3):  # no view count, no one-time link
        response = _content(test_client, "DOC-RC")
        assert response.status_code == 200 and response.content == PDF
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"] == 'inline; filename="claim-document.pdf"'
        assert "sandbox" in response.headers["content-security-policy"]
    image = _content(test_client, "DOC-POL")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"

    # Viewing writes nothing: no evidence, no inspection change, same workflow.
    assert store.updates == [] and store.created == [] and store.evidence == []
    assert vars(inspection) == before
    workflow = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]
    assert workflow["capture_count"] == 0 and workflow["evidence_complete"] is False


def test_document_views_are_audited_without_their_content(client, monkeypatch, caplog):
    test_client, _ = client
    viewer_store(monkeypatch)
    with caplog.at_level("INFO", logger="ci_micop.audit.document_access"):
        assert _content(test_client, "DOC-RC").status_code == 200
    (record,) = [r for r in caplog.records if r.name == "ci_micop.audit.document_access"]
    message = record.getMessage()
    assert "surveyor=EMP-1" in message and "claim=CLM-1" in message and "document=DOC-RC" in message
    assert "%PDF" not in message and "rc-copy.pdf" not in message


def test_unauthenticated_requests_are_rejected(client, monkeypatch):
    test_client, _ = client
    viewer_store(monkeypatch)
    app.dependency_overrides.pop(deps.get_current_user)
    assert test_client.get(DOCS_URL).status_code == 401
    assert _content(test_client, "DOC-FIR").status_code == 401


@pytest.mark.parametrize("role", ["Customer", "Claims Officer", "Admin"])
def test_only_surveyors_can_use_the_surveyor_document_endpoints(client, monkeypatch, role):
    test_client, user = client
    viewer_store(monkeypatch)
    user.Role, user.Employee_ID, user.Customer_ID = role, None, "CUST-1" if role == "Customer" else None
    assert test_client.get(DOCS_URL).status_code == 403
    assert _content(test_client, "DOC-FIR").status_code == 403


def test_unassigned_or_unknown_claims_get_the_same_answer(client, monkeypatch):
    test_client, user = client
    viewer_store(monkeypatch)
    user.Employee_ID = "EMP-2"  # a surveyor not assigned to CLM-1
    unassigned = [test_client.get(DOCS_URL), _content(test_client, "DOC-FIR")]
    user.Employee_ID = EMPLOYEE
    unknown = [test_client.get("/api/v1/surveyor/claims/CLM-NOPE/documents"), _content(test_client, "DOC-FIR", "CLM-NOPE")]
    for response in unassigned + unknown:
        assert (response.status_code, response.json()) == (404, {"detail": "Claim not found"})


def test_a_document_of_another_claim_cannot_be_opened_through_this_claim(client, monkeypatch):
    test_client, _ = client
    store = viewer_store(monkeypatch)
    _stored_document(store, "DOC-OTHER", "FIR", "other.pdf", PDF, claim_id="CLM-2")
    for document_id in ("DOC-OTHER", "DOC-NOPE", "DOC-PHOTO"):
        response = _content(test_client, document_id)
        assert (response.status_code, response.json()) == (404, {"detail": "Document not found"})
    assert "DOC-OTHER" not in test_client.get(DOCS_URL).text


def test_a_revoked_assignment_blocks_the_next_request(client, monkeypatch):
    test_client, _ = client
    store = viewer_store(monkeypatch)
    assert _content(test_client, "DOC-RC").status_code == 200
    store.inspections[0].Surveyor_ID = "EMP-2"  # reassigned to someone else
    assert _content(test_client, "DOC-RC").status_code == 404
    assert test_client.get(DOCS_URL).status_code == 404


def test_missing_files_are_reported_safely_never_as_available(client, monkeypatch):
    """A row with no file behind it - e.g. an RC/licence/policy copy
    uploaded before copies were kept - is reported unavailable, never
    falsely available, and never leaks the storage path."""
    test_client, _ = client
    store = viewer_store(monkeypatch)
    _stored_document(store, "DOC-GONE", "Driving Licence", "dl.pdf")  # row without a file
    items = {item["document_id"]: item for item in test_client.get(DOCS_URL).json()["documents"]}
    assert items["DOC-GONE"]["availability"] == "unavailable"

    gone = _content(test_client, "DOC-GONE")
    assert (gone.status_code, gone.json()["detail"]) == (404, "The file for this document is not available.")
    assert settings.DOCUMENT_STORAGE_ROOT not in gone.text


def test_stored_names_and_ids_cannot_reach_files_outside_the_claims_storage(client, monkeypatch, tmp_path):
    test_client, _ = client
    store = viewer_store(monkeypatch)
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(PDF + b"SECRET")
    for index, name in enumerate(["../../secret.pdf", "..\\..\\secret.pdf", str(secret), "/etc/passwd"]):
        _stored_document(store, f"DOC-TRAV-{index}", "RC", name)
        response = _content(test_client, f"DOC-TRAV-{index}")
        assert response.status_code == 404 and b"SECRET" not in response.content
    assert test_client.get("/api/v1/surveyor/claims/CLM-1/documents/..%2F..%2Fsecret.pdf/content").status_code == 404


def test_content_that_is_not_a_pdf_or_image_is_never_rendered(client, monkeypatch):
    test_client, _ = client
    store = viewer_store(monkeypatch)
    _stored_document(store, "DOC-HTML", "Driving Licence", "report.pdf", b"<html><script>alert(1)</script></html>")
    items = {item["document_id"]: item for item in test_client.get(DOCS_URL).json()["documents"]}
    assert items["DOC-HTML"]["availability"] == "unsupported" and items["DOC-HTML"]["media_type"] is None
    response = _content(test_client, "DOC-HTML")
    assert response.status_code == 415 and b"<script>" not in response.content


def test_documents_stay_locked_until_the_scheduled_date(client, monkeypatch):
    test_client, _ = client
    store = viewer_store(monkeypatch, inspections=[_inspection(Inspection_Date=TODAY + timedelta(days=1))])
    message = f"Customer documents become available on the scheduled inspection date, {surveyor_workflow._long_date(TODAY + timedelta(days=1))}"
    for response in (test_client.get(DOCS_URL), _content(test_client, "DOC-FIR")):
        assert response.status_code == 409 and response.json()["detail"].startswith(message)
    assert test_client.get("/api/v1/surveyor/claims/CLM-1").status_code == 200  # Claim Details stays readable
    assert store.updates == []


def test_documents_open_at_midnight_ist_on_the_scheduled_date(monkeypatch):
    from app.services import surveyor_documents

    viewer_store(monkeypatch, inspections=[_inspection(Inspection_Date=date(2026, 10, 28))])
    start = datetime(2026, 10, 28, tzinfo=IST)
    with pytest.raises(HTTPException) as early:
        surveyor_documents.authorize(None, "CLM-1", EMPLOYEE, now=start - timedelta(seconds=1))
    assert early.value.status_code == 409
    assert surveyor_documents.authorize(None, "CLM-1", EMPLOYEE, now=start)[1].Inspection_ID == "INSP-1"
    from datetime import timezone

    # The same instant in UTC (18:30 the day before) is judged identically.
    surveyor_documents.authorize(None, "CLM-1", EMPLOYEE, now=datetime(2026, 10, 27, 18, 30, tzinfo=timezone.utc))


def test_documents_remain_viewable_after_submission_and_the_report_stays_final(client, monkeypatch):
    test_client, _ = client
    store = viewer_store(
        monkeypatch,
        inspections=[_inspection(Survey_Report_Submitted=True, Inspection_Status="Completed")],
        damages=[_damage()],
    )
    assert _content(test_client, "DOC-RC").status_code == 200
    assert _patch(test_client, {"Damage_Severity": "Severe"}).status_code == 409
    assert _patch(test_client, {"Survey_Report_Submitted": False}).status_code == 409
    review = test_client.get("/api/v1/surveyor/claims/CLM-1").json()["workflow"]["submission_review"]
    assert review["meets_current_requirements"] is False  # the historical warning is unchanged
    assert store.updates == [] and store.inspections[0].Inspection_Status == "Completed"
