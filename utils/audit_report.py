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
    """Export complete audit records as readable TXT.

    Presentation uses three decimals for floating-point numbers.
    Stored database values are never altered or recalculated.
    """
    from datetime import datetime, timezone

    database_path = Path(database_path)
    output_path = Path(output_path).expanduser()

    def label_for(key):
        """Use familiar labels while retaining unknown field names."""
        labels = {
            "rgb": "RGB",
            "lab": "Lab",
            "rgb_stddev": "RGB standard deviation",
            "lab_stddev": "Lab standard deviation",
            "source_sha256": "Source SHA-256",
            "source_image": "Source image",
            "analysis_id": "Analysis UUID",
            "saved_at_utc": "Saved (UTC)",
            "stampz_version": "StampZ version",
            "sampling_bit_depth": "Sampling bit depth",
            "sampling_channels": "Sampling channels",
            "os_version": "OS version",
        }
        return labels.get(key, key.replace("_", " ").capitalize())

    def format_value(value):
        """Format scalar values without altering their source."""
        if value is None:
            return "Not recorded"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:.3f}"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            return value.replace("\r", "\\r").replace("\n", "\\n")
        return str(value)

    def format_sequence(values, key):
        """Present scalar sequences without JSON punctuation."""
        if not values:
            return "(empty)"

        formatted = [format_value(v) for v in values]

        if key == "lab" and len(values) == 3:
            return (
                f"L*={formatted[0]}  "
                f"a*={formatted[1]}  "
                f"b*={formatted[2]}"
            )

        if key == "rgb" and len(values) == 3:
            return (
                f"R={formatted[0]}  "
                f"G={formatted[1]}  "
                f"B={formatted[2]}"
            )

        if key in ("position", "size") and len(values) == 2:
            return f"{formatted[0]}, {formatted[1]}"

        return ", ".join(formatted)

    def format_fields(data, indent=0):
        """Recursively present every stored field, including new ones."""
        result = []
        prefix = " " * indent

        for key, value in data.items():
            label = label_for(key)

            if isinstance(value, dict):
                result.append(f"{prefix}{label}:")
                if value:
                    result.extend(format_fields(value, indent + 2))
                else:
                    result.append(f"{prefix}  (empty)")

            elif isinstance(value, (list, tuple)):
                if all(
                    not isinstance(item, (dict, list, tuple))
                    for item in value
                ):
                    result.append(
                        f"{prefix}{label}: "
                        f"{format_sequence(value, key)}"
                    )
                else:
                    result.append(f"{prefix}{label}:")
                    for index, item in enumerate(value, 1):
                        result.append(f"{prefix}  Entry {index}:")
                        if isinstance(item, dict):
                            result.extend(
                                format_fields(item, indent + 4)
                            )
                        elif isinstance(item, (list, tuple)):
                            result.append(
                                f"{prefix}    "
                                f"{format_sequence(item, key)}"
                            )
                        else:
                            result.append(
                                f"{prefix}    {format_value(item)}"
                            )

                    if not value:
                        result.append(f"{prefix}  (empty)")

            else:
                result.append(
                    f"{prefix}{label}: {format_value(value)}"
                )

        return result

    def section(lines, heading, data):
        """Append one clearly separated report section."""
        lines.extend([
            "",
            heading,
            "-" * 50,
        ])
        if data is None:
            lines.append("Not recorded")
        elif isinstance(data, dict):
            lines.extend(format_fields(data, 2))
        else:
            lines.append(format_value(data))

    # Retrieve records exclusively through our read-only functions.
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
        "STAMPZ-III AUDIT REPORT",
        "=" * 60,
        f"Database: {database_path.name}",
        f"Report type: {'Individual' if dataid is not None else 'Complete database'}",
        f"Generated (UTC): {generated_at}",
        f"Records: {len(records)}",
        "Analytical values displayed to three decimal places.",
        "Permanent records retain their original precision.",
        "",
    ]

    # Index for large database reports.
    if dataid is None:
        lines.extend([
            "REPORT INDEX",
            "-" * 50,
        ])
        for index, record in enumerate(records, 1):
            lines.append(f"{index:4}. {record['dataid']}")
        lines.append("")

    for index, record in enumerate(records, 1):
        snapshot = record["snapshot"]

        lines.extend([
            "=" * 60,
            f"ANALYSIS {index} OF {len(records)}",
            "=" * 60,
            f"DataID: {record['dataid']}",
            f"Original DataID: {record['original_dataid']}",
            f"Analysis UUID: {record['analysis_id']}",
            f"Original save (UTC): {record['saved_at_utc']}",
            "Audit status: Full audit available",
        ])

        section(
            lines, "SOURCE AND PROVENANCE",
            snapshot.get("metadata")
        )

        for group in ("ink", "paper"):
            samples_key = f"{group}_samples"
            average_key = f"{group}_average"

            samples = snapshot.get(samples_key, [])
            lines.extend([
                "",
                f"{group.upper()} MEASUREMENTS ({len(samples)})",
                "-" * 50,
            ])

            if not samples:
                lines.append("No samples recorded")

            for number, sample in enumerate(samples, 1):
                lines.append(f"  Marker {number}")
                lines.extend(format_fields(sample, 4))
                lines.append("")

            section(
                lines,
                f"{group.upper()} AVERAGE",
                snapshot.get(average_key),
            )

        # Retain every additional snapshot field, including
        # fields introduced by future StampZ versions.
        known = {
            "metadata", "ink_samples", "ink_average",
            "paper_samples", "paper_average",
        }
        additional = {
            key: value
            for key, value in snapshot.items()
            if key not in known
        }

        if additional:
            section(lines, "ADDITIONAL SNAPSHOT FIELDS", additional)

        lines.append("")

    lines.extend([
        "=" * 60,
        "END OF AUDIT REPORT",
        "This report is an export of stored analytical data.",
        "The permanent audit database remains authoritative.",
        "",
    ])

    # Never overwrite an existing exported report.
    with output_path.open("x", encoding="utf-8") as report:
        report.write("\n".join(lines))

    return output_path
