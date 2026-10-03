from __future__ import annotations

from pydantic import BaseModel


class PhotoMeasurementsOut(BaseModel):
    width: int
    height: int
    brightness: float  # mean grey level, 0-255
    contrast: float  # grey-level standard deviation
    reblur_ratio: float  # 0-1; near 1 means already blurry


class PhotoQualityOut(BaseModel):
    evidence_id: str
    evidence_type: str
    file_name: str
    status: str  # "NO_ISSUES_FOUND" | "ISSUES_FOUND" | "UNAVAILABLE"
    flags: list[str]
    measurements: PhotoMeasurementsOut | None
    explanation: str


class ClaimPhotoQualityOut(BaseModel):
    """Response for POST /officer/claims/{claim_id}/evidence/quality-check
    (Step 5.8.15 - see services/evidence_quality.py and
    docs/project_documentation/EVIDENCE_PHOTO_QUALITY.md).

    Deliberately has no combined quality score: each measurement is reported
    as-is alongside the plain flags it triggered."""

    Claim_ID: str
    photos_checked: int
    results: list[PhotoQualityOut]
    limitations: list[str]
