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


def export_audit_csv_legacy(database_path, output_path, dataid=None):
    """Export complete audit snapshots to CSV without database writes.

    Each measurement and average has a separate row.
    Other snapshot fields are recorded as metadata rows.
    """
    import csv
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

    def display(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    def flatten(value, prefix=""):
        """Yield every scalar with its complete field path."""
        if isinstance(value, dict):
            if not value:
                yield prefix, "(empty dictionary)"
            for key, item in value.items():
                path = f"{prefix}.{key}" if prefix else key
                yield from flatten(item, path)
        elif isinstance(value, (list, tuple)):
            if not value:
                yield prefix, "(empty list)"
            for index, item in enumerate(value):
                yield from flatten(item, f"{prefix}[{index}]")
        else:
            yield prefix, display(value)

    columns = [
        "RowType", "Database", "DataID", "OriginalDataID",
        "AnalysisUUID", "SavedUTC", "Group", "Marker",
        "L", "a", "b", "R", "G", "B",
        "Field", "Value",
    ]

    generated_at = datetime.now(timezone.utc).isoformat()

    # Exclusive creation protects previously exported reports.
    with output_path.open("x", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)

        # Simple report header.
        writer.writerow(["StampZ-III Audit Report"])
        writer.writerow(["Database", database_path.name])
        writer.writerow([
            "ReportType",
            "Individual" if dataid is not None else "Complete database",
        ])
        if dataid is not None:
            writer.writerow(["DataID", dataid])
            writer.writerow(["OriginalSaveUTC", records[0]["saved_at_utc"]])
        writer.writerow(["GeneratedUTC", generated_at])
        writer.writerow(["RecordCount", len(records)])
        writer.writerow(["Precision", "Floating-point values displayed to 3 decimals"])
        writer.writerow([])
        writer.writerow(columns)

        for record in records:
            snapshot = record["snapshot"]

            common = [
                database_path.name,
                record["dataid"],
                record["original_dataid"],
                record["analysis_id"],
                record["saved_at_utc"],
            ]

            for group in ("ink", "paper"):
                for kind, items in (
                    ("SAMPLE", snapshot.get(f"{group}_samples", [])),
                    ("AVERAGE", [snapshot.get(f"{group}_average")]),
                ):
                    for sample in items:
                        if sample is None:
                            continue

                        lab = sample.get("lab") or [None] * 3
                        rgb = sample.get("rgb") or [None] * 3

                        marker = (
                            sample.get("index", "")
                            if kind == "SAMPLE" else ""
                        )

                        writer.writerow([
                            kind, *common, group, marker,
                            *[display(v) for v in lab],
                            *[display(v) for v in rgb],
                            "", "",
                        ])

            # Include every additional field without discarding nested data.
            # Sample-level geometry, deviation, and future fields are
            # included here as well as the analytical rows above.
            for path, value in flatten(snapshot):
                writer.writerow([
                    "SNAPSHOT_FIELD", *common,
                    "", "", "", "", "", "", "", "",
                    path, value,
                ])

    return output_path


def get_database_measurements(database_path, dataid=None, set_id=None):
    """Read measurements from one selected StampZ database.

    Reads only the selected database. Does not calculate,
    modify, or retrieve measurements from companion databases.
    """
    database_path = Path(database_path).expanduser().resolve()

    if database_path.stem.endswith("_AUDIT"):
        raise ValueError(
            "Select an individual or AVG measurement database"
        )

    database_type = (
        "AVG" if database_path.stem.endswith("_AVG")
        else "INDIVIDUAL"
    )

    with _open_audit_readonly(database_path) as conn:
        query = """
            SELECT
                s.set_id,
                s.image_name,
                s.measurement_date AS set_date,
                s.description,
                m.*
            FROM measurement_sets AS s
            JOIN color_measurements AS m
                ON m.set_id = s.set_id
        """

        if dataid is not None and set_id is not None:
            raise ValueError(
                "Specify either DataID or set_id, not both"
            )

        parameters = ()

        if set_id is not None:
            query += " WHERE s.set_id = ?"
            parameters = (set_id,)
        elif dataid is not None:
            query += " WHERE s.image_name = ?"
            parameters = (dataid,)

        query += " ORDER BY s.set_id, m.id"

        cursor = conn.execute(query, parameters)
        columns = [item[0] for item in cursor.description]

        measurements = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    return {
        "database": database_path.name,
        "database_type": database_type,
        "measurements": measurements,
    }


def get_measurement_provenance(database_path, measurement):
    """Find the permanent audit snapshot for a saved measurement.

    Matches by analysis UUID only. Never modifies databases
    or guesses provenance from matching DataIDs.
    """
    import re

    database_path = Path(database_path).expanduser().resolve()

    description = measurement.get("description") or ""

    match = re.search(
        r"Audit analysis_id=([0-9a-fA-F-]{36})",
        description,
    )

    if not match:
        return {
            "status": "No audit history available",
            "snapshot": None,
        }

    analysis_id = match.group(1)

    # Individual and AVG databases share one audit archive.
    collection = database_path.stem

    if collection.endswith("_AVG"):
        collection = collection[:-4]

    audit_path = database_path.with_name(
        f"{collection}_AUDIT.db"
    )

    if not audit_path.is_file():
        return {
            "status": "No audit history available",
            "snapshot": None,
        }

    with _open_audit_readonly(audit_path) as conn:
        row = conn.execute("""
            SELECT analysis_id, dataid, original_dataid,
                   saved_at_utc, snapshot_json
            FROM audit_records
            WHERE analysis_id = ?
        """, (analysis_id,)).fetchone()

    if row is None:
        return {
            "status": "No audit history available",
            "snapshot": None,
        }

    return {
        "status": "Full audit available",
        "analysis_id": row[0],
        "dataid": row[1],
        "original_dataid": row[2],
        "saved_at_utc": row[3],
        "snapshot": json.loads(row[4]),
    }


def export_audit_csv(database_path, output_path, dataid=None, set_id=None):
    """Export measurements from one selected database.

    One row per saved measurement, with read-only provenance.
    No recalculation of Lab, RGB, or stored averages.
    """
    import csv
    import re
    from datetime import datetime, timezone

    database_path = Path(database_path).expanduser().resolve()
    output_path = Path(output_path).expanduser()

    result = get_database_measurements(
        database_path,
        dataid=dataid,
        set_id=set_id,
    )

    measurements = result["measurements"]
    database_type = result["database_type"]

    def fmt(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    def flatten(value, prefix=""):
        """Preserve nested metadata as labeled entries."""
        if isinstance(value, dict):
            if not value:
                yield prefix, "(empty)"
            for key, item in value.items():
                name = f"{prefix}.{key}" if prefix else key
                yield from flatten(item, name)
        elif isinstance(value, (list, tuple)):
            if not value:
                yield prefix, "(empty)"
            for index, item in enumerate(value):
                yield from flatten(item, f"{prefix}[{index}]")
        else:
            yield prefix, value

    def summary(data):
        """Create a semicolon-separated, single-cell summary."""
        return "; ".join(
            f"{key}: {fmt(value)}"
            for key, value in flatten(data)
        )

    def parse_size(value):
        if not value:
            return None
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\s*",
            str(value),
            re.IGNORECASE,
        )
        if not match:
            return None
        return float(match.group(1)), float(match.group(2))

    # Average dimensions only within the same saved measurement set.
    sizes_by_set = {}
    for measurement in measurements:
        measurement_set_id = measurement["set_id"]
        sizes_by_set.setdefault(measurement_set_id, []).append(
            measurement.get("sample_size")
        )

    def size_description(measurement):
        if database_type == "AVG":
            return fmt(measurement.get("sample_size"))

        sizes = sizes_by_set[measurement["set_id"]]
        parsed = [parse_size(s) for s in sizes]

        if not parsed or any(s is None for s in parsed):
            return "Not available"

        width = sum(s[0] for s in parsed) / len(parsed)
        height = sum(s[1] for s in parsed) / len(parsed)

        return f"{width:.1f} x {height:.1f} px"

    columns = [
        "Database",
        "DataID",
        "Original DataID",
        "Record Type",
        "Marker",
        "L*",
        "a*",
        "b*",
        "R",
        "G",
        "B",
        "Average Sample Size / Recorded Size",
        "Source Sample Count",
        "Calibration",
        "Image Information",
        "Source Image",
        "SHA-256",
        "Analysis UUID",
        "Saved UTC",
        "Audit Status",
        "Additional Measurement Information",
    ]

    known_measurement_fields = {
        "set_id", "id", "image_name", "set_date",
        "description", "coordinate_point",
        "l_value", "a_value", "b_value",
        "rgb_r", "rgb_g", "rgb_b",
        "sample_size", "source_samples_count",
    }

    # Only export fields belonging to the selected database.
    with output_path.open("x", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(["StampZ-III Audit Report"])
        writer.writerow(["Database", database_path.name])
        writer.writerow(["Database Type", database_type])
        writer.writerow(["Report Generated UTC",
                         datetime.now(timezone.utc).isoformat()])
        writer.writerow(["Records", len(measurements)])
        writer.writerow(["Display Precision", "3 decimal places"])
        writer.writerow([])

        writer.writerow(columns)

        for measurement in measurements:
            provenance = get_measurement_provenance(
                database_path, measurement
            )

            snapshot = provenance.get("snapshot") or {}
            metadata = snapshot.get("metadata") or {}
            image_metadata = metadata.get("image_metadata") or {}

            calibration = metadata.get("calibration") or {}

            image_info = {
                "RAW": image_metadata.get("is_raw"),
                "Format": image_metadata.get("format_info"),
                "Data type": image_metadata.get("data_type"),
                "Original bit depth": image_metadata.get(
                    "original_bit_depth"
                ),
                "Sampling bit depth": metadata.get(
                    "sampling_bit_depth"
                ),
                "Sampling channels": metadata.get(
                    "sampling_channels"
                ),
                "ICC": image_metadata.get("icc_profile_name"),
                "Color profile": image_metadata.get("color_profile"),
                "Gamma corrected": image_metadata.get(
                    "linear_gamma_corrected"
                ),
                "Precision preserved": image_metadata.get(
                    "precision_preserved"
                ),
                "StampZ version": metadata.get("stampz_version"),
                "Operating system": metadata.get("operating_system"),
                "OS version": metadata.get("os_version"),
                "Architecture": metadata.get("architecture"),
            }

            # Include additional source metadata without
            # discarding fields from future versions.
            for key, value in image_metadata.items():
                if key not in {
                    "is_raw", "format_info", "data_type",
                    "original_bit_depth", "icc_profile_name",
                    "color_profile", "linear_gamma_corrected",
                    "precision_preserved",
                }:
                    image_info[key] = value

            additional_metadata = {
                key: value
                for key, value in metadata.items()
                if key not in {
                    "calibration", "image_metadata",
                    "sampling_bit_depth", "sampling_channels",
                    "stampz_version", "operating_system",
                    "os_version", "architecture",
                    "source_image", "source_sha256",
                }
            }
            image_info.update(additional_metadata)

            extra = {
                key: value
                for key, value in measurement.items()
                if key not in known_measurement_fields
            }

            # The selected conventional DB supplies the values.
            # The audit snapshot supplies only verified provenance.
            writer.writerow([
                database_path.name,
                measurement.get("image_name", ""),
                provenance.get("original_dataid", ""),
                database_type,
                measurement.get("coordinate_point", ""),
                fmt(measurement.get("l_value")),
                fmt(measurement.get("a_value")),
                fmt(measurement.get("b_value")),
                fmt(measurement.get("rgb_r")),
                fmt(measurement.get("rgb_g")),
                fmt(measurement.get("rgb_b")),
                size_description(measurement),
                fmt(measurement.get("source_samples_count")),
                summary(calibration) if provenance.get("snapshot") else "",
                summary(image_info) if provenance.get("snapshot") else "",
                metadata.get("source_image", ""),
                metadata.get("source_sha256", ""),
                provenance.get("analysis_id", ""),
                measurement.get("set_date", ""),
                provenance["status"],
                summary(extra),
            ])

    return output_path

def export_database_audit_txt(
    database_path, output_path, dataid=None, set_id=None
):
    """Export one saved measurement set or one complete database.

    The selected database is authoritative for measurements.
    Audit snapshots provide provenance only.
    No database records are modified.
    """
    from datetime import datetime, timezone

    database_path = Path(database_path).expanduser().resolve()
    output_path = Path(output_path).expanduser()

    result = get_database_measurements(
        database_path,
        dataid=dataid,
        set_id=set_id,
    )

    measurements = result["measurements"]
    database_type = result["database_type"]

    if not measurements:
        raise ValueError("No measurements found for the selection")

    def fmt(value):
        if value is None:
            return "Not recorded"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value).replace("\r", "\\r").replace("\n", "\\n")

    def field_lines(data, indent=2):
        lines = []
        for key, value in data.items():
            label = key.replace("_", " ").capitalize()
            if isinstance(value, dict):
                lines.append(" " * indent + f"{label}:")
                lines.extend(field_lines(value, indent + 2))
            elif isinstance(value, (list, tuple)):
                lines.append(
                    " " * indent
                    + f"{label}: "
                    + ", ".join(fmt(v) for v in value)
                )
            else:
                lines.append(
                    " " * indent + f"{label}: {fmt(value)}"
                )
        return lines

    generated = datetime.now(timezone.utc).isoformat()
    single_set = set_id is not None or dataid is not None

    lines = [
        "STAMPZ-III DATABASE AUDIT REPORT",
        "=" * 60,
        f"Database: {database_path.name}",
        f"Database type: {database_type}",
        f"Report type: {'Selected measurement set' if single_set else 'Entire database'}",
        f"Generated (UTC): {generated}",
        f"Measurements: {len(measurements)}",
        "Analytical values displayed to three decimal places.",
        "Stored values retain their original precision.",
        "",
    ]

    # Group measurements by their actual saved set identity.
    sets = {}
    for measurement in measurements:
        sets.setdefault(measurement["set_id"], []).append(measurement)

    lines.append(f"Measurement sets: {len(sets)}")
    if len(sets) == 1:
        first = next(iter(sets.values()))[0]
        provenance = get_measurement_provenance(
            database_path, first
        )

        lines.extend([
            "",
            "=" * 60,
            f"DATAID:        {first['image_name']}",
            f"DATABASE:      {database_path.name}",
            f"ORIGINAL SAVE: {first.get('set_date', 'Not recorded')}",
            f"MEASUREMENTS:  {len(measurements)}",
            f"AUDIT STATUS:  {provenance.get('status', 'No audit history available').upper()}",
            "=" * 60,
        ])

    for index, (saved_set_id, items) in enumerate(sets.items(), 1):
        first = items[0]
        provenance = get_measurement_provenance(
            database_path, first
        )

        lines.extend([
            "",
            "=" * 60,
            f"MEASUREMENT SET {index} OF {len(sets)}",
            "=" * 60,
            f"DataID: {fmt(first.get('image_name'))}",
            f"Internal set ID: {saved_set_id}",
            f"Original save date: {fmt(first.get('set_date'))}",
            f"Measurements in set: {len(items)}",
            f"Audit status: {provenance.get('status', 'No audit history available')}",
        ])

        if provenance.get("analysis_id"):
            lines.append(
                f"Analysis UUID: {provenance['analysis_id']}"
            )

        if provenance.get("original_dataid"):
            lines.append(
                f"Original DataID: {provenance['original_dataid']}"
            )

        if provenance.get("saved_at_utc"):
            lines.append(
                f"Audit save (UTC): {provenance['saved_at_utc']}"
            )

        snapshot = provenance.get("snapshot")

        if snapshot:
            lines.extend([
                "",
                "SOURCE AND PROVENANCE",
                "-" * 50,
            ])
            lines.extend(
                field_lines(snapshot.get("metadata", {}))
            )
        else:
            lines.extend([
                "",
                "SOURCE AND PROVENANCE",
                "-" * 50,
                "No audit history available",
            ])

        lines.extend([
            "",
            f"RECORDED {database_type} MEASUREMENTS",
            "-" * 50,
        ])

        for number, measurement in enumerate(items, 1):
            lines.extend([
                "",
                f"  Measurement {number}",
                f"    Marker: {fmt(measurement.get('coordinate_point'))}",
                f"    Lab: L*={fmt(measurement.get('l_value'))}  "
                f"a*={fmt(measurement.get('a_value'))}  "
                f"b*={fmt(measurement.get('b_value'))}",
                f"    RGB: R={fmt(measurement.get('rgb_r'))}  "
                f"G={fmt(measurement.get('rgb_g'))}  "
                f"B={fmt(measurement.get('rgb_b'))}",
            ])

            # Preserve all additional stored measurement fields.
            excluded = {
                "l_value", "a_value", "b_value",
                "rgb_r", "rgb_g", "rgb_b",
                "coordinate_point",
            }

            additional = {
                key: value
                for key, value in measurement.items()
                if key not in excluded
            }

            lines.extend(field_lines(additional, 4))

    lines.extend([
        "",
        "=" * 60,
        "END OF DATABASE AUDIT REPORT",
        "Measurements were read from the selected database.",
        "Audit provenance is shown only where verified.",
        "No database records were modified.",
        "",
    ])

    # Exclusive creation prevents silent replacement of reports.
    with output_path.open("x", encoding="utf-8") as report:
        report.write("\n".join(lines))

    return output_path