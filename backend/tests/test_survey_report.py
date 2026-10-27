"""Database-backed tests for the survey report endpoints
(GET /surveyor/claims/{id}/report and /report.pdf), the record
requirements checked when a report is submitted, and the lock on a
submitted report.

These use tests/conftest.py's database fixtures. They have not been run
yet: they are deferred until a test database is set up after the final
dataset is integrated. tests/test_survey_report_rules.py covers the same
rules without a database.
"""

import fitz
import pytest

from app.db.session import SessionLocal
from app.db_models.surveyor_inspection import SurveyorInspection
from tests.conftest import auth_headers
from tests.surveyor_records import COMPLETE_FINDINGS, surveyor_records  # noqa: F401 - fixture


def _report(client, token, claim_id, suffix=""):
    return client.get(f"/api/v1/surveyor/claims/{claim_id}/report{suffix}", headers=auth_headers(token))


def _stored(inspection_id):
    db = SessionLocal()
    try:
        return db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == inspection_id).one()
    finally:
        db.close()


# ---------------------------------------------------------------- submission requirements


def test_submission_requires_a_damage_record_when_damage_was_observed(surveyor_records):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS)
    surveyor_records.capture_photo()

    response = surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True})
    assert response.status_code == 400
    assert "no vehicle damage record" in response.json()["detail"]
    assert _stored(inspection["Inspection_ID"]).Survey_Report_Submitted is False


def test_submission_requires_a_camera_captured_photo(surveyor_records):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS)
    surveyor_records.add_damage()
    # A file upload claiming source Surveyor is refused outright (retired endpoint).
    assert surveyor_records.legacy_upload(source="Surveyor").status_code == 410
    surveyor_records.capture_photo(latitude=None)  # a capture without a location does not count

    response = surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True})
    assert response.status_code == 400
    assert "in-app camera" in response.json()["detail"]
    assert _stored(inspection["Inspection_ID"]).Survey_Report_Submitted is False

    surveyor_records.capture_photo()
    assert surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True}).status_code == 200


def test_no_damage_observed_needs_no_damage_record(surveyor_records):
    inspection = surveyor_records.start_inspection(
        **{**COMPLETE_FINDINGS, "Damage_Observed": "No", "Damage_Severity": "Pending"}
    )
    surveyor_records.capture_photo()

    response = surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True})
    assert response.status_code == 200, response.text
    assert response.json()["Survey_Report_Submitted"] is True


# ---------------------------------------------------------------- submitted report is final


def test_submitted_report_cannot_be_reverted_or_edited(surveyor_records):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS)
    surveyor_records.add_damage()
    surveyor_records.capture_photo()
    assert surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True}).status_code == 200

    for body in (
        {"Survey_Report_Submitted": False},
        {"Vehicle_Condition": "Poor"},
        {"Surveyor_Comments": "Changed after submission"},
        {"Inspection_Status": "In Progress"},
    ):
        assert surveyor_records.patch(inspection["Inspection_ID"], body).status_code == 409, body

    stored = _stored(inspection["Inspection_ID"])
    assert stored.Survey_Report_Submitted is True
    assert stored.Inspection_Status == "Completed"
    assert stored.Vehicle_Condition == "Fair"
    assert stored.Surveyor_Comments == ""


