"""Local filesystem storage for uploaded claim documents.

Deliberately isolated in its own module, behind a small function
interface (`storage_path_for`, `save_file`, `delete_file`), so this is
the only place that needs to change if the project later moves to
S3/Azure/MinIO - see docs/project_documentation/CUSTOMER_DOCUMENT_UPLOAD.md.

PostgreSQL only ever stores document *metadata* (see db_models/document.py);
no binary file content is stored in the database.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings

# Whitelist rather than blacklist: anything not a letter, digit, dot,
# underscore or hyphen is replaced. This alone defeats path traversal
# (`../`, `..\\`, a leading `/` or `C:\`) since none of those characters
# survive, and Path(name).name below additionally strips any directory
# component the browser-supplied filename might still contain.
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(original_name: str) -> str:
    """Never trust the browser's filename as a filesystem path - this
    always returns a plain, safe basename with no directory component."""
    name = Path(original_name or "").name  # drops any "../", "..\\", or absolute-path component
    name = _UNSAFE_CHARS.sub("_", name).strip("._")
    return name[:100] or "upload"


def storage_path_for(owner_id: str, document_id: str, original_filename: str) -> Path:
    """infra/storage/documents/<owner_id>/<Document_ID>_<safe_filename>.

    owner_id is the Claim_ID for an ordinary claim document, or the
    Customer_ID for a claim-independent identity document imported via
    services/document_import.py - either way it is server-generated/
    validated already, but it is re-sanitized here too as defense in depth.
    """
    safe_owner_id = _UNSAFE_CHARS.sub("_", owner_id) or "unknown-owner"
    safe_document_id = _UNSAFE_CHARS.sub("_", document_id) or "unknown-document"
    safe_name = sanitize_filename(original_filename)
    root = Path(settings.DOCUMENT_STORAGE_ROOT).resolve()
    directory = root / safe_owner_id
    path = (directory / f"{safe_document_id}_{safe_name}").resolve()

    # Belt-and-braces: confirm the resolved path never escapes the storage
    # root, even if some future change to the sanitizers above regresses.
    if root not in path.parents:
        raise ValueError("Resolved storage path escapes the document storage root")
    return path


def save_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def delete_file(path: Path) -> None:
    """Best-effort cleanup used on rollback - never raises, since a
    failure here must not mask the original error being handled."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
