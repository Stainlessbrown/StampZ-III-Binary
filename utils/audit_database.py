"""Permanent analytical audit storage for StampZ-III.

Audit records are append-only. Database creation and transactions
are controlled by the save coordinator.
"""

import os
import re
import sys


def audit_database_path(collection_name):
    """Return the audit database path without creating any files."""
    from utils.naming_utils import standardize_name

    name = standardize_name(collection_name)

    if not name:
        raise ValueError("Database collection name cannot be empty")

    # Match ColorAnalysisDB's filename cleanup.
    name = re.sub(r'[^\w\-_\.]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')

    if not name:
        raise ValueError("Invalid database collection name")

    data_dir = os.getenv("STAMPZ_DATA_DIR")

    if data_dir:
        directory = os.path.join(
            data_dir, "data", "color_analysis"
        )
    elif getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        directory = os.path.expanduser(
            "~/Library/Application Support/StampZ-III/"
            "data/color_analysis"
        )
    else:
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        directory = os.path.join(
            project_root, "data", "color_analysis"
        )

    return os.path.join(directory, f"{name}_AUDIT.db")


def initialize_audit_database(conn, schema="main"):
    """Create audit tables and immutability safeguards.

    The caller owns the SQLite connection and transaction.
    No commit is performed here.
    """
    if schema not in ("main", "audit"):
        raise ValueError("Invalid audit schema")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.audit_records (
            analysis_id TEXT PRIMARY KEY,
            original_dataid TEXT NOT NULL,
            dataid TEXT NOT NULL UNIQUE,
            saved_at_utc TEXT NOT NULL,
            snapshot_json TEXT NOT NULL
        )
    """)

    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {schema}.idx_audit_family
        ON audit_records(original_dataid)
    """)

    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {schema}.idx_audit_timestamp
        ON audit_records(saved_at_utc)
    """)

    conn.execute(f"""
        CREATE TRIGGER IF NOT EXISTS {schema}.audit_no_update
        BEFORE UPDATE ON audit_records
        BEGIN
            SELECT RAISE(ABORT,
                'Permanent audit records cannot be updated');
        END
    """)

    conn.execute(f"""
        CREATE TRIGGER IF NOT EXISTS {schema}.audit_no_delete
        BEFORE DELETE ON audit_records
        BEGIN
            SELECT RAISE(ABORT,
                'Permanent audit records cannot be deleted');
        END
    """)


def insert_permanent_audit(
    conn, snapshot, original_dataid, dataid, schema="main"
):
    """Insert one complete analytical snapshot."""
    import json
    from utils.audit_save_coordinator import _audit_json_default

    if schema not in ("main", "audit"):
        raise ValueError("Invalid audit schema")

    if not conn.in_transaction:
        raise RuntimeError("Audit insertion requires a transaction")

    if not original_dataid or not dataid:
        raise ValueError("Audit DataIDs cannot be empty")

    payload = json.dumps(
        snapshot,
        sort_keys=True,
        allow_nan=False,
        default=_audit_json_default,
    )

    conn.execute(
        f"""
        INSERT INTO {schema}.audit_records (
            analysis_id,
            original_dataid,
            dataid,
            saved_at_utc,
            snapshot_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            snapshot["analysis_id"],
            original_dataid,
            dataid,
            snapshot["saved_at_utc"],
            payload,
        ),
    )