def test_admin_cannot_edit_a_submitted_report_either(client, admin_token, seed_data):
    response = client.patch(
        f"/api/v1/surveyor/inspections/{seed_data['inspection1']}",
        json={"Survey_Report_Submitted": False},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 409
    assert _stored(seed_data["inspection1"]).Survey_Report_Submitted is True


def test_inspection_date_and_location_cannot_be_changed(surveyor_records):
    inspection = surveyor_records.start_inspection()
    response = surveyor_records.patch(
        inspection["Inspection_ID"], {"Inspection_Date": "2020-01-01", "Inspection_Location": "Elsewhere"}
    )
    assert response.status_code == 200
    stored = _stored(inspection["Inspection_ID"])
    assert str(stored.Inspection_Date) == inspection["Inspection_Date"]
    assert stored.Inspection_Location == inspection["Inspection_Location"]


# ---------------------------------------------------------------- report availability and contents


def test_report_unavailable_while_the_workflow_is_incomplete(client, surveyor_token, surveyor_records, seed_data):
    surveyor_records.start_inspection(**COMPLETE_FINDINGS)  # no damage record, no evidence yet
    for suffix in ("", ".pdf"):
        assert _report(client, surveyor_token, seed_data["claim1"], suffix).status_code == 409


def test_draft_report_contains_the_persisted_workflow_data(client, surveyor_token, surveyor_records, seed_data):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS, Surveyor_Comments="Rear bumper cracked.")
    surveyor_records.add_damage()
    surveyor_records.add_damage(Damaged_Part="Tail Lamp", Estimated_Damage_Cost="2500.00")
    surveyor_records.capture_photo()

    response = _report(client, surveyor_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["report_status"] == "Draft"
    assert report["claim"]["Claim_ID"] == seed_data["claim1"]
    assert report["claim"]["Claim_Number"] == "TEST-CLMNUM-0001"
    assert report["customer"] == {"Customer_ID": seed_data["customer1"], "Customer_Name": "Test Customer One"}
    assert report["vehicle"]["Registration_Number"] == "TEST-REG-0001"
    assert report["policy"] == {"Policy_Number": "TEST-POLNUM-0001", "Policy_Type": "Comprehensive"}
    assert report["surveyor"] == {"Employee_ID": seed_data["employee_surveyor"]}
    assert report["inspection"]["Inspection_ID"] == inspection["Inspection_ID"]
    assert report["inspection"]["Surveyor_Comments"] == "Rear bumper cracked."
    assert {d["Damaged_Part"] for d in report["vehicle_damage"]} >= {"Rear Bumper", "Tail Lamp"}
    assert any(e["Evidence_Source"] == "Surveyor" for e in report["evidence"])
    assert all(e["analysis"] is None for e in report["evidence"] if e["Verification_Status"] == "Pending")

    for private in ("Date_of_Birth", "test_customer1@example.com", "9990000001", "1 Test Street"):
        assert private not in response.text

    assert _stored(inspection["Inspection_ID"]).Survey_Report_Submitted is False  # viewing never submits


def test_pdf_download_is_a_real_pdf_with_the_same_data(client, surveyor_token, surveyor_records, seed_data):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS)
    surveyor_records.add_damage(Damaged_Part="Tail Lamp")
    surveyor_records.capture_photo()

    report = _report(client, surveyor_token, seed_data["claim1"]).json()
    response = _report(client, surveyor_token, seed_data["claim1"], ".pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="survey-report-TEST-CLMNUM-0001.pdf"' in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")

    text = " ".join(page.get_text() for page in fitz.open("pdf", response.content)).replace("\n", " ")
    for value in (
        report["claim"]["Claim_Number"],
        report["customer"]["Customer_Name"],
        report["vehicle"]["Registration_Number"],
        report["policy"]["Policy_Number"],
        report["inspection"]["Inspection_ID"],
        "Tail Lamp",
        "In-app camera",
        "Not analysed yet",
    ):
        assert value in text, value

    assert _stored(inspection["Inspection_ID"]).Survey_Report_Submitted is False  # downloading never submits


def test_submitted_report_stays_available(client, surveyor_token, seed_data):
    # seed_data's inspection1 is already submitted; with no active inspection
    # of the surveyor's own on claim1, the report is that one.
    response = _report(client, surveyor_token, seed_data["claim1"])
    assert response.status_code == 200, response.text
    assert response.json()["report_status"] == "Submitted"
    assert response.json()["inspection"]["Inspection_ID"] == seed_data["inspection1"]


# ---------------------------------------------------------------- access


@pytest.mark.parametrize("suffix", ["", ".pdf"])
def test_surveyor_cannot_read_another_surveyors_report(client, surveyor_token, other_surveyor_claim, suffix):
    assert _report(client, surveyor_token, other_surveyor_claim["claim_id"], suffix).status_code == 403


