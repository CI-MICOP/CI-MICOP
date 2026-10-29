"""Photos surveyors take with the in-app camera (evidence table) and their
capture records. (Customer accident photos are "Accident Photos" documents
- services/document_upload.py, services/claim_photos.py - and never
surveyor evidence.)

The schema has no columns for who captured a photo, how, or where, so -
until it is extended at dataset integration (see the proposed schema
changes in the project report) - the server writes a small JSON capture
record next to each stored photo, under the same storage root. Nothing in
PostgreSQL changes.

The record separates what the browser reported ("client") from what the
server established itself ("server": role, identity, claim, inspection,
receipt time, image facts) and from the checks the server ran ("checks").
Browser-reported time and coordinates can be spoofed; they are recorded
and checked for plausibility, never treated as proof. The capture record
itself lives on the server's disk; it is not tamper-proof against someone
with access to that disk.

Integrity (fail closed): a record is written once, atomically (temporary
file + rename, so a crash never leaves a half-written record), and is
only accepted when it is well-formed, names the same claim and row it is
stored next to, and its SHA-256 and size still match the stored photo. A
missing, unreadable, mismatched or altered record means "not a verified
capture" - never a fallback to the row's Evidence_Source or file name.
"""
from __future__ import annotations

import functools
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

from app.crud import evidence as crud_evidence
from app.crud import surveyor_inspection as crud_inspection
from app.services import evidence_storage

CAPTURE_METHOD = "in_app_camera"
METADATA_VERSION = 2

ROLE_SURVEYOR = "surveyor"

# Location readings less precise than this (the browser's reported
# accuracy radius) are recorded but do not count as a captured location.
# No project rule existed; 100 m is a pragmatic default for a phone GPS
# fix outdoors. It shows the photo was taken near a reported point - it
# does not prove the accident site.
MAX_LOCATION_ACCURACY_M = 100.0

# A client capture time further than this from the server receipt time is
# flagged as inconsistent (clock skew, a delayed upload or manipulation).
MAX_CLIENT_TIME_SKEW_S = 10 * 60

LOCATION_CAPTURED = "captured"
LOCATION_UNAVAILABLE = "unavailable"
LOCATION_INSUFFICIENT = "accuracy_insufficient"
# A surveyor-confirmed point picked on the map/address-search fallback
# (indoor-friendly: device GPS is often unusable indoors). Never upgraded
# to LOCATION_CAPTURED - a map pick is never presented as GPS-verified.
LOCATION_MAP_SELECTED = "map_selected"

# The only two statuses that satisfy "a usable location reading" for the
# surveyor-photo requirement (services/surveyor_workflow.py via
# qualifies_for_inspection below): a sufficiently accurate GPS fix, or an
# explicit map selection the surveyor confirmed. accuracy_insufficient and
# unavailable are recorded honestly but never count - the fix for the
# original indoor-GPS problem is the map fallback, not silently accepting
# a bad or missing reading.
LOCATION_USABLE_STATUSES = frozenset({LOCATION_CAPTURED, LOCATION_MAP_SELECTED})

LOCATION_SOURCE_VALUES = frozenset({"gps", "map"})
MAX_ADDRESS_LABEL_LENGTH = 255

# Formats a browser canvas produces, identified from the bytes themselves.
_CAPTURE_FORMATS = ((b"\xff\xd8\xff", ".jpg", "JPEG"), (b"\x89PNG\r\n\x1a\n", ".png", "PNG"))
_LOCATION_ERRORS = {"permission_denied", "position_unavailable", "timeout", "unsupported"}


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


# ---------------------------------------------------------------- validation


def validate_image(content: bytes) -> tuple[str, str, int, int]:
    """(extension, format, width, height) - the bytes must be a complete,
    decodable JPEG or PNG; the client's filename and MIME type are ignored."""
    if not content:
        raise _bad_request("The captured photo is empty.")
    match = next(((ext, fmt) for sig, ext, fmt in _CAPTURE_FORMATS if content.startswith(sig)), None)
    if match is None:
        raise _bad_request("The captured photo must be a JPEG or PNG image.")
    ext, fmt = match
    try:
        with Image.open(io.BytesIO(content)) as image:
            detected = image.format
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise _bad_request("The captured photo could not be read as an image.") from exc
    if detected != fmt:
        raise _bad_request("The captured photo does not match its image format.")
    return ext, fmt, width, height


