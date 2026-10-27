"""Business logic for surveyor evidence: photos taken with the in-app
camera (POST /surveyor/evidence/capture).

The earlier file-upload path (POST /surveyor/evidence) is retired - the
route answers 410 and there is no service function behind it - so a file
from the device's storage or gallery can never become surveyor evidence.
Follows services/document_upload.py's pattern (assignment check,
allow-listed type, content validated from the bytes, ID generation, and
the file+database transaction). See
docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import evidence as crud_evidence
from app.db_models.evidence import Evidence
from app.services import evidence_capture, evidence_storage, surveyor_workflow

# Real values observed in the approved dataset
# (ai_ml/datasets/CI_MICOP_15_Tables_Complete/10_evidence.xlsx, 1301 rows) -
# kept for reference; existing rows may hold them.
EVIDENCE_TYPE_VALUES = {"Survey Photo", "Damage Photo", "Accident Photo"}


async def _read_limited(upload_file: UploadFile, max_bytes: int) -> bytes:
    """Reads in bounded chunks so an oversized upload is rejected without
    first buffering the whole thing into memory."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload_file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds the maximum allowed size of {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ---------------------------------------------------------------- in-app camera capture

# What a surveyor's camera photo shows. Chosen for the inspection workflow
# (the dataset's own vocabulary - EVIDENCE_TYPE_VALUES above - stays valid
# for existing rows); stored as Evidence_Type, which is free text.
SURVEYOR_CAPTURE_TYPES = (
    "Vehicle Damage Close-up",
    "Overall Vehicle Condition",
    "Damage Location and Extent",
    "Accident Scene / Surroundings",
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _evidence_date(value: str | None, inspection, received: datetime) -> date:
    """The photo's evidence date: today by default; never in the future
    (IST) and never before the inspection's scheduled date."""
    if not value:
        return received.date()
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise _bad_request("The evidence date is not a valid date (YYYY-MM-DD).") from exc
    if parsed > received.date():
        raise _bad_request("The evidence date cannot be in the future.")
    if parsed < inspection.Inspection_Date:
        raise _bad_request("The evidence date cannot be before the scheduled inspection date.")
    return parsed


async def capture_evidence_for_surveyor(
    db: Session,
    employee_id: str,
    claim_id: str,
    evidence_type: str,
    photo: UploadFile,
    captured_at: str | None,
    latitude: float | None,
    longitude: float | None,
    accuracy_m: float | None,
    location_error: str | None,
    evidence_date: str | None = None,
    now: datetime | None = None,
) -> tuple[Evidence, dict]:
    """Stores a photo taken with the surveyor's in-app camera, with its
    capture record.

    The surveyor, claim, inspection and role come from the JWT and the
    database; Evidence_Source is set to "Surveyor" here, never taken from
    the request. A photo without a usable location is still stored but
    flagged, and does not count towards the surveyor-photo requirement.
    """
    inspection = surveyor_workflow.require_writable_step(
        db, claim_id, employee_id, surveyor_workflow.STEP_EVIDENCE, now
    )
    if evidence_type not in SURVEYOR_CAPTURE_TYPES:
        raise _bad_request(f"Unsupported evidence_type. Allowed values: {list(SURVEYOR_CAPTURE_TYPES)}")

    content = await _read_limited(photo, settings.EVIDENCE_MAX_UPLOAD_BYTES)
    ext, image_format, width, height = evidence_capture.validate_image(content)

    received = now or surveyor_workflow.now_ist()
    photo_date = _evidence_date(evidence_date, inspection, received)
    location, location_status = evidence_capture.location_record(latitude, longitude, accuracy_m, location_error)
    client_time, time_status = evidence_capture.client_time_status(captured_at, received)

    evidence_id = crud_evidence.generate_evidence_id(db)
    file_name = f"camera-capture-{received.strftime('%Y%m%d-%H%M%S')}{ext}"
    stored_path = evidence_storage.storage_path_for(claim_id, evidence_id, file_name)
    evidence = Evidence(
        Evidence_ID=evidence_id,
        Claim_ID=claim_id,
        Evidence_Type=evidence_type,
        File_Name=file_name,
        Evidence_Date=photo_date,
        Evidence_Source="Surveyor",
        # No automated analysis has run - honest "not yet analysed"
        # placeholders, as for uploaded evidence above.
        Image_Quality=Decimal("0.0000"),
        Vehicle_Damage_Detected=False,
        Damage_Severity="Pending",
        Location_Match=False,
        Duplicate_Evidence_Indicator=False,
        Evidence_Confidence_Score=Decimal("0.0000"),
        Verification_Status="Pending",
    )
    metadata = {
        "version": evidence_capture.METADATA_VERSION,
        "capture_method": evidence_capture.CAPTURE_METHOD,
        # Reported by the browser - recorded and plausibility-checked, not trusted.
        "client": {"captured_at": client_time, **location},
        # Established by the server.
        "server": {
            "role": evidence_capture.ROLE_SURVEYOR,
            "received_at": received.isoformat(),
            "surveyor_employee_id": inspection.Surveyor_ID,
            "claim_id": claim_id,
            "inspection_id": inspection.Inspection_ID,
            "evidence_id": evidence_id,
            **evidence_capture.image_facts(content, image_format, width, height),
        },
        "checks": {
            "location_status": location_status,
            "max_accuracy_m": evidence_capture.MAX_LOCATION_ACCURACY_M,
            "client_time_status": time_status,
            "content_validated": True,
        },
    }

    metadata_path = evidence_capture.metadata_path_for(stored_path)
    try:
        evidence_storage.save_file(stored_path, content)
        evidence_capture.write_metadata(stored_path, metadata)
    except OSError as exc:
        evidence_storage.delete_file(stored_path)
        evidence_storage.delete_file(metadata_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The photo could not be stored. No evidence record was saved.",
        ) from exc

    try:
        crud_evidence.create(db, evidence)
        db.commit()
    except Exception as exc:
        db.rollback()
        evidence_storage.delete_file(stored_path)
        evidence_storage.delete_file(metadata_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The evidence could not be saved. No file was retained.",
        ) from exc
    db.refresh(evidence)

    # Saving work on the Evidence step resumes forward progression: any
    # correction left open on an earlier step is closed.
    surveyor_workflow.close_corrections(
        inspection, ("inspection", "damage"), inspection.Surveyor_ID, "evidence_captured", strict=False
    )
    return evidence, metadata