@pytest.mark.parametrize("suffix", ["", ".pdf"])
@pytest.mark.parametrize("token_fixture", ["customer1_token", "officer_token", "admin_token"])
def test_only_surveyors_can_read_reports(client, seed_data, request, token_fixture, suffix):
    token = request.getfixturevalue(token_fixture)
    assert _report(client, token, seed_data["claim1"], suffix).status_code == 403


def test_report_requires_authentication(client, seed_data):
    assert client.get(f"/api/v1/surveyor/claims/{seed_data['claim1']}/report").status_code == 401


# ---------------------------------------------------------------- locks, schedule and lists


def test_damage_and_evidence_are_locked_after_submission(client, surveyor_token, surveyor_records, seed_data):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS)
    surveyor_records.add_damage()
    surveyor_records.capture_photo()
    assert surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True}).status_code == 200

    damage = client.post(
        "/api/v1/surveyor/vehicle-damage",
        json={"Claim_ID": seed_data["claim1"], "Damage_Type": "Rear Damage", "Damaged_Part": "Door", "Damage_Severity": "Minor",
              "Damage_Location": "Rear", "Estimated_Damage_Cost": "100", "Repair_or_Replace": "Repair", "Damage_Description": "Dent."},
        headers=auth_headers(surveyor_token),
    )
    assert damage.status_code == 409


def test_future_scheduled_inspection_cannot_be_started(client, surveyor_token, seed_data):
    from datetime import timedelta

    from app.services.surveyor_workflow import now_ist

    db = SessionLocal()
    try:
        db.add(
            SurveyorInspection(
                Inspection_ID="TEST-INS-FUTURE",
                Claim_ID=seed_data["claim1"],
                Surveyor_ID=seed_data["employee_surveyor"],
                Inspection_Date=now_ist().date() + timedelta(days=3),
                Inspection_Location="TestCity",
                Vehicle_Condition="Pending",
                Damage_Observed="Pending",
                Damage_Severity="Pending",
                Parts_Required=0,
                Repair_Recommendation="Pending",
                Surveyor_Comments="",
                Inspection_Status="Scheduled",
                Survey_Report_Submitted=False,
                Surveyor_Confidence_Score=0,
            )
        )
        db.commit()

        response = client.patch(
            "/api/v1/surveyor/inspections/TEST-INS-FUTURE",
            json={"Vehicle_Condition": "Good"},
            headers=auth_headers(surveyor_token),
        )
        assert response.status_code == 409
        assert "scheduled for" in response.json()["detail"]
        detail = client.get(f"/api/v1/surveyor/claims/{seed_data['claim1']}", headers=auth_headers(surveyor_token)).json()
        assert detail["workflow"]["schedule"]["reached"] is False
    finally:
        db.query(SurveyorInspection).filter(SurveyorInspection.Inspection_ID == "TEST-INS-FUTURE").delete()
        db.commit()
        db.close()


def test_submitted_claims_move_from_active_inspections_to_survey_reports(client, surveyor_token, surveyor_records):
    inspection = surveyor_records.start_inspection(**COMPLETE_FINDINGS)
    surveyor_records.add_damage()
    surveyor_records.capture_photo()

    def ids(path):
        rows = client.get(f"/api/v1/surveyor/{path}", headers=auth_headers(surveyor_token)).json()
        return {row["inspection"]["Inspection_ID"] for row in rows}

    assert inspection["Inspection_ID"] in ids("active-inspections")
    assert inspection["Inspection_ID"] not in ids("survey-reports")
    assert surveyor_records.patch(inspection["Inspection_ID"], {"Survey_Report_Submitted": True}).status_code == 200
    assert inspection["Inspection_ID"] not in ids("active-inspections")
    assert inspection["Inspection_ID"] in ids("survey-reports")

    report = client.get(
        f"/api/v1/surveyor/survey-reports/{inspection['Inspection_ID']}/report", headers=auth_headers(surveyor_token)
    )
    assert report.status_code == 200 and report.json()["report_status"] == "Submitted"
