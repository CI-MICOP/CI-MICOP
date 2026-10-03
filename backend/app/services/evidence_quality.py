"""Step 5.8.15: evidence photo quality check (roadmap item 5, information
quality - photo part).

This is NOT fraud detection, NOT a risk score, and NOT an automatic claim
decision. It answers one narrow question for a Claims Officer: is each
evidence photo on this claim clear enough to rely on - or is it too small,
too dark, too bright, washed out, or blurry?

Method (no AI model - see docs/project_documentation/EVIDENCE_PHOTO_QUALITY.md):
simple image measurements computed with Pillow, already a backend
dependency, on a greyscale copy of the photo:
  - resolution: the photo's own width x height;
  - brightness: mean grey level (0 = black, 255 = white);
  - contrast:   standard deviation of the grey levels;
  - blur:       "re-blur ratio" - how much edge detail survives an extra
                Gaussian blur. A sharp photo loses most of its edge detail
                (low ratio); an already-blurry photo barely changes (ratio
                near 1). Unlike raw edge strength, this does not depend on
                how bright or contrasty the photo is.
Each measurement is compared against a documented threshold and reported
as a plain flag. There is deliberately no single combined quality score.

Read-time only: this module never writes to the database (it does not set
Evidence.Image_Quality or Evidence_Confidence_Score), never touches
Final_Decision, Approved_Amount or claim_decision_audit, and is not wired
into ai_pipeline.py.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.crud import evidence as crud_evidence
from app.db_models.claim import Claim
from app.db_models.evidence import Evidence
from app.services import evidence_storage

STATUS_NO_ISSUES_FOUND = "NO_ISSUES_FOUND"
STATUS_ISSUES_FOUND = "ISSUES_FOUND"
STATUS_UNAVAILABLE = "UNAVAILABLE"

FLAG_LOW_RESOLUTION = "LOW_RESOLUTION"
FLAG_TOO_DARK = "TOO_DARK"
FLAG_TOO_BRIGHT = "TOO_BRIGHT"
FLAG_LOW_CONTRAST = "LOW_CONTRAST"
FLAG_BLURRY = "BLURRY"

# Thresholds chosen from measurements on generated test images
# (EVIDENCE_PHOTO_QUALITY.md, Section 5) before the validation corpus was
# run. Documented design choices for this prototype, not calibrated values.
MIN_SHORT_SIDE_PX = 480  # VGA (640x480) is the smallest accepted size
MIN_BRIGHTNESS = 60  # normal test images measured 92-162
MAX_BRIGHTNESS = 200
MIN_CONTRAST = 15.0  # normal test images measured 21-54; washed-out 5-11
MAX_REBLUR_RATIO = 0.80  # sharp detailed images measured 0.17-0.31; blurred 0.88+

# Photos wider than this are shrunk first so blur and contrast are measured
# on a comparable scale and large photos stay fast. Smaller photos are never
# enlarged (enlarging would itself make them look blurry).
_ANALYSIS_MAX_WIDTH = 640
_REBLUR_RADIUS = 2

FLAG_TEXT = {
    FLAG_LOW_RESOLUTION: "low resolution",
    FLAG_TOO_DARK: "too dark",
    FLAG_TOO_BRIGHT: "too bright",
    FLAG_LOW_CONTRAST: "low contrast (washed out)",
    FLAG_BLURRY: "blurry",
}

_STANDARD_LIMITATIONS = [
    "These are simple image measurements (size, brightness, contrast, edge detail), not an AI or "
    "image-recognition model - they say whether a photo is clear, not what it shows.",
    "A photo of a plain, featureless surface has little edge detail and may be flagged as blurry "
    "even when it is in focus.",
    "Thresholds were chosen on generated test images, not on a labelled set of real accident photos.",
    "A clear photo is not necessarily a genuine or relevant one - see the separate photo copy check.",
]


@dataclass
class PhotoMeasurements:
    width: int
    height: int
    brightness: float
    contrast: float
    reblur_ratio: float


@dataclass
class PhotoQualityResult:
    evidence_id: str
    evidence_type: str
    file_name: str
    status: str
    flags: list[str] = field(default_factory=list)
    measurements: PhotoMeasurements | None = None
    explanation: str = ""


@dataclass
class ClaimPhotoQualityResult:
    claim_id: str
    photos_checked: int
    results: list[PhotoQualityResult]
    limitations: list[str]


def _edge_energy(grey: Image.Image) -> float:
    """Mean absolute difference between neighbouring pixels, across and down."""
    w, h = grey.size
    if w < 2 or h < 2:
        return 0.0
    across = ImageChops.difference(grey.crop((1, 0, w, h)), grey.crop((0, 0, w - 1, h)))
    down = ImageChops.difference(grey.crop((0, 1, w, h)), grey.crop((0, 0, w, h - 1)))
    return ImageStat.Stat(across).mean[0] + ImageStat.Stat(down).mean[0]


def measure_image(image: Image.Image) -> PhotoMeasurements:
    width, height = image.size
    grey = image.convert("L")
    if grey.width > _ANALYSIS_MAX_WIDTH:
        grey = grey.resize((_ANALYSIS_MAX_WIDTH, max(2, round(grey.height * _ANALYSIS_MAX_WIDTH / grey.width))), Image.LANCZOS)
    stats = ImageStat.Stat(grey)
    edges = _edge_energy(grey)
    reblur_ratio = 1.0 if edges == 0 else _edge_energy(grey.filter(ImageFilter.GaussianBlur(_REBLUR_RADIUS))) / edges
    return PhotoMeasurements(
        width=width,
        height=height,
        brightness=round(stats.mean[0], 1),
        contrast=round(stats.stddev[0], 1),
        reblur_ratio=round(reblur_ratio, 2),
    )


def flags_for(m: PhotoMeasurements) -> list[str]:
    flags = []
    if min(m.width, m.height) < MIN_SHORT_SIDE_PX:
        flags.append(FLAG_LOW_RESOLUTION)
    if m.brightness < MIN_BRIGHTNESS:
        flags.append(FLAG_TOO_DARK)
    if m.brightness > MAX_BRIGHTNESS:
        flags.append(FLAG_TOO_BRIGHT)
    if m.contrast < MIN_CONTRAST:
        flags.append(FLAG_LOW_CONTRAST)
    if m.reblur_ratio > MAX_REBLUR_RATIO:
        flags.append(FLAG_BLURRY)
    return flags


def measure_bytes(content: bytes) -> PhotoMeasurements | None:
    """None when the bytes cannot be decoded as an image."""
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            return measure_image(image)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _read_stored_bytes(evidence: Evidence) -> bytes | None:
    try:
        path = evidence_storage.storage_path_for(evidence.Claim_ID, evidence.Evidence_ID, evidence.File_Name)
        content = path.read_bytes()
    except (OSError, ValueError):
        return None
    return content or None


def assess_evidence(evidence: Evidence, content: bytes | None) -> PhotoQualityResult:
    base = dict(evidence_id=evidence.Evidence_ID, evidence_type=evidence.Evidence_Type, file_name=evidence.File_Name)
    if content is None:
        return PhotoQualityResult(
            **base,
            status=STATUS_UNAVAILABLE,
            explanation="The stored file for this photo could not be found or read, so its quality could not be checked.",
        )
    measurements = measure_bytes(content)
    if measurements is None:
        return PhotoQualityResult(
            **base,
            status=STATUS_UNAVAILABLE,
            explanation="The stored file could not be decoded as an image, so its quality could not be checked.",
        )
    flags = flags_for(measurements)
    if not flags:
        return PhotoQualityResult(
            **base,
            status=STATUS_NO_ISSUES_FOUND,
            measurements=measurements,
            explanation="No size, brightness, contrast or blur issue was found in this photo.",
        )
    return PhotoQualityResult(
        **base,
        status=STATUS_ISSUES_FOUND,
        flags=flags,
        measurements=measurements,
        explanation=(
            "This photo may be hard to rely on: " + ", ".join(FLAG_TEXT[f] for f in flags) + ". "
            "Consider requesting a clearer photo."
        ),
    )


def check_claim_photo_quality(db: Session, claim: Claim) -> ClaimPhotoQualityResult:
    """Entry point routers should call. Only reads this claim's own evidence
    files. Read-only."""
    own = crud_evidence.list_by_claim(db, claim.Claim_ID)
    return ClaimPhotoQualityResult(
        claim_id=claim.Claim_ID,
        photos_checked=len(own),
        results=[assess_evidence(e, _read_stored_bytes(e)) for e in own],
        limitations=list(_STANDARD_LIMITATIONS),
    )
