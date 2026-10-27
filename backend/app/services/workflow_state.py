"""Server-side correction state for a surveyor's inspection.

The schema has nowhere to record that a surveyor deliberately reopened a
completed step, so - until a table is added at dataset integration (see
the proposed schema changes) - the server keeps it in a small JSON file
per inspection under the evidence storage root, next to the claim's
evidence. Only the server writes it; nothing a client sends is trusted as
"correction mode". Every open/close is kept as an audit trail.

Robustness, as far as files allow:
- writes are atomic (temporary file + rename): a crash leaves the old or
  the new state, never a half-written file;
- read-modify-write is serialised by a lock inside this process, so two
  requests handled by one server process cannot lose each other's change;
- a file that exists but is unreadable or malformed raises
  WorkflowStateError: it is never treated as "no corrections" for a write
  and never overwritten, so its audit history is not destroyed.

Not guaranteed: with several server processes (e.g. multiple workers)
the in-process lock does not serialise writes between them, and there is
no transaction shared with PostgreSQL. A database table is the proper fix
(proposed for the integration phase).
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from app.core.config import settings
from app.services.evidence_capture import atomic_write_json

CORRECTABLE_STEPS = ("inspection", "damage")
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_LOCK = threading.RLock()


class WorkflowStateError(RuntimeError):
    """The correction state file exists but cannot be trusted."""


def _path_for(inspection) -> Path:
    root = Path(settings.EVIDENCE_STORAGE_ROOT).resolve()
    claim = _UNSAFE.sub("_", inspection.Claim_ID) or "unknown-claim"
    name = _UNSAFE.sub("_", inspection.Inspection_ID) or "unknown-inspection"
    path = (root / claim / f"{name}.workflow.json").resolve()
    if root not in path.parents:
        raise ValueError("Workflow state path escapes the evidence storage root")
    return path


def _valid(data, inspection) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("inspection_id", inspection.Inspection_ID) != inspection.Inspection_ID:
        return False
    corrections, history = data.get("open_corrections"), data.get("history")
    if not isinstance(corrections, dict) or not isinstance(history, list):
        return False
    if any(step not in CORRECTABLE_STEPS or not isinstance(at, str) for step, at in corrections.items()):
        return False
    return all(isinstance(entry, dict) for entry in history)


def read_state(inspection) -> dict:
    """The state for an inspection; empty when no file exists yet. Raises
    WorkflowStateError when the file exists but is unreadable/malformed."""
    path = _path_for(inspection)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"inspection_id": inspection.Inspection_ID, "open_corrections": {}, "history": []}
    except OSError as exc:
        raise WorkflowStateError(f"Correction state for {inspection.Inspection_ID} could not be read") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise WorkflowStateError(f"Correction state for {inspection.Inspection_ID} is corrupted") from exc
    if not _valid(data, inspection):
        raise WorkflowStateError(f"Correction state for {inspection.Inspection_ID} is malformed")
    data["inspection_id"] = inspection.Inspection_ID
    return data


def _write_state(inspection, data: dict) -> None:
    atomic_write_json(_path_for(inspection), data)


def open_corrections(inspection) -> dict:
    """{step: opened_at} for the corrections currently open."""
    return dict(read_state(inspection)["open_corrections"])


def is_open(inspection, step: str) -> bool:
    return step in read_state(inspection)["open_corrections"]


def open_correction(inspection, step: str, actor: str, at: str) -> None:
    with _LOCK:
        data = read_state(inspection)
        if step not in data["open_corrections"]:
            data["open_corrections"][step] = at
            data["history"].append({"event": "opened", "step": step, "by": actor, "at": at})
            _write_state(inspection, data)


def close_corrections(inspection, steps, actor: str, at: str, reason: str) -> None:
    with _LOCK:
        data = read_state(inspection)
        closing = [step for step in steps if step in data["open_corrections"]]
        if not closing:
            return
        for step in closing:
            data["open_corrections"].pop(step)
            data["history"].append({"event": "closed", "step": step, "by": actor, "at": at, "reason": reason})
        _write_state(inspection, data)
