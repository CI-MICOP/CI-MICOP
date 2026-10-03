"""Step 5.8.13-E: controlled multi-document validation corpus for the
Step 5.8.13-C narrative location-consistency research prototype
(services/semantic_consistency.py).

Every FIR / Survey Report text below was written by hand for this
validation. None of it is real accident data, and none of it comes from the
synthetic research dataset (whose document text is unrelated filler - see
the Step 5.8.13 audit). Results on this corpus describe how the prototype
behaves on these controlled phrasings only; they are not an accuracy
estimate for real-world police or survey reports.

Each case records two labels:
  ideal     - what a careful human reader would conclude about whether the
              two documents state the same accident location
  observed  - what the prototype actually returned when this corpus was
              first run (2026-10-02). Recorded from a real run, not
              predicted. test_semantic_consistency_corpus.py asserts the
              prototype still returns exactly this, so any future change
              to the prototype's behaviour shows up as a test failure and
              the results table in SEMANTIC_CONSISTENCY_VALIDATION.md must
              be updated alongside it.
"""

from dataclasses import dataclass

CONSISTENT = "CONSISTENT"
CONTRADICTION = "CONTRADICTION"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class CorpusCase:
    case_id: str
    category: str
    fir_text: str
    survey_text: str
    ideal: str
    observed: str
    note: str


CORPUS: list[CorpusCase] = [
    # ---------------------------------------------------------------- baseline behaviour
    CorpusCase(
        "V01", "same place, same wording",
        "The accident occurred near Anna Salai.",
        "The insured vehicle was damaged in an accident near Anna Salai.",
        ideal=CONSISTENT, observed=CONSISTENT,
        note="Baseline agreement.",
    ),
    CorpusCase(
        "V02", "same place, different preposition",
        "The collision happened at Anna Salai.",
        "Inspection confirms the accident took place near Anna Salai.",
        ideal=CONSISTENT, observed=CONSISTENT,
        note="'at' and 'near' are both accepted keywords.",
    ),
    CorpusCase(
        "V03", "same place, different capitalisation",
        "The accident occurred near ANNA SALAI.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=CONSISTENT,
        note="Normalisation upper-cases both sides before comparing.",
    ),
    CorpusCase(
        "V04", "different places",
        "The accident occurred near Anna Salai.",
        "The vehicle was damaged in an accident near Guindy.",
        ideal=CONTRADICTION, observed=CONTRADICTION,
        note="Baseline disagreement.",
    ),
    CorpusCase(
        "V05", "different places, 'in' keyword",
        "The accident happened in Velachery.",
        "Survey records the accident in Tambaram.",
        ideal=CONTRADICTION, observed=CONTRADICTION,
        note="Baseline disagreement using 'in'.",
    ),
    CorpusCase(
        "V06", "time mention alongside place",
        "The accident occurred at 6 PM near Anna Salai.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=CONSISTENT,
        note="'at 6' is ignored because the keyword must be followed by a capitalised word.",
    ),
    # ---------------------------------------------------------------- missing information
    CorpusCase(
        "V07", "no place in survey report",
        "The accident occurred near Anna Salai.",
        "The vehicle was inspected and front bumper damage was observed.",
        ideal=INCONCLUSIVE, observed=INCONCLUSIVE,
        note="Nothing to compare on one side.",
    ),
    CorpusCase(
        "V08", "no place in either document",
        "The vehicle met with an accident and the driver was unhurt.",
        "The survey inspection was completed and damage was recorded.",
        ideal=INCONCLUSIVE, observed=INCONCLUSIVE,
        note="Nothing to compare on either side.",
    ),
    # ---------------------------------------------------------------- known risks
    CorpusCase(
        "V09", "city and street in one document",
        "The accident occurred in Chennai near Anna Salai.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=INCONCLUSIVE,
        note="Two place mentions in the FIR make it ambiguous, so the prototype declines to compare.",
    ),
    CorpusCase(
        "V10", "longer form of the same place",
        "The accident occurred near Anna Salai.",
        "The vehicle was damaged near Anna Salai Junction.",
        ideal=CONSISTENT, observed=CONTRADICTION,
        note="Exact string comparison treats 'Anna Salai' and 'Anna Salai Junction' as different places.",
    ),
    CorpusCase(
        "V11", "two names for the same road",
        "The accident occurred near Anna Salai.",
        "The vehicle was damaged near Mount Road.",
        ideal=CONSISTENT, observed=CONTRADICTION,
        note="Anna Salai is the official name of Mount Road; the prototype has no knowledge of aliases.",
    ),
    CorpusCase(
        "V12", "keyword at start of sentence",
        "At Anna Salai, the car hit a road divider.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=INCONCLUSIVE,
        note="Keyword matching is case-sensitive, so 'At' is not recognised.",
    ),
    CorpusCase(
        "V13", "abbreviated place name",
        "The accident occurred near T. Nagar.",
        "The vehicle was damaged near T. Nagar.",
        ideal=CONSISTENT, observed=INCONCLUSIVE,
        note="A single-letter word followed by a full stop is not captured as a place.",
    ),
    CorpusCase(
        "V14", "place written in lower case",
        "The accident occurred near anna salai.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=INCONCLUSIVE,
        note="The place must start with a capital letter to be captured.",
    ),
    CorpusCase(
        "V15", "month name after 'in'",
        "The accident occurred in March near Anna Salai.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=INCONCLUSIVE,
        note="'March' is captured as a second place, making the FIR ambiguous.",
    ),
    CorpusCase(
        "V16", "hospital name after 'at'",
        "The accident occurred near Anna Salai. The driver was treated at Apollo Hospital.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=INCONCLUSIVE,
        note="'Apollo Hospital' is captured as a second place, making the FIR ambiguous.",
    ),
    CorpusCase(
        "V17", "capitalised word straight after the place",
        "The accident occurred near Anna Salai Monday morning.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONSISTENT, observed=CONTRADICTION,
        note="The capture runs on into 'Monday', so 'Anna Salai Monday' is compared with 'Anna Salai'.",
    ),
    CorpusCase(
        "V18", "real disagreement hidden by a second mention",
        "The accident occurred in Chennai near Guindy.",
        "The vehicle was damaged near Anna Salai.",
        ideal=CONTRADICTION, observed=INCONCLUSIVE,
        note="The FIR's two mentions make it ambiguous, so a genuine disagreement is not reported.",
    ),
]

# A few cases are also run through the real upload -> PDF text extraction ->
# endpoint pipeline, to confirm PDF extraction does not change the result.
END_TO_END_CASE_IDS = ["V01", "V04", "V10", "V12"]
