
"""Atomic audit-trail saving for StampZ-III.

Coordinates saving individual measurements and averages
across two SQLite databases.

Every successful manual save will create an independent
analytical snapshot. Existing records must not be modified.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from copy import deepcopy
from math import isfinite

from utils.audit_dataid import (
    initialize_audit_sequences,
    allocate_audit_dataid,
)

def execute_audit_transaction(
    audit_db_path,
    operation,
    individual_db_path=None,
    average_db_path=None,
):
    """Coordinate an audit save with the selected measurement DBs.

    main       = permanent AUDIT database
    individual = optional individual measurements
    avg        = optional averaged measurements
    """
    import os

    from utils.audit_database import initialize_audit_database

    if not individual_db_path and not average_db_path:
        raise ValueError("Select individual measurements, averages, or both")

    paths = [
        path for path in
        (audit_db_path, individual_db_path, average_db_path)
        if path is not None
    ]

    if len(set(map(os.path.abspath, paths))) != len(paths):
        raise ValueError("Audit and measurement database paths must differ")

    # Create only the directories required by this operation.
    for path in paths:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    conn = sqlite3.connect(audit_db_path)

    try:
        if individual_db_path:
            conn.execute(
                "ATTACH DATABASE ? AS individual",
                (individual_db_path,),
            )

        if average_db_path:
            conn.execute(
                "ATTACH DATABASE ? AS avg",
                (average_db_path,),
            )

        # SQLite rollback journals permit coordinated commits
        # across attached file-based databases.
        for row in conn.execute("PRAGMA database_list"):
            schema = row[1]
            mode = conn.execute(
                f"PRAGMA {schema}.journal_mode=DELETE"
            ).fetchone()[0]

            if mode.lower() != "delete":
                raise RuntimeError(
                    f"Unexpected journal mode: {schema}={mode}"
                )

        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")

        initialize_audit_database(conn)

        result = operation(conn)

        conn.commit()
        return result

    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise

    finally:
        conn.close()


def new_analysis_id():
    """Generate a unique identity for one SAVE operation."""
    return str(uuid.uuid4())

def audit_timestamp():
    """Return an unambiguous UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()

def allocate_shared_dataid(conn, original_dataid):
    """Allocate one DataID using the permanent AUDIT database.

    The audit database is main. Optional measurement databases
    are attached as individual and/or avg.
    """
    if not conn.in_transaction:
        raise RuntimeError("Audit allocation requires a transaction")

    return allocate_audit_dataid(conn, original_dataid)



def create_analytical_snapshot(
    ink_samples,
    ink_average,
    paper_samples=None,
    paper_average=None,
    metadata=None,
):
    """Freeze one user-approved Results analysis.

    All supplied samples must already be enabled and analyzed.
    Average values must come directly from Results.

    No sampling, calibration, averaging, or outlier filtering
    is performed here.
    """

    def validate_triplet(values, label):
        if not isinstance(values, (tuple, list)) or len(values) != 3:
            raise ValueError(f"{label} must contain three values")

        result = tuple(float(v) for v in values)

        if not all(isfinite(v) for v in result):
            raise ValueError(f"{label} contains invalid values")

        return result

    def freeze_samples(samples, group):
        frozen = []
        seen_indices = set()

        for sample in samples:
            index = int(sample["index"])

            if index < 1 or index in seen_indices:
                raise ValueError(
                    f"Invalid or duplicate marker index: {index}"
                )

            seen_indices.add(index)

            frozen.append({
                "index": index,
                "group": group,
                "rgb": validate_triplet(
                    sample["rgb"], f"Marker {index} RGB"
                ),
                "lab": validate_triplet(
                    sample["lab"], f"Marker {index} Lab"
                ),
                "position": tuple(sample["position"]),
                "type": sample["type"],
                "size": tuple(sample["size"]),
                "anchor": sample["anchor"],
                "rgb_stddev": deepcopy(
                    sample.get("rgb_stddev")
                ),
                "lab_stddev": deepcopy(
                    sample.get("lab_stddev")
                ),
            })

        return frozen

    def freeze_average(average, group):
        if average is None:
            return None

        return {
            "group": group,
            "rgb": validate_triplet(
                average["rgb"], f"{group} average RGB"
            ),
            "lab": validate_triplet(
                average["lab"], f"{group} average Lab"
            ),
        }

    ink = freeze_samples(ink_samples, "ink")
    paper = freeze_samples(paper_samples or [], "paper")

    all_indices = [s["index"] for s in ink + paper]
    if len(all_indices) != len(set(all_indices)):
        raise ValueError("Marker appears in both ink and paper groups")

    ink_avg = freeze_average(ink_average, "ink")
    paper_avg = freeze_average(paper_average, "paper")

    if bool(ink) != bool(ink_avg):
        raise ValueError("Ink samples and average must agree")

    if bool(paper) != bool(paper_avg):
        raise ValueError("Paper samples and average must agree")

    if not ink and not paper:
        raise ValueError("No enabled samples to save")

    return {
        "analysis_id": new_analysis_id(),
        "saved_at_utc": audit_timestamp(),
        "ink_samples": ink,
        "ink_average": ink_avg,
        "paper_samples": paper,
        "paper_average": paper_avg,
        "metadata": deepcopy(metadata or {}),
    }


