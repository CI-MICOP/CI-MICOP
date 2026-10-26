"""Policy in force on the accident date - database-free."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import policy_cover as pc

START, END = date(2025, 8, 1), date(2026, 7, 31)


@pytest.mark.parametrize(
    "accident, expected",
    [
        (date(2026, 1, 10), pc.STATUS_COVERED),
        (START, pc.STATUS_COVERED),  # first day inclusive
        (END, pc.STATUS_COVERED),  # last day inclusive
        (date(2026, 8, 1), pc.STATUS_EXPIRED),  # day after expiry
        (date(2026, 9, 2), pc.STATUS_EXPIRED),  # SCN-CLM-15
        (date(2025, 7, 31), pc.STATUS_NOT_STARTED),
    ],
)
def test_cover_is_decided_by_the_recorded_dates(accident, expected):
    assert pc.check_cover(accident, START, END).status == expected


def test_no_fixed_policy_length_is_assumed():
    # A six-month and a three-year period are both judged on their own dates.
    assert pc.check_cover(date(2026, 8, 1), date(2026, 1, 1), date(2026, 6, 30)).status == pc.STATUS_EXPIRED
    assert pc.check_cover(date(2028, 5, 1), date(2026, 1, 1), date(2028, 12, 31)).status == pc.STATUS_COVERED


@pytest.mark.parametrize("args", [(None, START, END), (date(2026, 1, 1), None, END), (date(2026, 1, 1), START, None)])
def test_missing_dates_cannot_run_and_are_never_covered(args):
    result = pc.check_cover(*args)
    assert result.status == pc.STATUS_CANNOT_RUN
    assert "not recorded" in result.explanation


def test_inverted_period_cannot_run():
    assert pc.check_cover(date(2026, 1, 1), END, START).status == pc.STATUS_CANNOT_RUN


def test_single_period_limitation_is_always_stated():
    assert pc.SINGLE_PERIOD_LIMITATION in pc.check_cover(date(2026, 1, 1), START, END).limitations


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *_):
        return self

    def order_by(self, *_):
        return self

    def first(self):
        return self.row


def test_claim_without_accident_or_policy_record_cannot_run(monkeypatch):
    db = SimpleNamespace(query=lambda model: _Query(None))
    monkeypatch.setattr(pc.crud_policy, "get", lambda db, policy_id: None)
    result = pc.check_claim_policy_cover(db, SimpleNamespace(Claim_ID="CLM-1", Policy_ID="POL-1"))
    assert result.status == pc.STATUS_CANNOT_RUN


def test_claim_entry_point_reads_accident_and_policy_records(monkeypatch):
    db = SimpleNamespace(query=lambda model: _Query(SimpleNamespace(Accident_Date=date(2026, 9, 2))))
    policy = SimpleNamespace(Policy_Start_Date=START, Policy_End_Date=END)
    monkeypatch.setattr(pc.crud_policy, "get", lambda db, policy_id: policy)
    result = pc.check_claim_policy_cover(db, SimpleNamespace(Claim_ID="CLM-1", Policy_ID="POL-1"))
    assert result.status == pc.STATUS_EXPIRED
