"""Renders the survey report (services/survey_report.py) as a PDF.

Uses PyMuPDF, already a project dependency for document analysis, so no
new library is needed. The PDF is drawn only from the report dictionary -
the same data the JSON report endpoint returns - so View Report and
Download Report cannot drift apart. Every value is HTML-escaped before
layout.

Layout uses plain paragraphs rather than HTML tables: PyMuPDF's Story
layout does not split a table across pages, so a long table could be lost
at a page break, while paragraphs always flow onto the next page.
"""
from __future__ import annotations

import io
from datetime import date, datetime, time
from decimal import Decimal
from html import escape

import fitz  # PyMuPDF

NOT_AVAILABLE = "Not available"

_CSS = """
* { font-family: sans-serif; }
body { font-size: 9.5pt; color: #1f2937; }
h1 { font-size: 17pt; color: #1e3a8a; margin: 0 0 2pt 0; }
h2 { font-size: 11.5pt; color: #1e40af; margin: 14pt 0 5pt 0; padding-bottom: 2pt; border-bottom: 1px solid #93c5fd; }
h3 { font-size: 10pt; margin: 0 0 3pt 0; }
p { margin: 0 0 4pt 0; }
p.row { margin: 0 0 3pt 0; }
.label { color: #4b5563; font-weight: bold; }
.record { margin: 0 0 6pt 0; padding: 4pt 6pt; background-color: #f8fafc; border-left: 2px solid #93c5fd; }
.meta { font-size: 9pt; color: #4b5563; }
.status { font-weight: bold; color: #1e40af; }
.draft { font-weight: bold; color: #b45309; }
.note { font-size: 8.5pt; color: #b45309; }
.review { margin: 0 0 6pt 0; padding: 4pt 6pt; background-color: #fffbeb; border-left: 2px solid #b45309; color: #78350f; font-size: 9pt; }
.muted { color: #6b7280; }
"""


def _text(value) -> str:
    if value is None or value == "":
        return NOT_AVAILABLE
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %H:%M")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)


def _money(value) -> str:
    if value is None:
        return NOT_AVAILABLE
    return f"INR {Decimal(value):,.2f}"


def _e(value) -> str:
    return escape(_text(value))


def _rows(pairs) -> str:
    return "".join(f'<p class="row"><span class="label">{escape(label)}:</span> {value}</p>' for label, value in pairs)


def _record(title: str, pairs) -> str:
    return f'<div class="record"><h3>{escape(title)}</h3>{_rows(pairs)}</div>'


def _analysis_summary(analysis) -> str:
    if analysis is None:
        return '<span class="muted">Not analysed yet</span>'
    return escape(
        f'Image quality {_text(analysis["Image_Quality"])}; '
        f'damage detected: {_text(analysis["Vehicle_Damage_Detected"])}; '
        f'severity: {_text(analysis["Damage_Severity"])}; '
        f'location match: {_text(analysis["Location_Match"])}; '
        f'duplicate: {_text(analysis["Duplicate_Evidence_Indicator"])}; '
        f'confidence {_text(analysis["Evidence_Confidence_Score"])}'
    )


LOCATION_STATUS_TEXT = {
    "captured": "Location captured",
    "unavailable": "Location unavailable",
    "accuracy_insufficient": "Location accuracy insufficient",
}
CLIENT_TIME_TEXT = {
    "consistent": "consistent with server receipt time",
    "inconsistent": "inconsistent with server receipt time",
    "missing": "not reported",
    "invalid": "not readable",
}


def _capture_rows(capture: dict | None, qualifying: bool | None) -> list[tuple[str, str]]:
    """Capture metadata, keeping device-reported and server-recorded values
    apart. Photos without an in-app capture record are said to be so."""
    if not capture:
        return [("Capture", '<span class="muted">No in-app camera capture record (uploaded evidence)</span>')]
    client = capture.get("client") or {}
    server = capture.get("server") or {}
    checks = capture.get("checks") or {}
    if client.get("latitude") is not None:
        location = f'{client["latitude"]:.6f}, {client["longitude"]:.6f} (&#177;{client["accuracy_m"]:.0f} m)'
    else:
        location = f'Not available ({escape(str(client.get("error") or "not provided"))})'
    time_status = CLIENT_TIME_TEXT.get(checks.get("client_time_status"), "not checked")
    return [
        ("Capture Method", "In-app camera"),
        ("Device-reported Capture Time", f'{_e(client.get("captured_at"))} ({escape(time_status)})'),
        ("Device-reported Location", location),
        (
            "Location Check",
            escape(LOCATION_STATUS_TEXT.get(checks.get("location_status"), "Not checked"))
            + (f' (limit {checks["max_accuracy_m"]:.0f} m)' if checks.get("max_accuracy_m") else ""),
        ),
        ("Server Receipt Time", _e(server.get("received_at"))),
        ("Recorded Surveyor", _e(server.get("surveyor_employee_id"))),
        ("Image Check", f'{_e(server.get("image_format"))} {_e(server.get("width"))}x{_e(server.get("height"))}, content validated'),
        ("Counts as Surveyor Photo", "Yes" if qualifying else "No"),
    ]