def initialize_audit_records(conn, schema="main"):
    """Create the permanent audit-record table if it does not exist."""
    if schema not in ("main", "avg"):
        raise ValueError(f"Invalid database schema: {schema}")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.audit_records (
            analysis_id TEXT PRIMARY KEY,
            dataid TEXT NOT NULL,
            saved_at_utc TEXT NOT NULL,
            snapshot_json TEXT NOT NULL
        )
    """)

def _audit_json_default(value):
    """Convert NumPy values to standard JSON-compatible Python types."""
    import numpy as np

    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)

    raise TypeError(
        f"Unsupported audit JSON type: {type(value).__name__}"
    )


def insert_audit_record(conn, snapshot, dataid, schema="main"):
    """Insert one immutable analytical audit record."""
    import json

    if schema not in ("main", "avg"):
        raise ValueError(f"Invalid database schema: {schema}")

    if not conn.in_transaction:
        raise RuntimeError("Audit insertion requires a transaction")

    initialize_audit_records(conn, schema)

    conn.execute(
        f"""
        INSERT INTO {schema}.audit_records (
            analysis_id, dataid, saved_at_utc, snapshot_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            snapshot["analysis_id"],
            dataid,
            snapshot["saved_at_utc"],
            json.dumps(snapshot, sort_keys=True, allow_nan=False,
                       default=_audit_json_default),
        ),
    )


def insert_audit_individual_samples(conn, set_id, samples, schema="individual"):
    """Insert original analytical samples without replacing existing rows."""
    if schema not in ("individual", "avg"):
        raise ValueError(f"Invalid database schema: {schema}")

    if not conn.in_transaction:
        raise RuntimeError("Individual audit insertion requires a transaction")

    count = 0

    for sample in samples:
        rgb = sample["rgb"]
        lab = sample["lab"]
        position = sample["position"]
        size = sample["size"]
        rgb_sd = sample.get("rgb_stddev") or (None, None, None)
        lab_sd = sample.get("lab_stddev") or (None, None, None)

        conn.execute(
            f"""
            INSERT INTO {schema}.color_measurements (
                set_id, coordinate_point, x_position, y_position,
                l_value, a_value, b_value,
                rgb_r, rgb_g, rgb_b,
                sample_type, sample_size, sample_anchor, notes,
                rgb_r_stddev, rgb_g_stddev, rgb_b_stddev,
                lab_l_stddev, lab_a_stddev, lab_b_stddev
            ) VALUES ({",".join(["?"] * 20)})
            """,
            (
                set_id, sample["index"], position[0], position[1],
                lab[0], lab[1], lab[2],
                rgb[0], rgb[1], rgb[2],
                sample["type"], f"{size[0]}x{size[1]}",
                sample["anchor"], "Audit analytical sample",
                rgb_sd[0], rgb_sd[1], rgb_sd[2],
                lab_sd[0], lab_sd[1], lab_sd[2],
            ),
        )
        count += 1

    return count

