"""Step 5.8.25: limit on repeated failed logins.

After LOGIN_MAX_FAILED_ATTEMPTS wrong passwords in a row for the same
username from the same client address, further login attempts for that
pair are refused for LOGIN_LOCKOUT_MINUTES - including one with the right
password, otherwise guessing could simply continue.

Kept in memory on purpose (see
docs/project_documentation/SECURITY_AND_REGRESSION_REVIEW.md, Section 5.2):
- the approved schema has no column to store a lockout time, and this
  project does not change the schema without a demonstrated need;
- authentication_users.Failed_Login_Count is still updated by the login
  endpoint exactly as before - it is a record, not the limiter.

Consequences of in-memory state: the counts are lost when the API restarts,
and each API process counts separately. Counting per client address means
someone guessing a user's password blocks their own address, not the real
user's.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.core.config import settings

_MAX_TRACKED_KEYS = 10_000


@dataclass
class _Entry:
    failures: int
    last_failure: float


_entries: dict[tuple[str, str], _Entry] = {}
_lock = threading.Lock()


def _window_seconds() -> float:
    return settings.LOGIN_LOCKOUT_MINUTES * 60


def make_key(username: str, client_host: str | None) -> tuple[str, str]:
    return ((username or "").strip().lower(), client_host or "unknown")


def seconds_until_allowed(key: tuple[str, str], now: float | None = None) -> int:
    """0 when a login attempt may proceed, otherwise the seconds left."""
    now = time.monotonic() if now is None else now
    with _lock:
        entry = _entries.get(key)
        if entry is None:
            return 0
        remaining = entry.last_failure + _window_seconds() - now
        if remaining <= 0:
            del _entries[key]
            return 0
        if entry.failures < settings.LOGIN_MAX_FAILED_ATTEMPTS:
            return 0
        return int(remaining) + 1


def record_failure(key: tuple[str, str], now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _lock:
        entry = _entries.get(key)
        if entry is None or entry.last_failure + _window_seconds() <= now:
            if len(_entries) >= _MAX_TRACKED_KEYS:
                _drop_expired(now)
            _entries[key] = _Entry(failures=1, last_failure=now)
        else:
            entry.failures += 1
            entry.last_failure = now


def record_success(key: tuple[str, str]) -> None:
    with _lock:
        _entries.pop(key, None)


def reset_all() -> None:
    """For tests."""
    with _lock:
        _entries.clear()


def _drop_expired(now: float) -> None:
    window = _window_seconds()
    for key in [k for k, entry in _entries.items() if entry.last_failure + window <= now]:
        del _entries[key]
    if len(_entries) >= _MAX_TRACKED_KEYS:
        # Still full of live entries: forget the oldest rather than grow without limit.
        for key in sorted(_entries, key=lambda k: _entries[k].last_failure)[: _MAX_TRACKED_KEYS // 10]:
            del _entries[key]