def _html(report: dict) -> str:
    claim = report["claim"]
    customer = report["customer"] or {}
    vehicle = report["vehicle"] or {}
    policy = report["policy"] or {}
    inspection = report["inspection"]
    invalid = {item["field"]: item for item in report["invalid_values"]}

    def finding(field):
        value = _e(inspection[field])
        if field in invalid:
            value += ' <span class="note">(not a valid option)</span>'
        return value

    is_draft = report["report_status"] == "Draft"
    status_html = (
        '<span class="draft">Draft - not yet submitted</span>' if is_draft else '<span class="status">Submitted</span>'
    )

    parts = [
        "<h1>Motor Insurance Survey Report</h1>",
        f'<p class="meta">Claim {_e(claim["Claim_Number"])} &#183; Report status: {status_html}</p>',
        f'<p class="meta">Surveyor: {_e(report["surveyor"]["Employee_ID"])} &#183; '
        f'Generated: {_e(report["generated_at"])}</p>',
        _submission_review_html(report.get("submission_review")),
        "<h2>A. Claim Information</h2>",
        _rows(
            [
                ("Claim ID", _e(claim["Claim_ID"])),
                ("Claim Number", _e(claim["Claim_Number"])),
                ("Claim Date", _e(claim["Claim_Date"])),
                ("Intimation Date", _e(claim["Claim_Intimation_Date"])),
                ("Claim Type", _e(claim["Claim_Type"])),
                ("Claim Status", _e(claim["Claim_Status"])),
                ("Claim Amount", escape(_money(claim["Claim_Amount"]))),
                ("Claim Description", _e(claim["Claim_Description"])),
                ("Customer Name", _e(customer.get("Customer_Name"))),
                ("Customer ID", _e(customer.get("Customer_ID"))),
                ("Vehicle Registration", _e(vehicle.get("Registration_Number"))),
                ("Vehicle Make / Model", f'{_e(vehicle.get("Make"))} / {_e(vehicle.get("Model"))}'),
                ("Vehicle Year", _e(vehicle.get("Manufacturing_Year"))),
                ("Policy Number", _e(policy.get("Policy_Number"))),
                ("Policy Type", _e(policy.get("Policy_Type"))),
            ]
        ),
        "<h2>B. Accident Information</h2>",
    ]

    accidents = report["accidents"]
    if not accidents:
        parts.append('<p class="muted">No accident record is stored for this claim.</p>')
    for index, a in enumerate(accidents, start=1):
        rows = _rows(
            [
                ("Date and Time", f'{_e(a["Accident_Date"])}, {_e(a["Accident_Time"])}'),
                ("Accident Type", _e(a["Accident_Type"])),
                ("Location", _e(a["Accident_Location"])),
                (
                    "City / State / Pincode",
                    f'{_e(a["Accident_City"])} / {_e(a["Accident_State"])} / {_e(a["Accident_Pincode"])}',
                ),
                ("Description", _e(a["Accident_Description"])),
                ("Weather / Road", f'{_e(a["Weather_Condition"])} / {_e(a["Road_Condition"])}'),
                ("Police Report", _e(a["Police_Report_Available"])),
                ("FIR Number", _e(a["FIR_Number"])),
                ("Third Party Involved", _e(a["Third_Party_Involved"])),
                ("Injury Reported", _e(a["Injury_Reported"])),
                ("Witness Available", _e(a["Witness_Available"])),
            ]
        )
        parts.append(f"<h3>Accident {index}</h3>{rows}" if len(accidents) > 1 else rows)

    severity = (
        finding("Damage_Severity")
        if inspection["Damage_Observed"] == "Yes"
        else '<span class="muted">Not applicable</span>'
    )
    parts += [
        "<h2>C. Inspection Details</h2>",
        _rows(
            [
                ("Inspection ID", _e(inspection["Inspection_ID"])),
                ("Inspection Date", _e(inspection["Inspection_Date"])),
                ("Inspection Location", _e(inspection["Inspection_Location"])),
                ("Vehicle Condition", finding("Vehicle_Condition")),
                ("Damage Observed", finding("Damage_Observed")),
                ("Damage Severity", severity),
                ("Parts Required", _e(inspection["Parts_Required"])),
                ("Repair Recommendation", finding("Repair_Recommendation")),
                ("Inspection Status", _e(inspection["Inspection_Status"])),
                ("Surveyor Comments", _e(inspection["Surveyor_Comments"] or None)),
            ]
        ),
    ]
    for warning in report.get("warnings") or []:
        parts.append(f'<p class="note">{escape(warning)}</p>')
    if invalid:
        labels = ", ".join(item["label"] for item in invalid.values())
        parts.append(
            f'<p class="note">Stored value(s) not among the allowed options: {escape(labels)}. Shown as stored.</p>'
        )

    parts.append("<h2>D. Vehicle Damage Assessment</h2>")
    damages = report["vehicle_damage"]
    if not damages:
        parts.append('<p class="muted">No vehicle damage records have been saved for this claim.</p>')
    for index, d in enumerate(damages, start=1):
        parts.append(
            _record(
                f"Damage {index}: {_text(d['Damaged_Part'])}",
                [
                    ("Damage Type", _e(d["Damage_Type"])),
                    ("Severity", _e(d["Damage_Severity"])),
                    ("Location", _e(d["Damage_Location"])),
                    ("Repair or Replace", _e(d["Repair_or_Replace"])),
                    ("Estimated Cost", escape(_money(d["Estimated_Damage_Cost"]))),
                    ("Photo Evidence Available", _e(d["Photo_Evidence_Available"])),
                    ("Description", _e(d["Damage_Description"])),
                ],
            )
        )
    if damages:
        parts.append(
            f'<p><span class="label">Total estimated damage cost:</span> '
            f'{escape(_money(report["total_estimated_damage_cost"]))}</p>'
        )

    parts.append("<h2>E. Evidence</h2>")
    evidence = report["evidence"]
    if not evidence:
        parts.append('<p class="muted">No surveyor-captured evidence has been saved for this inspection.</p>')
    for index, item in enumerate(evidence, start=1):
        parts.append(
            _record(
                f"Evidence {index}: {_text(item['File_Name'])}",
                [
                    ("Evidence Type", _e(item["Evidence_Type"])),
                    ("Evidence Date", _e(item["Evidence_Date"])),
                    ("Source", _e(item["Evidence_Source"])),
                    ("Verification Status (AI)", _e(item["Verification_Status"])),
                    ("Automated Analysis (AI)", _analysis_summary(item["analysis"])),
                    *_capture_rows(item.get("capture"), item.get("qualifying_capture")),
                ],
            )
        )
    parts.append(
        '<p class="note">Device-reported time and location are recorded and checked for plausibility; '
        "they are not proof of where or when a photo was taken.</p>"
    )

    parts += [
        "<h2>F. Surveyor</h2>",
        _rows([("Surveyor Employee ID", _e(report["surveyor"]["Employee_ID"]))]),
    ]
    return "<body>" + "".join(parts) + "</body>"