def insert_audit_average(conn, set_id, average, samples, schema="avg"):
    """Insert a frozen analytical average without recalculating it."""
    if schema not in ("main", "avg"):
        raise ValueError(f"Invalid database schema: {schema}")

    if not conn.in_transaction:
        raise RuntimeError("Audit average insertion requires a transaction")

    if not samples or average is None:
        raise ValueError("An average requires contributing samples")

    rgb = average["rgb"]
    lab = average["lab"]

    avg_x = sum(s["position"][0] for s in samples) / len(samples)
    avg_y = sum(s["position"][1] for s in samples) / len(samples)

    marker_ids = ",".join(str(s["index"]) for s in samples)

    types = {s["type"] for s in samples}
    sizes = {tuple(s["size"]) for s in samples}
    anchors = {s["anchor"] for s in samples}

    sample_type = next(iter(types)) if len(types) == 1 else "various"
    sample_size = (
        f"{next(iter(sizes))[0]}x{next(iter(sizes))[1]}"
        if len(sizes) == 1 else "various"
    )
    sample_anchor = (
        next(iter(anchors)) if len(anchors) == 1 else "various"
    )

    conn.execute(
        f"""
        INSERT INTO {schema}.color_measurements (
            set_id, coordinate_point, x_position, y_position,
            l_value, a_value, b_value,
            rgb_r, rgb_g, rgb_b,
            sample_type, sample_size, sample_anchor, notes,
            is_averaged, source_samples_count, source_sample_ids
        ) VALUES ({",".join(["?"] * 17)})
        """,
        (
            set_id, 999, avg_x, avg_y,
            lab[0], lab[1], lab[2],
            rgb[0], rgb[1], rgb[2],
            sample_type, sample_size, sample_anchor,
            f"Audit {average['group']} average",
            1, len(samples), marker_ids,
        ),
    )

    return 1


def create_audit_measurement_set(
    conn, dataid, analysis_id, saved_at_utc, schema="individual"
):
    """Create a new measurement set without reusing an existing one."""
    if schema not in ("individual", "avg"):
        raise ValueError(f"Invalid database schema: {schema}")

    if not conn.in_transaction:
        raise RuntimeError("Audit set creation requires a transaction")

    cursor = conn.execute(
        f"""
        INSERT INTO {schema}.measurement_sets (
            image_name, measurement_date, description
        ) VALUES (?, ?, ?)
        """,
        (
            dataid,
            saved_at_utc,
            f"Audit analysis_id={analysis_id}",
        ),
    )

    return cursor.lastrowid



def save_complete_audit(
    audit_db_path,
    original_dataid,
    snapshot,
    individual_db_path=None,
    average_db_path=None,
):
    """Save permanent audit history and selected measurements atomically."""
    from utils.audit_database import insert_permanent_audit
    from utils.audit_measurement_schema import (
        prepare_individual_schema,
        prepare_average_schema,
    )

    if not individual_db_path and not average_db_path:
        raise ValueError("No conventional measurement database selected")

    if not original_dataid:
        raise ValueError("Original DataID is required")

    def operation(conn):
        # Prepare only the requested conventional databases.
        if individual_db_path:
            prepare_individual_schema(conn)

        if average_db_path:
            prepare_average_schema(conn)

        # Allocate one identifier for this entire analytical save.
        dataid = allocate_shared_dataid(conn, original_dataid)

        # Always preserve the complete frozen snapshot.
        insert_permanent_audit(
            conn,
            snapshot,
            original_dataid=original_dataid,
            dataid=dataid,
        )

        results = {
            "analysis_id": snapshot["analysis_id"],
            "original_dataid": original_dataid,
            "dataid": dataid,
            "individual_count": 0,
            "average_count": 0,
        }

        for group in ("ink", "paper"):
            samples = snapshot[f"{group}_samples"]
            average = snapshot[f"{group}_average"]

            if not samples:
                continue

            if average is None:
                raise ValueError(f"Missing {group} average")

            if group == "paper":
                if dataid.endswith("-p"):
                    group_dataid = dataid
                else:
                    group_dataid = f"{dataid}-p"
            else:
                group_dataid = dataid

            if individual_db_path:
                set_id = create_audit_measurement_set(
                    conn,
                    group_dataid,
                    snapshot["analysis_id"],
                    snapshot["saved_at_utc"],
                    schema="individual",
                )

                results["individual_count"] += (
                    insert_audit_individual_samples(
                        conn, set_id, samples,
                        schema="individual",
                    )
                )

            if average_db_path:
                set_id = create_audit_measurement_set(
                    conn,
                    group_dataid,
                    snapshot["analysis_id"],
                    snapshot["saved_at_utc"],
                    schema="avg",
                )

                results["average_count"] += insert_audit_average(
                    conn, set_id, average, samples,
                    schema="avg",
                )

        return results

    return execute_audit_transaction(
        audit_db_path=audit_db_path,
        operation=operation,
        individual_db_path=individual_db_path,
        average_db_path=average_db_path,
    )
