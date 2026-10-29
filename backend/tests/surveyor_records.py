"""Shared helpers for database-backed tests that need a surveyor's workflow
records on seed_data's claim1 (an active inspection, vehicle damage,
evidence).

Every record is created through the real API and removed afterwards by
the `surveyor_records` fixture - including stored evidence files - so no
test leaves rows behind.
"""

import io

import pytest
from PIL import Image

from app.db.session import SessionLocal
from app.db_models.evidence import Evidence
from app.db_models.surveyor_inspection import SurveyorInspection
from app.db_models.vehicle_damage import VehicleDamage
from app.services import evidence_capture, evidence_storage
from tests.conftest import auth_headers

JPG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20


def real_jpeg() -> bytes:
    """A complete, decodable JPEG - the capture endpoint decodes images."""
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (30, 90, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()

COMPLETE_FINDINGS = {
    "Vehicle_Condition": "Fair",
    "Damage_Observed": "Yes",
    "Damage_Severity": "Minor",
    "Repair_Recommendation": "Repair",
}

DAMAGE_FIELDS = {
    "Damage_Type": "Rear Damage",
    "Damaged_Part": "Rear Bumper",
    "Damage_Severity": "Minor",
    "Damage_Location": "Rear",
    "Estimated_Damage_Cost": "15000.00",
    "Repair_or_Replace": "Repair",
    "Photo_Evidence_Available": True,
    "Damage_Description": "Cracked rear bumper.",
}


class SurveyorRecords:
    def __init__(self, client, token, claim_id):
        self.client = client
        self.token = token
        self.claim_id = claim_id
        self.inspection_ids: list[str] = []
        self.damage_ids: list[str] = []
        self.evidence_ids: list[str] = []

    def start_inspection(self, **findings) -> dict:
        response = self.client.post(
            "/api/v1/surveyor/inspections", json={"Claim_ID": self.claim_id}, headers=auth_headers(self.token)
        )
        assert response.status_code == 201, response.text
        inspection = response.json()
        self.inspection_ids.append(inspection["Inspection_ID"])
        if findings:
            response = self.patch(inspection["Inspection_ID"], findings)
            assert response.status_code == 200, response.text
            inspection = response.json()
        return inspection

    def patch(self, inspection_id: str, body: dict):
        return self.client.patch(
            f"/api/v1/surveyor/inspections/{inspection_id}", json=body, headers=auth_headers(self.token)
        )

    def add_damage(self, **overrides) -> dict:
        response = self.client.post(
            "/api/v1/surveyor/vehicle-damage",
            json={"Claim_ID": self.claim_id, **DAMAGE_FIELDS, **overrides},
            headers=auth_headers(self.token),
        )
        assert response.status_code == 201, response.text
        self.damage_ids.append(response.json()["Damage_ID"])
        return response.json()

    def legacy_upload(self, source: str = "Surveyor"):
        """The retired file-upload endpoint - answers 410 and stores nothing."""
        return self.client.post(
            "/api/v1/surveyor/evidence",
            headers=auth_headers(self.token),
            data={
                "claim_id": self.claim_id,
                "evidence_type": "Damage Photo",
                "evidence_date": "2026-09-10",
                "evidence_source": source,
            },
            files={"file": ("rear.jpg", JPG_BYTES, "image/jpeg")},
        )

    def capture_photo(self, latitude=13.0827, longitude=80.2707, accuracy_m=12.0, evidence_type="Vehicle Damage Close-up") -> dict:
        """A photo through the in-app camera endpoint, with a location
        reading - the only kind that satisfies the surveyor-photo rule."""
        data = {"claim_id": self.claim_id, "evidence_type": evidence_type}
        if latitude is not None:
            data.update({"latitude": str(latitude), "longitude": str(longitude), "accuracy_m": str(accuracy_m)})
        response = self.client.post(
            "/api/v1/surveyor/evidence/capture",
            headers=auth_headers(self.token),
            data=data,
            files={"photo": ("capture.jpg", real_jpeg(), "image/jpeg")},
        )
        assert response.status_code == 201, response.text
        self.evidence_ids.append(response.json()["Evidence_ID"])
        return response.json()

    def capture_photo_at_map_location(
        self, latitude=13.0827, longitude=80.2707, address_label=None, evidence_type="Vehicle Damage Close-up"
    ) -> dict:
        """A photo through the in-app camera endpoint, with an indoor-friendly
        map-selected location instead of a device GPS reading."""
        data = {
            "claim_id": self.claim_id,
            "evidence_type": evidence_type,
            "location_source": "map",
            "latitude": str(latitude),
            "longitude": str(longitude),
        }
        if address_label is not None:
            data["address_label"] = address_label
        response = self.client.post(
            "/api/v1/surveyor/evidence/capture",
            headers=auth_headers(self.token),
            data=data,
            files={"photo": ("capture.jpg", real_jpeg(), "image/jpeg")},
        )
        assert response.status_code == 201, response.text
        self.evidence_ids.append(response.json()["Evidence_ID"])
        return response.json()

    def cleanup(self) -> None:
        db = SessionLocal()
        try:
            if self.evidence_ids:
                for row in db.query(Evidence).filter(Evidence.Evidence_ID.in_(self.evidence_ids)).all():
                    path = evidence_storage.storage_path_for(row.Claim_ID, row.Evidence_ID, row.File_Name)
                    evidence_storage.delete_file(path)
                    evidence_storage.delete_file(evidence_capture.metadata_path_for(path))
                db.query(Evidence).filter(Evidence.Evidence_ID.in_(self.evidence_ids)).delete(
                    synchronize_session=False
                )
            if self.damage_ids:
                db.query(VehicleDamage).filter(VehicleDamage.Damage_ID.in_(self.damage_ids)).delete(
                    synchronize_session=False
                )
            if self.inspection_ids:
                db.query(SurveyorInspection).filter(
                    SurveyorInspection.Inspection_ID.in_(self.inspection_ids)
                ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


@pytest.fixture()
def surveyor_records(client, surveyor_token, seed_data):
    records = SurveyorRecords(client, surveyor_token, seed_data["claim1"])
    yield records
    records.cleanup()


@pytest.fixture()
def active_claim1_inspection(surveyor_records):
    """Damage and evidence writes need the surveyor's active (unsubmitted),
    scheduled and complete inspection - seed_data's inspection1 is already
    submitted. Damage_Observed "No", so evidence needs no damage record."""
    return surveyor_records.start_inspection(**{**COMPLETE_FINDINGS, "Damage_Observed": "No", "Damage_Severity": "Pending"})
