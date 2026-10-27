"""Unit tests for services/survey_report_pdf.py.

No database: the renderer only takes the report dictionary. Run with
`pytest --noconftest tests/test_survey_report_pdf.py` to skip the shared
database fixtures in conftest.py.
"""

from datetime import date, datetime, time
from decimal import Decimal

import fitz

from app.services.survey_report_pdf import render_survey_report_pdf


def _report(**overrides):
    report = {
        "report_status": "Draft",
        "generated_at": datetime(2026, 10, 26, 10, 30),
        "surveyor": {"Employee_ID": "EMP-1"},
        "claim": {
            "Claim_ID": "CLM-1",
            "Claim_Number": "CLM-2026-AAAA",
            "Claim_Date": date(2026, 9, 1),
            "Claim_Intimation_Date": date(2026, 9, 2),
            "Claim_Type": "Own Damage",
            "Claim_Status": "Under Review",
            "Claim_Amount": Decimal("50000.00"),
            "Claim_Description": "Rear-ended <script>alert(1)</script> at a signal.",
        },
        "customer": {"Customer_ID": "CUST-1", "Customer_Name": "Asha R"},
        "vehicle": {"Registration_Number": "TN01AB1234", "Make": "Maruti", "Model": "Swift", "Manufacturing_Year": 2021},
        "policy": None,
        "accidents": [
            {
                "Accident_Date": date(2026, 8, 30),
                "Accident_Time": time(18, 5),
                "Accident_Type": "Collision",
                "Accident_Location": "Anna Salai",
                "Accident_City": "Chennai",
                "Accident_State": "Tamil Nadu",
                "Accident_Pincode": "600002",
                "Accident_Description": "Hit from behind.",
                "Weather_Condition": "Clear",
                "Road_Condition": "Dry",
                "Police_Report_Available": True,
                "FIR_Number": None,
                "Third_Party_Involved": True,
                "Injury_Reported": False,
                "Witness_Available": False,
            }
        ],
        "inspection": {
            "Inspection_ID": "INSP-1",
            "Inspection_Date": date(2026, 9, 3),
            "Inspection_Location": "Chennai",
            "Vehicle_Condition": "Damaged",
            "Damage_Observed": "Yes",
            "Damage_Severity": "Minor",
            "Parts_Required": 2,
            "Repair_Recommendation": "Repair",
            "Inspection_Status": "In Progress",
            "Surveyor_Comments": "",
            "Survey_Report_Submitted": False,
        },
        "invalid_values": [{"field": "Vehicle_Condition", "label": "Vehicle Condition", "value": "Damaged"}],
        "vehicle_damage": [],
        "total_estimated_damage_cost": Decimal("0"),
        "evidence": [
            {
                "Evidence_ID": "EVD-1",
                "Evidence_Type": "Damage Photo",
                "Evidence_Date": date(2026, 9, 3),
                "Evidence_Source": "Surveyor",
                "File_Name": "rear.jpg",
                "Verification_Status": "Pending",
                "analysis": None,
            }
        ],
    }
    report.update(overrides)
    return report


def _text(pdf: bytes) -> tuple[fitz.Document, str]:
    document = fitz.open("pdf", pdf)
    return document, " ".join(page.get_text() for page in document).replace("\n", " ")


def test_renders_a_valid_pdf_with_every_section():
    pdf = render_survey_report_pdf(_report())
    assert pdf.startswith(b"%PDF-")
    _, text = _text(pdf)
    for heading in (
        "Motor Insurance Survey Report",
        "A. Claim Information",
        "B. Accident Information",
        "C. Inspection Details",
        "D. Vehicle Damage Assessment",
        "E. Evidence",
        "F. Surveyor",
    ):
        assert heading in text
    assert "Draft - not yet submitted" in text
    assert "INR 50,000.00" in text
    assert "Generated: 26 Oct 2026, 10:30" in text


def test_missing_values_and_pending_analysis_are_shown_honestly():
    _, text = _text(render_survey_report_pdf(_report()))
    assert "Policy Number: Not available" in text  # no policy - nothing invented
    assert "FIR Number: Not available" in text
    assert "Surveyor Comments: Not available" in text
    assert "Not analysed yet" in text
    assert "No vehicle damage records have been saved" in text


def test_completed_analysis_is_shown_with_its_values():
    evidence = [
        {
            "Evidence_ID": "EVD-2",
            "Evidence_Type": "Survey Photo",
            "Evidence_Date": date(2026, 9, 3),
            "Evidence_Source": "Customer",
            "File_Name": "front.png",
            "Verification_Status": "Verified",
            "analysis": {
                "Image_Quality": Decimal("0.8200"),
                "Vehicle_Damage_Detected": True,
                "Damage_Severity": "Minor",
                "Location_Match": True,
                "Duplicate_Evidence_Indicator": False,
                "Evidence_Confidence_Score": Decimal("0.9100"),
            },
        }
    ]
    _, text = _text(render_survey_report_pdf(_report(evidence=evidence)))
    assert "Image quality 0.8200" in text
    assert "Not analysed yet" not in text


def test_invalid_stored_values_are_shown_as_stored_and_flagged():
    _, text = _text(render_survey_report_pdf(_report()))
    assert "Damaged (not a valid option)" in text


def test_values_are_escaped_not_interpreted_as_markup():
    _, text = _text(render_survey_report_pdf(_report()))
    assert "<script>alert(1)</script>" in text


def test_long_reports_flow_onto_further_pages_without_losing_records():
    damages = [
        {
            "Damage_ID": f"DMG-{i}",
            "Damage_Type": "Rear Damage",
            "Damaged_Part": f"Panel{i:02d}",
            "Damage_Severity": "Minor",
            "Damage_Location": "Rear",
            "Estimated_Damage_Cost": Decimal("1000"),
            "Repair_or_Replace": "Repair",
            "Photo_Evidence_Available": False,
            "Damage_Description": "Dent. " * 30,
        }
        for i in range(30)
    ]
    document, text = _text(
        render_survey_report_pdf(_report(vehicle_damage=damages, total_estimated_damage_cost=Decimal("30000")))
    )
    assert document.page_count > 1
    assert all(f"Panel{i:02d}" in text for i in range(30))
    assert "INR 30,000.00" in text
    assert f"Page {document.page_count} of {document.page_count}" in text
    assert "rear.jpg" in text  # the evidence section after the long list is still there


def test_submitted_reports_are_labelled_submitted():
    _, text = _text(render_survey_report_pdf(_report(report_status="Submitted")))
    assert "Report status: Submitted" in text
    assert "Draft" not in text
