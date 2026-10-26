"""What a verification check found, as one of seven distinct outcomes.

The older MATCH / MISMATCH / UNAVAILABLE `status` of the consistency checks
is kept unchanged (existing responses, tests and screens use it). `outcome`
is added next to it so that very different situations are no longer all
reported as UNAVAILABLE. Nothing here is persisted - no column or enum.

  VERIFIED                 - the check ran and the available evidence supports it
  MISMATCH                 - a reliable comparison ran and the values conflict
  NOT_SUBMITTED            - the customer did not upload the document this check needs
  REFERENCE_UNAVAILABLE    - the insurer-held record to compare with does not exist
  INVALID_OR_EXPIRED       - the document fails a validity rule on the relevant date
  VERIFICATION_UNAVAILABLE - the check could not run (no text extracted, OCR
                             unavailable, capability not implemented)
  INCONCLUSIVE             - it ran, but the evidence supports no conclusion

None of these is a claim decision; only the officer decides.
"""

from __future__ import annotations

VERIFIED = "VERIFIED"
MISMATCH = "MISMATCH"
NOT_SUBMITTED = "NOT_SUBMITTED"
REFERENCE_UNAVAILABLE = "REFERENCE_UNAVAILABLE"
INVALID_OR_EXPIRED = "INVALID_OR_EXPIRED"
VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
INCONCLUSIVE = "INCONCLUSIVE"

ALL_OUTCOMES = (VERIFIED, MISMATCH, NOT_SUBMITTED, REFERENCE_UNAVAILABLE, INVALID_OR_EXPIRED,
                VERIFICATION_UNAVAILABLE, INCONCLUSIVE)


def no_text_outcome(documents) -> str:
    """For documents that were submitted but yielded nothing usable: if none
    has any extracted text, the check could not run (not analysed yet, OCR
    unavailable, or unreadable); otherwise it ran and found nothing."""
    if all(not (d.Extracted_Text or "").strip() for d in documents):
        return VERIFICATION_UNAVAILABLE
    return INCONCLUSIVE
