"""Read-only audit reporting for StampZ-III.

Retrieve permanent analytical audit records without modifying
their source databases or recalculating stored measurements.
"""

import json
import sqlite3
from pathlib import Path


def _open_audit_readonly(database_path):
    """Open an existing audit database in SQLite read-only mode."""
    path = Path(database_path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Audit database not found: {path}")

    uri = path.as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)

    # Additional protection against database writes.
    conn.execute("PRAGMA query_only=ON")

    return conn


def list_audit_records(database_path):
    """Return audit record identifiers, newest first."""
    with _open_audit_readonly(database_path) as conn:
        rows = conn.execute("""
            SELECT dataid, original_dataid,
                   analysis_id, saved_at_utc
            FROM audit_records
            ORDER BY saved_at_utc DESC, dataid
        """).fetchall()

    return [
        {
            "dataid": row[0],
            "original_dataid": row[1],
            "analysis_id": row[2],
            "saved_at_utc": row[3],
        }
        for row in rows
    ]


def get_audit_record(database_path, dataid):
    """Retrieve one existing audit record by its assigned DataID."""
    with _open_audit_readonly(database_path) as conn:
        row = conn.execute("""
            SELECT analysis_id, original_dataid,
                   dataid, saved_at_utc, snapshot_json
            FROM audit_records
            WHERE dataid = ?
        """, (dataid,)).fetchone()

    if row is None:
        return None

    return {
        "analysis_id": row[0],
        "original_dataid": row[1],
        "dataid": row[2],
        "saved_at_utc": row[3],
        "snapshot": json.loads(row[4]),
    }
def export_audit_txt(database_path, output_path, dataid=None):
    """Export stored audit information to a human-readable TXT file.

    If dataid is supplied, export one record.
    Otherwise, export all audit records in the database.

    The source database is always opened read-only.
    """
    from datetime import datetime, timezone

    database_path = Path(database_path)
    output_path = Path(output_path).expanduser()

    if dataid is not None:
        record = get_audit_record(database_path, dataid)
        if record is None:
            raise ValueError(f"DataID not found: {dataid}")
        records = [record]
    else:
        records = [
            get_audit_record(database_path, entry["dataid"])
            for entry in list_audit_records(database_path)
        ]

    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "StampZ-III Audit Report",
        "=" * 60,
        f"Database: {database_path.name}",
        f"Report type: {'Individual' if dataid is not None else 'Complete database'}",
        f"Report generated (UTC): {generated_at}",
        f"Records: {len(records)}",
        "",
    ]

    for record in records:
        lines.extend([
            "-" * 60,
            f"DataID: {record['dataid']}",
            f"Original DataID: {record['original_dataid']}",
            f"Analysis UUID: {record['analysis_id']}",
            f"Original save (UTC): {record['saved_at_utc']}",
            "Audit status: Full audit available",
            "",
            "ORIGINAL ANALYTICAL SNAPSHOT",
            json.dumps(
                record["snapshot"],
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            ),
            "",
        ])

    lines.extend([
        "=" * 60,
        "End of Audit Report",
        "This file is an export. The original audit database",
        "remains the authoritative record.",
        "",
    ])

    # Refuse to overwrite an existing report.
    # The Save dialog can propose another filename.
    with output_path.open("x", encoding="utf-8") as report:
        report.write("\n".join(lines))

    return output_path