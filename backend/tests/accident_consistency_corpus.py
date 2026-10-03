"""Step 5.8.16: controlled validation corpus for the accident-detail
consistency checks (services/accident_consistency.py).

Every document text below was written by hand for this validation. None of
it is real police or survey text and none comes from the synthetic research
dataset. Results describe how the checks behave on these phrasings only -
not an accuracy estimate for real documents.

Each case records:
  ideal    - what a careful human reader would conclude
  observed - what the check actually returned when this corpus was first
             run (2026-10-03). Recorded from a real run, not predicted;
             test_accident_consistency.py asserts it still holds.
"""

from dataclasses import dataclass
from datetime import date

MATCH = "MATCH"
MISMATCH = "MISMATCH"
UNAVAILABLE = "UNAVAILABLE"

RECORD_DATE = date(2026, 8, 20)
RECORD_FIR = "123/2026"


@dataclass(frozen=True)
class AccidentCase:
    case_id: str
    check: str  # "date" | "fir"
    description: str
    fir_text: str
    survey_text: str | None
    ideal: str
    observed: str


CORPUS: list[AccidentCase] = [
    # ------------------------------------------------------------ accident date (record: 2026-08-20)
    AccidentCase("A01", "date", "dd/mm/yyyy after 'Date of accident'", "Date of accident: 20/08/2026.", None, MATCH, MATCH),
    AccidentCase("A02", "date", "ISO date after 'Accident date'", "Accident date: 2026-08-20", None, MATCH, MATCH),
    AccidentCase("A03", "date", "'occurred on' + day month year", "The accident occurred on 20 August 2026.", None, MATCH, MATCH),
    AccidentCase("A04", "date", "'Date of incident' + month day, year", "Date of incident: August 20, 2026", None, MATCH, MATCH),
    AccidentCase("A05", "date", "dotted date", "Date of accident: 20.08.2026", None, MATCH, MATCH),
    AccidentCase("A06", "date", "FIR states a different day", "Date of accident: 21/08/2026", None, MISMATCH, MISMATCH),
    AccidentCase(
        "A07", "date", "FIR correct, Survey Report different",
        "Date of accident: 20/08/2026", "Date of accident: 22/08/2026", MISMATCH, MISMATCH,
    ),
    AccidentCase(
        "A08", "date", "only an unlabelled report date",
        "Report printed on 25/08/2026. Front bumper damaged.", None, UNAVAILABLE, UNAVAILABLE,
    ),
    AccidentCase(
        "A09", "date", "place between 'occurred' and 'on'",
        "The accident occurred near Anna Salai on 20/08/2026.", None, MATCH, UNAVAILABLE,
    ),
    AccidentCase("A10", "date", "month-first (US) order", "Date of accident: 08/20/2026", None, MATCH, UNAVAILABLE),
    AccidentCase("A11", "date", "two-digit year", "Date of accident: 20/08/26", None, MATCH, UNAVAILABLE),
    AccidentCase("A12", "date", "dd-MON-yyyy", "DATE OF ACCIDENT : 20-AUG-2026", None, MATCH, UNAVAILABLE),
    # ------------------------------------------------------------ FIR number (record: 123/2026)
    AccidentCase("F01", "fir", "'FIR No:'", "FIR No: 123/2026", None, MATCH, MATCH),
    AccidentCase("F02", "fir", "'F.I.R. No.'", "F.I.R. No. 123/2026 registered at Guindy.", None, MATCH, MATCH),
    AccidentCase("F03", "fir", "lower case", "fir no: 123/2026", None, MATCH, MATCH),
    AccidentCase("F04", "fir", "different number", "FIR No: 124/2026", None, MISMATCH, MISMATCH),
    AccidentCase("F05", "fir", "FIR mentioned, no number", "An FIR was lodged at Guindy police station.", None, UNAVAILABLE, UNAVAILABLE),
    AccidentCase(
        "F06", "fir", "correct number plus an older reference",
        "FIR No: 123/2026. Previous complaint ref FIR No: 77/2025.", None, MATCH, MATCH,
    ),
    AccidentCase(
        "F07", "fir", "spaces around the slash",
        "First Information Report Number: 123 / 2026", None, MATCH, MISMATCH,
    ),
    AccidentCase("F08", "fir", "'Cr. No.' (crime number) label", "Cr. No. 123/2026, Guindy Police Station", None, MATCH, UNAVAILABLE),
]