def location_record(latitude, longitude, accuracy_m, location_error) -> tuple[dict, str]:
    """The device-GPS-reported location and the server's verdict on it.
    Never called for a map-selected location - see map_location_record."""
    error = location_error if location_error in _LOCATION_ERRORS else ("other" if location_error else None)
    if latitude is None or longitude is None or accuracy_m is None:
        missing = {
            "latitude": None,
            "longitude": None,
            "accuracy_m": None,
            "error": error or "not_provided",
            "source": "gps",
            "address_label": None,
        }
        return missing, LOCATION_UNAVAILABLE
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180) or not (accuracy_m > 0):
        raise _bad_request("The reported location is not valid.")
    location = {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_m": accuracy_m,
        "error": None,
        "source": "gps",
        "address_label": None,
    }
    if accuracy_m > MAX_LOCATION_ACCURACY_M:
        return location, LOCATION_INSUFFICIENT
    return location, LOCATION_CAPTURED


def map_location_record(latitude, longitude, address_label: str | None) -> tuple[dict, str]:
    """A location the surveyor picked themselves on the map/address-search
    fallback, confirmed before saving. No accuracy figure exists for a
    manual pick - never fabricated - and this is never classified as
    LOCATION_CAPTURED (GPS-verified), whatever the client sends."""
    if latitude is None or longitude is None:
        raise _bad_request("A map-selected location requires latitude and longitude.")
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise _bad_request("The selected location is not valid.")
    label = (address_label or "").strip()[:MAX_ADDRESS_LABEL_LENGTH] or None
    location = {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_m": None,
        "error": None,
        "source": "map",
        "address_label": label,
    }
    return location, LOCATION_MAP_SELECTED


def client_time_status(captured_at: str | None, received: datetime) -> tuple[str | None, str]:
    if not captured_at:
        return None, "missing"
    try:
        parsed = datetime.fromisoformat(captured_at)
    except ValueError:
        return captured_at[:64], "invalid"
    if parsed.tzinfo is None:
        return captured_at[:64], "invalid"
    skew = abs((received - parsed).total_seconds())
    return parsed.isoformat(), ("consistent" if skew <= MAX_CLIENT_TIME_SKEW_S else "inconsistent")


