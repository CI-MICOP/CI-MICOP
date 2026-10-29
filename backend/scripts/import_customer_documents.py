"""CI-MICOP development data-import script.

Attaches existing RC / Driving Licence / Insurance Policy files to
existing customer (and, where applicable, vehicle/policy) records, from a
CSV manifest - see docs/project_documentation (or the final report for
this task) for the manifest format.

This is a controlled, operator-run script - there is no web upload page
or API endpoint for this, deliberately, so it is never reachable from a
browser or a customer/surveyor/officer session. Run it only with direct
access to the backend environment and database.

Usage (always dry-run unless --apply is given - dry-run makes no changes
to the database or to storage):

    python scripts/import_customer_documents.py --manifest manifest.csv --documents-dir ./incoming
    python scripts/import_customer_documents.py --manifest manifest.csv --documents-dir ./incoming --apply

Manifest CSV columns (header row required):
    customer_id        required  an existing Customer_ID
    document_type       required  one of: RC, Driving Licence, Insurance Policy
    filename            required  file name inside --documents-dir
    vehicle_id          required for RC; ignored otherwise
    policy_id           required for Insurance Policy; ignored otherwise
    expiry_date         optional, YYYY-MM-DD
    issuer_reference    optional free text (e.g. "RTA Chennai")
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app as _app  # noqa: E402,F401  (side effect: registers every SQLAlchemy model)
from app.db.session import SessionLocal  # noqa: E402
from app.services import document_import  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, type=Path, help="Path to the manifest CSV file")
    parser.add_argument("--documents-dir", required=True, type=Path, help="Directory containing the source files")
    parser.add_argument(
        "--imported-by",
        default=None,
        help="User_ID of the operator running this import, recorded on every row it creates",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the database and storage. Without this flag, the script only reports what it would do.",
    )
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    if not args.documents_dir.is_dir():
        print(f"Documents directory not found: {args.documents_dir}", file=sys.stderr)
        return 2

    with args.manifest.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    rows = document_import.parse_manifest_rows(csv_rows)

    dry_run = not args.apply
    mode = "DRY RUN (no changes will be made)" if dry_run else "APPLY (writing to the database and storage)"
    print(f"CI-MICOP document import - {mode}")
    print(f"Manifest: {args.manifest}  Documents: {args.documents_dir}")
    print("-" * 70)

    db = SessionLocal()
    try:
        report = document_import.run_import(db, rows, args.documents_dir, args.imported_by, dry_run)
    finally:
        db.close()

    for result in report.results:
        row = result.row
        print(
            f"line {row.line_number}: {row.customer_id} / {row.document_type} / {row.filename} "
            f"-> {result.outcome} ({result.message})"
            + (f" [Document_ID={result.document_id}]" if result.document_id else "")
        )

    counts = report.counts
    print("-" * 70)
    print(
        f"Total: {len(report.results)}  "
        f"Imported/would-import: {counts[document_import.IMPORTED] + counts[document_import.WOULD_IMPORT]}  "
        f"Already present: {counts[document_import.SKIPPED_DUPLICATE]}  "
        f"Invalid: {counts[document_import.INVALID]}"
    )
    if dry_run:
        print("No changes were made (dry run). Re-run with --apply to import.")

    return 1 if counts[document_import.INVALID] else 0


if __name__ == "__main__":
    raise SystemExit(main())
