
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
    individual_db_path,
    average_db_path,
    operation,
):
    """Execute an operation within a shared SQLite transaction.

    operation(conn) receives an open connection with:
        main = individual database
        avg  = averaged database

    On success, commit all changes.
    On failure, roll back all changes.
    """
    if individual_db_path == average_db_path:
        raise ValueError("Individual and AVG databases must differ")

    conn = sqlite3.connect(individual_db_path)

    try:
        conn.execute(
            "ATTACH DATABASE ? AS avg",
            (average_db_path,),
        )

        # Configure rollback journals before beginning transaction.
        for schema in ("main", "avg"):
            mode = conn.execute(
                f"PRAGMA {schema}.journal_mode=DELETE"
            ).fetchone()[0]

            if mode.lower() != "delete":
                raise RuntimeError(
                    f"Unexpected journal mode for {schema}: {mode}"
                )

        conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("BEGIN IMMEDIATE")

        result = operation(conn)

        conn.execute("COMMIT")
        return result

    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
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
    """Allocate one DataID across individual and AVG databases.

    Must be called inside an active transaction.
    The returned sequence belongs to the whole SAVE operation.
    """
    if not conn.in_transaction:
        raise RuntimeError("Audit allocation requires a transaction")

    # Read every existing DataID from both databases.
    # Database errors must propagate, never be treated as empty data.
    individual_names = [
        row[0] for row in conn.execute(
            "SELECT image_name FROM main.measurement_sets"
        )
    ]

    average_names = [
        row[0] for row in conn.execute(
            "SELECT image_name FROM avg.measurement_sets"
        )
    ]

    # Initialize or advance the persistent counter.
    initialize_audit_sequences(
        conn, individual_names + average_names
    )

    # Allocate once for the entire analysis.
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
            json.dumps(snapshot, sort_keys=True, allow_nan=False),
        ),
    )


