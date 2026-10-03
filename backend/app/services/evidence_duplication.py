"""Step 5.8.14: evidence duplication / reuse check (roadmap item 4).

This is NOT fraud detection, NOT a fraud score, NOT a risk score, and NOT
an automatic claim decision. It answers one narrow question for a Claims
Officer: does a photo on this claim also appear - byte-for-byte, or as a
lightly edited copy - elsewhere among the evidence photos stored by this
application?

Method (no AI model - see docs/project_documentation/EVIDENCE_DUPLICATION.md):
  - exact copy: SHA-256 of the stored file bytes;
  - near copy:  a 64-bit difference hash ("dHash", a perceptual hash)
    computed with Pillow, already a backend dependency. Two photos are a
    near copy when their hashes differ in at most
    NEAR_DUPLICATE_MAX_DISTANCE bits.
This matches the "SHA-256 · pHash" part of the project's evidence-reuse
design. The embedding-model part (CLIP) is deliberately not implemented in
this step: it would need a heavy new dependency and a real labelled photo
set to validate it against, neither of which exists yet.

Read-time only: this module never writes to the database (it does not set
Evidence.Duplicate_Evidence_Indicator), never touches Final_Decision,
Approved_Amount or claim_decision_audit, and is not wired into
ai_pipeline.py. Photos from other claims are compared, because reuse across
claims is the case this check exists for; the endpoint exposing it is
restricted to Claims Officer / Admin, who may already view every claim.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.crud import evidence as crud_evidence
from app.db_models.claim import Claim
from app.db_models.evidence import Evidence
from app.services import evidence_storage

STATUS_EXACT_DUPLICATE = "EXACT_DUPLICATE"
STATUS_NEAR_DUPLICATE = "NEAR_DUPLICATE"
STATUS_NO_MATCH_FOUND = "NO_MATCH_FOUND"
STATUS_UNAVAILABLE = "UNAVAILABLE"

MATCH_EXACT = "EXACT"
MATCH_NEAR = "NEAR"

# Chosen from the Step 5.8.14 validation corpus (EVIDENCE_DUPLICATION.md,
# Section 5): resized, re-compressed, brightened/darkened and greyscale
# copies of the same generated image stayed within 0-6 bits, while
# genuinely different generated images were never closer than 19 bits.
# 10 sits between the two with margin on both sides. It is a documented
# design choice for this prototype, not a calibrated probability.
NEAR_DUPLICATE_MAX_DISTANCE = 10

_HASH_SIZE = 8  # 8x8 comparisons -> 64-bit hash

_STANDARD_LIMITATIONS = [
    "This is a deterministic image-fingerprint check (SHA-256 plus a 64-bit difference "
    "hash), not an AI or image-recognition model - it compares how photos look at a very "
    "coarse level, not what they show.",
    "It recognises resized, re-saved and lightly brightened or darkened copies, but not "
    "mirrored, rotated or heavily cropped copies.",
    "It only compares photos stored by this application - it cannot detect a photo taken "
    "from the internet or from another insurer's records.",
    "The near-copy threshold was chosen on generated test images, not on a labelled set "
    "of real accident photos.",
]


@dataclass
class Fingerprint:
    sha256: str
    dhash: int | None  # None when the bytes could not be decoded as an image


@dataclass
class EvidenceMatch:
    evidence_id: str
    claim_id: str
    same_claim: bool
    match_type: str  # "EXACT" | "NEAR"
    hash_distance: int | None  # bits differing in the dHash; None if not computable


@dataclass
class EvidenceDuplicationResult:
    evidence_id: str
    evidence_type: str
    file_name: str
    status: str
    matches: list[EvidenceMatch] = field(default_factory=list)
    explanation: str = ""


@dataclass
class ClaimEvidenceDuplicationResult:
    claim_id: str
    photos_checked: int
    photos_compared_against: int
    results: list[EvidenceDuplicationResult]
    limitations: list[str]


def compute_dhash(image: Image.Image, hash_size: int = _HASH_SIZE) -> int:
    """Difference hash: shrink to a (hash_size+1) x hash_size greyscale
    thumbnail and record, for each pixel, whether it is brighter than its
    right-hand neighbour. Small edits (resizing, re-compression, mild
    brightness change) barely move these comparisons; a different picture
    changes about half of them."""
    grey = image.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = grey.tobytes()
    width = hash_size + 1
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * width + col]
            right = pixels[row * width + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def fingerprint_bytes(content: bytes) -> Fingerprint:
    sha256 = hashlib.sha256(content).hexdigest()
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            dhash = compute_dhash(image)
    except (UnidentifiedImageError, OSError, ValueError):
        dhash = None
    return Fingerprint(sha256=sha256, dhash=dhash)


def _stored_path(evidence: Evidence) -> Path:
    return evidence_storage.storage_path_for(evidence.Claim_ID, evidence.Evidence_ID, evidence.File_Name)


def _load_fingerprint(evidence: Evidence) -> Fingerprint | None:
    """None when the stored file is missing or cannot be read at all -
    e.g. seeded development rows that never had a physical file."""
    try:
        content = _stored_path(evidence).read_bytes()
    except (OSError, ValueError):
        return None
    if not content:
        return None
    return fingerprint_bytes(content)


def compare_fingerprints(a: Fingerprint, b: Fingerprint) -> tuple[str, int | None] | None:
    """(match_type, hash_distance) if a and b are an exact or near copy,
    otherwise None."""
    distance = hamming_distance(a.dhash, b.dhash) if a.dhash is not None and b.dhash is not None else None
    if a.sha256 == b.sha256:
        return MATCH_EXACT, distance
    if distance is not None and distance <= NEAR_DUPLICATE_MAX_DISTANCE:
        return MATCH_NEAR, distance
    return None


def _describe(match: EvidenceMatch) -> str:
    where = "on this same claim" if match.same_claim else f"on claim {match.claim_id}"
    return f"evidence {match.evidence_id} {where}"


def _result_for(
    evidence: Evidence,
    fingerprint: Fingerprint | None,
    others: list[tuple[Evidence, Fingerprint]],
) -> EvidenceDuplicationResult:
    base = dict(evidence_id=evidence.Evidence_ID, evidence_type=evidence.Evidence_Type, file_name=evidence.File_Name)

    if fingerprint is None:
        return EvidenceDuplicationResult(
            **base,
            status=STATUS_UNAVAILABLE,
            explanation="The stored file for this photo could not be found or read, so it could not be compared.",
        )

    matches: list[EvidenceMatch] = []
    for other, other_fingerprint in others:
        found = compare_fingerprints(fingerprint, other_fingerprint)
        if found is None:
            continue
        match_type, distance = found
        matches.append(
            EvidenceMatch(
                evidence_id=other.Evidence_ID,
                claim_id=other.Claim_ID,
                same_claim=other.Claim_ID == evidence.Claim_ID,
                match_type=match_type,
                hash_distance=distance,
            )
        )
    # Exact copies first, then closest near copies; stable by ID for repeatability.
    matches.sort(key=lambda m: (m.match_type != MATCH_EXACT, m.hash_distance or 0, m.evidence_id))

    exact = [m for m in matches if m.match_type == MATCH_EXACT]
    near = [m for m in matches if m.match_type == MATCH_NEAR]

    if exact:
        return EvidenceDuplicationResult(
            **base,
            status=STATUS_EXACT_DUPLICATE,
            matches=matches,
            explanation=(
                "An identical file is also stored as " + ", ".join(_describe(m) for m in exact) + ". "
                "Possible evidence reuse identified for officer review."
            ),
        )
    if near:
        return EvidenceDuplicationResult(
            **base,
            status=STATUS_NEAR_DUPLICATE,
            matches=matches,
            explanation=(
                "A visually near-identical photo (for example resized or re-saved) is also stored as "
                + ", ".join(f"{_describe(m)} ({m.hash_distance} of 64 fingerprint bits differ)" for m in near)
                + ". Possible evidence reuse identified for officer review."
            ),
        )
    if fingerprint.dhash is None:
        return EvidenceDuplicationResult(
            **base,
            status=STATUS_UNAVAILABLE,
            explanation=(
                "No byte-identical copy was found, but the file could not be decoded as an image, "
                "so a near-copy comparison was not possible."
            ),
        )
    return EvidenceDuplicationResult(
        **base,
        status=STATUS_NO_MATCH_FOUND,
        explanation=(
            f"No identical or near-identical copy was found among the {len(others)} other stored "
            "evidence photo(s) that could be read. This does not prove the photo is original."
        ),
    )


def check_claim_evidence(db: Session, claim: Claim) -> ClaimEvidenceDuplicationResult:
    """Entry point routers should call. Fingerprints every readable stored
    evidence photo once, then compares each photo on this claim with every
    other one (same claim and other claims). Read-only."""
    own = crud_evidence.list_by_claim(db, claim.Claim_ID)
    readable: list[tuple[Evidence, Fingerprint]] = []
    fingerprints: dict[str, Fingerprint | None] = {}
    for evidence in crud_evidence.list_all(db):
        fp = _load_fingerprint(evidence)
        fingerprints[evidence.Evidence_ID] = fp
        if fp is not None:
            readable.append((evidence, fp))

    results = []
    for evidence in own:
        others = [(e, fp) for e, fp in readable if e.Evidence_ID != evidence.Evidence_ID]
        results.append(_result_for(evidence, fingerprints.get(evidence.Evidence_ID), others))

    return ClaimEvidenceDuplicationResult(
        claim_id=claim.Claim_ID,
        photos_checked=len(own),
        photos_compared_against=len(readable),
        results=results,
        limitations=list(_STANDARD_LIMITATIONS),
    )