def _submission_review_html(review: dict | None) -> str:
    """A submitted report whose saved records no longer meet the current
    submission rules says so, with the reasons - it is not re-verified."""
    if not review or review.get("meets_current_requirements"):
        return ""
    items = "".join(f"<li>{escape(problem)}</li>" for problem in review.get("problems") or [])
    return f'<div class="review"><p><b>{escape(review["message"])}</b></p><ul>{items}</ul></div>'


def render_survey_report_pdf(report: dict) -> bytes:
    """A4 PDF of the report, paginated automatically, with a footer on
    every page (claim number, status, generation time and page X of Y)."""
    story = fitz.Story(html=_html(report), user_css=_CSS)
    page_rect = fitz.paper_rect("a4")
    content_rect = page_rect + (40, 40, -40, -50)

    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    more = 1
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()

    document = fitz.open("pdf", buffer.getvalue())
    claim_number = _text(report["claim"]["Claim_Number"])
    footer = f"Survey Report {claim_number} - {report['report_status']} - generated {_text(report['generated_at'])}"
    grey = (0.42, 0.45, 0.5)
    for number, page in enumerate(document, start=1):
        page.insert_text((40, page_rect.height - 25), footer, fontsize=7.5, color=grey)
        label = f"Page {number} of {document.page_count}"
        x = page_rect.width - 40 - fitz.get_text_length(label, fontsize=7.5)
        page.insert_text((x, page_rect.height - 25), label, fontsize=7.5, color=grey)
    document.set_metadata({"title": f"Survey Report {claim_number}", "creator": "CI-MICOP"})
    output = document.tobytes(garbage=3, deflate=True)
    document.close()
    return output
