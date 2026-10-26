"""RC validity, driving-licence validity / class / number, and policy cover,
each judged on the ACCIDENT date.

Deterministic, read-time only, never written to the database and never a
decision. What each check can see:

- RC: the labelled validity date on the customer-submitted RC copy (the kept
  verification record - see claim_copy_retention). The insurer's vehicles
  table records no RC validity date and no registry is integrated, so the
  copy's date cannot be cross-checked against an insurer reference. A
  registration MISMATCH (document_consistency) is reported first: the
  validity of an RC for another vehicle says nothing about this one.
- Licence: number, labelled validity date and classes from the submitted
  copy. The schema holds no licence record, so the number cannot be compared
  with an insurer reference (REFERENCE_UNAVAILABLE) unless one is passed in.
  The class needed is derived only from a recognisable vehicle type; per-class
  authorisation dates are not on the documents and are not checked.
- Policy: the policy record's own period (policy_cover), plus its
  Coverage_Type where that clearly excludes the claim's cover. One period per
  policy is recorded, so separate own-damage / third-party periods cannot be
  told apart.

No date is ever invented: a missing or unreadable date is INCONCLUSIVE, an
unreadable copy is VERIFICATION_UNAVAILABLE - never VERIFIED or expired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.crud import policy as crud_policy
from app.crud import vehicle as crud_vehicle
from app.db_models.accident import Accident
from app.db_models.claim import Claim
from app.services import document_consistency, document_fields, policy_cover
from app.services import verification_outcome as vo

RC_NO_REFERENCE = (
    "The insurer's vehicle record holds no RC validity date and no vehicle-registry service is integrated, "
    "so this is based only on the submitted RC copy."
)
LICENCE_NO_REFERENCE = (
    "The insurer holds no licence record in the application and no licensing service is integrated, "
    "so this is based only on the submitted licence copy."
)
CLASS_DATES_LIMITATION = "Per-class authorisation dates are not recorded on the copy and are not checked."


@dataclass
class ValidityCheck:
    outcome: str
    explanation: str
    evidence: dict[str, str | None] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


@dataclass
class ClaimValidityResult:
    rc_validity: ValidityCheck
    licence_number: ValidityCheck
    licence_validity: ValidityCheck
    licence_class: ValidityCheck
    policy_cover: ValidityCheck


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _no_accident_date(name: str) -> ValidityCheck:
    return ValidityCheck(vo.REFERENCE_UNAVAILABLE, f"{name} could not be checked because the claim has no accident date on record.")


# ---------------------------------------------------------------- RC


def check_rc_validity(documents, accident_date: date | None, registration: document_consistency.ConsistencyResult | None = None) -> ValidityCheck:
    rcs = [d for d in documents if d.Document_Type == "RC"]
    if not rcs:
        return ValidityCheck(vo.NOT_SUBMITTED, "RC validity could not be checked because no RC copy was submitted for this claim.")
    if registration is not None and registration.outcome == vo.MISMATCH:
        return ValidityCheck(
            vo.MISMATCH,
            "RC validity was not assessed: the registration number on the submitted RC copy does not match the "
            "insured vehicle, so its dates do not describe this vehicle.",
            {"registration_on_copy": registration.extracted_value, "registration_on_record": registration.structured_value},
        )
    if accident_date is None:
        return _no_accident_date("RC validity")
    found = [(raw, parsed, d) for d in rcs for raw, parsed in document_fields.extract_rc_fields(d.Extracted_Text).validity_dates]
    if not found:
        outcome = vo.no_text_outcome(rcs)
        reason = ("no text could be read from the RC copy (not analysed, OCR unavailable, or unreadable)"
                  if outcome == vo.VERIFICATION_UNAVAILABLE else "no labelled validity date was found on the RC copy")
        return ValidityCheck(outcome, f"RC validity could not be determined: {reason}. It is not assumed valid or expired.",
                             {"accident_date": _iso(accident_date)}, [RC_NO_REFERENCE])
    # A renewed RC can show more than one validity date; the latest one governs.
    raw, valid_upto, document = max(found, key=lambda item: item[1])
    evidence = {"accident_date": _iso(accident_date), "valid_upto": _iso(valid_upto), "as_written": raw,
                "document_id": document.Document_ID}
    if accident_date > valid_upto:
        return ValidityCheck(vo.INVALID_OR_EXPIRED,
                             f"The RC copy records registration validity up to {valid_upto.isoformat()}, before the "
                             f"accident on {accident_date.isoformat()}. Needs officer review.", evidence, [RC_NO_REFERENCE])
    return ValidityCheck(vo.VERIFIED,
                         f"The RC copy records registration validity up to {valid_upto.isoformat()}, which covers the "
                         f"accident on {accident_date.isoformat()}.", evidence, [RC_NO_REFERENCE])


# ---------------------------------------------------------------- licence

_CAR_WORDS = ("car", "jeep", "suv", "hatchback", "sedan", "muv")
_TWO_WHEELER_WORDS = ("motorcycle", "motor cycle", "scooter", "two wheeler", "two-wheeler", "bike")
_CLASSES_FOR_CAR = {"LMV", "LMV-NT", "LMV-TR", "LMV-TRANS"}
_CLASSES_FOR_TWO_WHEELER = {"MCWG", "MCEX50CC", "MC"}


def required_licence_classes(vehicle_type: str | None) -> tuple[str, set[str]] | None:
    """(class label, acceptable class codes) for a recognisable PRIVATE vehicle
    type; None when the type does not say (e.g. goods or transport vehicles,
    whose class rules this check does not model)."""
    text = (vehicle_type or "").lower()
    if any(word in text for word in ("goods", "transport", "commercial", "taxi", "bus", "truck")):
        return None
    if any(word in text for word in _TWO_WHEELER_WORDS):
        return "MCWG (motorcycle with gear)", _CLASSES_FOR_TWO_WHEELER
    if any(word in text for word in _CAR_WORDS):
        return "LMV (light motor vehicle)", _CLASSES_FOR_CAR
    return None


def check_licence(documents, accident_date: date | None, vehicle_type: str | None,
                  reference_number: str | None = None) -> tuple[ValidityCheck, ValidityCheck, ValidityCheck]:
    """(number, validity, class) for the submitted licence copy."""
    licences = [d for d in documents if d.Document_Type == "Driving Licence"]
    if not licences:
        missing = ValidityCheck(vo.NOT_SUBMITTED, "No driving-licence copy was submitted for this claim.")
        return missing, missing, missing
    fields = [document_fields.extract_licence_fields(d.Extracted_Text) for d in licences]
    unread = vo.no_text_outcome(licences) == vo.VERIFICATION_UNAVAILABLE
    unread_text = "no text could be read from the licence copy (not analysed, OCR unavailable, or unreadable)"

    numbers = [n for f in fields for n in f.numbers]
    if unread:
        number = ValidityCheck(vo.VERIFICATION_UNAVAILABLE, f"Licence number could not be checked: {unread_text}.")
    elif not numbers:
        number = ValidityCheck(vo.INCONCLUSIVE, "No labelled licence number was found on the licence copy.")
    elif reference_number is None:
        number = ValidityCheck(vo.REFERENCE_UNAVAILABLE,
                               "The licence number was read from the copy, but there is no insurer licence record to compare it with.",
                               {"number_on_copy": numbers[0]}, [LICENCE_NO_REFERENCE])
    elif document_fields.normalize_licence_number(reference_number) in {document_fields.normalize_licence_number(n) for n in numbers}:
        number = ValidityCheck(vo.VERIFIED, "The licence number on the copy matches the insurer's licence record.",
                               {"number_on_copy": numbers[0], "number_on_record": reference_number})
    else:
        number = ValidityCheck(vo.MISMATCH, "The licence number on the copy does not match the insurer's licence record.",
                               {"number_on_copy": numbers[0], "number_on_record": reference_number})

    dates = [d for f in fields for d in f.validity_dates]
    if accident_date is None:
        validity = _no_accident_date("Licence validity")
    elif unread:
        validity = ValidityCheck(vo.VERIFICATION_UNAVAILABLE, f"Licence validity could not be checked: {unread_text}.")
    elif not dates:
        bad = [b for f in fields for b in f.unparsed_dates]
        validity = ValidityCheck(vo.INCONCLUSIVE,
                                 "No usable labelled validity date was found on the licence copy"
                                 + (f" ('{bad[0]}' is not a valid date)" if bad else "")
                                 + ". It is not assumed valid or expired.", {"accident_date": _iso(accident_date)},
                                 [LICENCE_NO_REFERENCE])
    else:
        raw, valid_to = max(dates, key=lambda item: item[1])
        evidence = {"accident_date": _iso(accident_date), "valid_to": _iso(valid_to), "as_written": raw}
        if accident_date > valid_to:
            validity = ValidityCheck(vo.INVALID_OR_EXPIRED,
                                     f"The licence copy is valid to {valid_to.isoformat()}, before the accident on "
                                     f"{accident_date.isoformat()}. Needs officer review.", evidence, [LICENCE_NO_REFERENCE])
        else:
            validity = ValidityCheck(vo.VERIFIED,
                                     f"The licence copy is valid to {valid_to.isoformat()}, which covers the accident on "
                                     f"{accident_date.isoformat()}.", evidence, [LICENCE_NO_REFERENCE])

    classes = [c for f in fields for c in f.classes]
    needed = required_licence_classes(vehicle_type)
    if unread:
        vehicle_class = ValidityCheck(vo.VERIFICATION_UNAVAILABLE, f"Licence class could not be checked: {unread_text}.")
    elif needed is None:
        vehicle_class = ValidityCheck(vo.INCONCLUSIVE,
                                      f"The licence class needed for vehicle type '{vehicle_type or 'unknown'}' is not "
                                      "determined by this check.", {"classes_on_copy": ", ".join(classes) or None})
    elif not classes:
        vehicle_class = ValidityCheck(vo.INCONCLUSIVE, "No labelled vehicle class was found on the licence copy.",
                                      {"class_needed": needed[0]})
    elif needed[1] & set(classes):
        vehicle_class = ValidityCheck(vo.VERIFIED, f"The licence copy includes {needed[0]}, needed for this vehicle.",
                                      {"class_needed": needed[0], "classes_on_copy": ", ".join(classes)},
                                      [CLASS_DATES_LIMITATION])
    else:
        vehicle_class = ValidityCheck(vo.INVALID_OR_EXPIRED,
                                      f"The licence copy covers {', '.join(classes)} but not {needed[0]}, needed for this "
                                      "vehicle. Needs officer review.",
                                      {"class_needed": needed[0], "classes_on_copy": ", ".join(classes)},
                                      [CLASS_DATES_LIMITATION])
    return number, validity, vehicle_class


# ---------------------------------------------------------------- policy

_THIRD_PARTY_ONLY = ("third party only", "tp only", "liability only", "act only")
_OWN_DAMAGE_ONLY = ("own damage only", "od only", "standalone od", "stand-alone od")


def check_policy(policy, accident_date: date | None, claim_type: str | None) -> ValidityCheck:
    if policy is None:
        return ValidityCheck(vo.REFERENCE_UNAVAILABLE, "Policy cover could not be checked because no policy record was found for this claim.")
    cover = policy_cover.check_cover(accident_date, policy.Policy_Start_Date, policy.Policy_End_Date)
    evidence = {"accident_date": _iso(accident_date), "policy_start": _iso(policy.Policy_Start_Date),
                "policy_end": _iso(policy.Policy_End_Date), "coverage_type": policy.Coverage_Type,
                "claim_type": claim_type}
    limitations = list(cover.limitations)
    if cover.status == policy_cover.STATUS_CANNOT_RUN:
        outcome = vo.REFERENCE_UNAVAILABLE if accident_date is None else vo.INCONCLUSIVE
        return ValidityCheck(outcome, cover.explanation, evidence, limitations)
    if cover.status in (policy_cover.STATUS_EXPIRED, policy_cover.STATUS_NOT_STARTED):
        return ValidityCheck(vo.INVALID_OR_EXPIRED, cover.explanation, evidence, limitations)
    coverage = (policy.Coverage_Type or "").lower()
    if claim_type in ("Own Damage", "Theft") and any(word in coverage for word in _THIRD_PARTY_ONLY):
        return ValidityCheck(vo.INVALID_OR_EXPIRED,
                             f"The accident is within the policy period, but the cover recorded is "
                             f"'{policy.Coverage_Type}', which does not include {claim_type.lower()}. Needs officer review.",
                             evidence, limitations)
    if claim_type == "Third Party" and any(word in coverage for word in _OWN_DAMAGE_ONLY):
        return ValidityCheck(vo.INVALID_OR_EXPIRED,
                             f"The accident is within the policy period, but the cover recorded is "
                             f"'{policy.Coverage_Type}', which does not include third-party liability. Needs officer review.",
                             evidence, limitations)
    if not coverage or coverage in ("standard",):
        limitations.append(f"The recorded cover type '{policy.Coverage_Type}' does not say which sections apply; only the "
                           "period was checked.")
    return ValidityCheck(vo.VERIFIED, cover.explanation, evidence, limitations)


# ---------------------------------------------------------------- claim entry point


def check_claim_validity(db: Session, claim: Claim) -> ClaimValidityResult:
    """Read-only. The single entry point routers call."""
    accident = db.query(Accident).filter(Accident.Claim_ID == claim.Claim_ID).order_by(Accident.Accident_ID).first()
    accident_date = accident.Accident_Date if accident else None
    documents = crud_document.list_by_claim(db, claim.Claim_ID)
    vehicle = crud_vehicle.get(db, claim.Vehicle_ID)
    registration = document_consistency.compare_registration_number(db, claim)
    number, validity, vehicle_class = check_licence(documents, accident_date, vehicle.Vehicle_Type if vehicle else None)
    return ClaimValidityResult(
        rc_validity=check_rc_validity(documents, accident_date, registration),
        licence_number=number,
        licence_validity=validity,
        licence_class=vehicle_class,
        policy_cover=check_policy(crud_policy.get(db, claim.Policy_ID), accident_date, claim.Claim_Type),
    )