def image_facts(content: bytes, image_format: str, width: int, height: int) -> dict:
    return {
        "image_format": image_format,
        "width": width,
        "height": height,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


# ---------------------------------------------------------------- capture records on disk


def metadata_path_for(stored_photo_path: Path) -> Path:
    return stored_photo_path.with_name(stored_photo_path.name + ".capture.json")


def atomic_write_json(path: Path, data: dict, *, exclusive: bool = False) -> None:
    """Writes `path` all-or-nothing: a temporary file in the same folder,
    flushed to disk, then renamed over the target (atomic on one
    filesystem). With `exclusive`, an existing file is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise FileExistsError(path)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive and path.exists():
            raise FileExistsError(path)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def write_metadata(stored_photo_path: Path, metadata: dict) -> Path:
    """A capture record is written once, next to its new photo."""
    path = metadata_path_for(stored_photo_path)
    atomic_write_json(path, metadata, exclusive=True)
    return path


def update_review(stored_photo_path: Path, metadata: dict, kept: bool, employee_id: str, when: datetime) -> dict:
    """Records the surveyor's explicit Keep/un-keep decision for an
    already-captured photo, alongside its existing capture record. Only the
    "review" key is replaced - everything the server established at capture
    time (client/server/checks) is carried over exactly as read, so this can
    never be used to alter the recorded location, time or image facts."""
    updated = {**metadata, "review": {"kept": kept, "kept_by": employee_id, "kept_at": when.isoformat()}}
    atomic_write_json(metadata_path_for(stored_photo_path), updated)
    return updated


@functools.lru_cache(maxsize=512)
def _file_sha256(path: str, mtime_ns: int, size: int) -> str:
    # Keyed on modification time and size, so a changed file is re-hashed.
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _well_formed(data) -> bool:
    if not isinstance(data, dict) or data.get("capture_method") != CAPTURE_METHOD:
        return False
    if data.get("version") != METADATA_VERSION:
        return False
    server, checks = data.get("server"), data.get("checks")
    if not isinstance(server, dict) or not isinstance(checks, dict) or not isinstance(data.get("client"), dict):
        return False
    if server.get("role") != ROLE_SURVEYOR:
        return False
    sha = server.get("sha256")
    return isinstance(sha, str) and len(sha) == 64 and isinstance(server.get("size_bytes"), int)


def read_metadata_at(stored_photo_path: Path, expected: dict) -> dict | None:
    """The capture record next to a stored photo, only if it is well-formed,
    every `expected` server field matches (claim, row id, ...) and the
    photo on disk is still the one it describes. None otherwise."""
    try:
        data = json.loads(metadata_path_for(stored_photo_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not _well_formed(data):
        return None
    server = data["server"]
    if any(server.get(field) != value for field, value in expected.items()):
        return None
    try:
        stat = stored_photo_path.stat()
        if stat.st_size != server["size_bytes"]:
            return None
        if _file_sha256(str(stored_photo_path), stat.st_mtime_ns, stat.st_size) != server["sha256"]:
            return None
    except OSError:
        return None
    return data


def read_metadata(evidence) -> dict | None:
    """The verified surveyor capture record for an evidence row, or None
    when the photo was not taken with the surveyor's in-app camera (dataset
    rows, customer rows, older uploads) or the record is missing,
    unreadable, for another row, or no longer matches the stored photo."""
    if evidence.Evidence_Source != "Surveyor":
        return None
    try:
        photo_path = evidence_storage.storage_path_for(evidence.Claim_ID, evidence.Evidence_ID, evidence.File_Name)
    except ValueError:
        return None
    return read_metadata_at(
        photo_path,
        {"role": ROLE_SURVEYOR, "claim_id": evidence.Claim_ID, "evidence_id": evidence.Evidence_ID},
    )


def role_of(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    return (metadata.get("server") or {}).get("role")


def is_surveyor_capture_for(metadata: dict | None, inspection) -> bool:
    """Taken through the surveyor camera endpoint by this inspection's own
    surveyor, for this inspection. Customer photos and any evidence row
    without such a record (whatever its Evidence_Source says) never are."""
    if role_of(metadata) != ROLE_SURVEYOR:
        return False
    server = metadata.get("server") or {}
    return server.get("surveyor_employee_id") == inspection.Surveyor_ID and server.get("inspection_id") == inspection.Inspection_ID


def qualifies_for_inspection(metadata: dict | None, inspection) -> bool:
    """Whether a photo satisfies the surveyor-photo requirement: a surveyor
    capture for this inspection with a usable location reading - a
    sufficiently accurate GPS fix, or a surveyor-confirmed map selection
    (see LOCATION_USABLE_STATUSES). Neither an insufficient-accuracy GPS
    reading nor a missing one ever qualifies."""
    return is_surveyor_capture_for(metadata, inspection) and (metadata.get("checks") or {}).get(
        "location_status"
    ) in LOCATION_USABLE_STATUSES


def public_view(metadata: dict | None) -> dict | None:
    """What the surveyor API and the report show - no storage paths."""
    if not metadata:
        return None
    review = metadata.get("review") or {}
    return {
        "capture_method": metadata.get("capture_method"),
        "client": metadata.get("client") or {},
        "server": metadata.get("server") or {},
        "checks": metadata.get("checks") or {},
        # None until the surveyor makes an explicit choice - never defaulted
        # to "kept" just because the photo was saved.
        "review": {"kept": review.get("kept"), "kept_at": review.get("kept_at")},
    }


# ---------------------------------------------------------------- Claims Officer review


def claim_evidence_locations(db, claim_id: str) -> list[dict]:
    """Every surveyor-camera evidence item on this claim with its location
    source and status - for the Claims Officer's Evidence Check (never the
    storage path, never upgraded from what the surveyor actually recorded).
    Customer evidence (no in-app surveyor capture record) is left out, the
    same scope the surveyor's own evidence view uses. qualifying_capture is
    resolved against the capture's OWN inspection (read from its server
    metadata), not whichever inspection the caller happens to have, since
    an officer has none of their own."""
    inspections = {i.Inspection_ID: i for i in crud_inspection.list_by_claim(db, claim_id)}
    rows = []
    for evidence in crud_evidence.list_by_claim(db, claim_id):
        metadata = read_metadata(evidence)
        if role_of(metadata) != ROLE_SURVEYOR:
            continue
        inspection = inspections.get((metadata.get("server") or {}).get("inspection_id"))
        rows.append(
            {
                "Evidence_ID": evidence.Evidence_ID,
                "Evidence_Type": evidence.Evidence_Type,
                "Evidence_Date": evidence.Evidence_Date,
                "capture": public_view(metadata),
                "qualifying_capture": bool(inspection) and qualifies_for_inspection(metadata, inspection),
            }
        )
    return rows
