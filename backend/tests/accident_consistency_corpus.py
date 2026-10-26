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
from datetime import date, time

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
        "The accident occurred near Anna Salai on 20/08/2026.", None, MATCH, MATCH,  # was UNAVAILABLE in 5.8.16
    ),
    AccidentCase("A10", "date", "month-first (US) order", "Date of accident: 08/20/2026", None, MATCH, UNAVAILABLE),
    AccidentCase("A11", "date", "two-digit year", "Date of accident: 20/08/26", None, MATCH, UNAVAILABLE),
    AccidentCase("A12", "date", "dd-MON-yyyy", "DATE OF ACCIDENT : 20-AUG-2026", None, MATCH, MATCH),  # was UNAVAILABLE in 5.8.16
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
        "First Information Report Number: 123 / 2026", None, MATCH, MATCH,  # was a false MISMATCH in 5.8.16
    ),
    AccidentCase("F08", "fir", "'Cr. No.' (crime number) label", "Cr. No. 123/2026, Guindy Police Station", None, MATCH, UNAVAILABLE),
    # ------------------------------------------------------------ Step 5.8.17 held-out cases
    # Written after the Step 5.8.17 fixes but BEFORE running them, with new
    # wording, to check the fixes generalise beyond A09/A12/F07.
    AccidentCase(
        "A13", "date", "'happened at <place> on' + ordinal day and short month",
        "The collision happened at Guindy junction on 20th Aug 2026.", None, MATCH, MATCH,
    ),
    AccidentCase(
        "A14", "date", "labelled date plus an unlabelled dd-MON-yyyy report date",
        "Date of accident: 20-08-2026. Report dated 25-AUG-2026.", None, MATCH, MATCH,
    ),
    AccidentCase(
        "A15", "date", "a different date in the NEXT sentence must not be used",
        "The accident occurred near Anna Salai. On 22/08/2026 the vehicle was towed.", None, UNAVAILABLE, UNAVAILABLE,
    ),
    AccidentCase("F09", "fir", "spaces around the slash, then more text", "FIR No: 123 / 2026 dated 20/08/2026", None, MATCH, MATCH),
    AccidentCase("F10", "fir", "spaces around the slash, different number", "F.I.R. No. 77 / 2025", None, MISMATCH, MISMATCH),
    # ------------------------------------------------------------ FIR label variants ("FIR-No")
    # F11-F14 were UNAVAILABLE before the label pattern accepted a hyphen.
    AccidentCase("F11", "fir", "'FIR-No:' as OCR reads it", "FIR-No: 123/2026", None, MATCH, MATCH),
    AccidentCase("F12", "fir", "'FIR - No.' with spaces", "FIR - No. 123/2026 Police Station: Guindy", None, MATCH, MATCH),
    AccidentCase("F13", "fir", "'FIR-No' different number", "FIR-No: 124/2026", None, MISMATCH, MISMATCH),
    AccidentCase("F14", "fir", "'FIR-No' without a colon", "FIR-No 123/2026 dated 20/08/2026", None, MATCH, MATCH),
    AccidentCase("F15", "fir", "hyphen but no number word", "FIR-registered at Guindy police station.", None, UNAVAILABLE, UNAVAILABLE),
]


# ---------------------------------------------------------------- accident time (Step 5.8.17)
RECORD_TIME = time(18, 30)


@dataclass(frozen=True)
class TimeCase:
    case_id: str
    description: str
    fir_text: str
    survey_text: str | None
    ideal: str
    observed: str


# All written BEFORE the time check was first run.
TIME_CORPUS: list[TimeCase] = [
    TimeCase("T01", "24-hour time", "Time of accident: 18:30", None, MATCH, MATCH),
    TimeCase("T02", "12-hour time", "Time of accident: 6:30 PM", None, MATCH, MATCH),
    TimeCase("T03", "'occurred near <place> at' + p.m.", "The accident occurred near Anna Salai at 6.30 p.m.", None, MATCH, MATCH),
    TimeCase("T04", "'hrs', 15 minutes later", "Accident time: 1845 hrs", None, MATCH, MATCH),
    TimeCase("T05", "45 minutes later", "Time of accident: 7:15 PM", None, MISMATCH, MISMATCH),
    TimeCase("T06", "a.m. instead of p.m.", "Time of accident: 6:30 AM", None, MISMATCH, MISMATCH),
    TimeCase("T07", "FIR right, Survey Report different", "Time of accident: 18:30", "Time of accident: 21:00", MISMATCH, MISMATCH),
    TimeCase("T08", "only an unlabelled report time", "Report generated at 10:15 AM.", None, UNAVAILABLE, UNAVAILABLE),
    TimeCase("T09", "'at around'", "The accident occurred at around 6:30 PM.", None, MATCH, UNAVAILABLE),
    TimeCase("T10", "no time at all", "The accident occurred in the evening.", None, UNAVAILABLE, UNAVAILABLE),
    TimeCase("T11", "a dotted date is not read as a time", "Date of accident: 20.08.2026", None, UNAVAILABLE, UNAVAILABLE),
]
