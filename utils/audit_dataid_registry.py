"""Permanent, installation-wide DataID registry for StampZ-III.

The registry is independent of individual measurement databases.
Assigned DataIDs are never recycled.
"""

import os
import sqlite3

from utils.path_utils import get_base_data_dir


def registry_database_path():
    """Return the central registry path without creating files."""
    return os.path.join(
        get_base_data_dir(),
        "StampZ_DataID_Registry.db",
    )

def initialize_registry(conn):
    """Create central registry tables in an existing SQLite transaction.

    The central registry must be attached as 'registry'.
    This function does not commit the transaction.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registry.dataid_sequences (
            original_dataid TEXT PRIMARY KEY,
            highest_number INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS registry.dataid_assignments (
            assigned_dataid TEXT PRIMARY KEY,
            original_dataid TEXT NOT NULL,
            database_name TEXT NOT NULL,
            analysis_id TEXT NOT NULL UNIQUE,
            saved_at_utc TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS registry.idx_assignments_original
        ON dataid_assignments(original_dataid)
    """)

    # Preserve DataIDs found in databases predating the
    # installation-wide registry.
    #
    # A reservation prevents reuse without pretending that
    # older records have verified audit metadata.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registry.historical_reservations (
            dataid TEXT PRIMARY KEY,
            first_database TEXT NOT NULL,
            inventory_at_utc TEXT NOT NULL
        )
    """)

    # Track every historical collection containing a DataID.
    #
    # One DataID may legitimately appear in individual,
    # AVG, and AUDIT companion files. Different collections
    # must also remain distinguishable.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registry.historical_locations (
            dataid TEXT NOT NULL,
            database_name TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            PRIMARY KEY (dataid, database_name, source_kind)
        )
    """)

    # Reserve paper companion DataIDs independently of primary
    # assignments, while retaining their common analysis UUID.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registry.companion_assignments (
            assigned_dataid TEXT PRIMARY KEY,
            primary_dataid TEXT NOT NULL,
            analysis_id TEXT NOT NULL,
            saved_at_utc TEXT NOT NULL
        )
    """)

def allocate_registry_dataid(
    conn, original_dataid, database_name,
    analysis_id, saved_at_utc, needs_paper=False
):
    """Allocate globally unique primary and optional paper DataIDs.

    Both identifiers are checked and registered within the
    caller's existing transaction. This function does not commit.
    """
    from utils.audit_dataid import numbered_dataid, _paper_variant

    if not conn.in_transaction:
        raise RuntimeError("Registry allocation requires a transaction")

    if not isinstance(original_dataid, str) or not original_dataid.strip():
        raise ValueError("Original DataID is required")

    initialize_registry(conn)

    def identifier_exists(identifier):
        """Check every authoritative registry reservation."""
        for table, column in (
            ("dataid_assignments", "assigned_dataid"),
            ("companion_assignments", "assigned_dataid"),
            ("historical_reservations", "dataid"),
        ):
            row = conn.execute(
                f"SELECT 1 FROM registry.{table} "
                f"WHERE {column} = ? LIMIT 1",
                (identifier,),
            ).fetchone()

            if row:
                return True

        return False

    row = conn.execute("""
        SELECT highest_number
        FROM registry.dataid_sequences
        WHERE original_dataid = ?
    """, (original_dataid,)).fetchone()

    number = (row[0] if row else 0) + 1

    while True:
        candidate = numbered_dataid(original_dataid, number)

        paper_candidate = (
            _paper_variant(candidate)
            if needs_paper else None
        )

        primary_collision = identifier_exists(candidate)

        paper_collision = (
            paper_candidate is not None
            and paper_candidate != candidate
            and identifier_exists(paper_candidate)
        )

        if not primary_collision and not paper_collision:
            break

        number += 1

    # Record the primary identifier.
    conn.execute("""
        INSERT INTO registry.dataid_assignments (
            assigned_dataid, original_dataid,
            database_name, analysis_id, saved_at_utc
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        candidate, original_dataid,
        database_name, analysis_id, saved_at_utc
    ))

    # Reserve the paper companion only when required.
    # A paper-only identifier already ending in -p is the
    # primary assignment and must not be registered twice.
    if paper_candidate and paper_candidate != candidate:
        conn.execute("""
            INSERT INTO registry.companion_assignments (
                assigned_dataid, primary_dataid,
                analysis_id, saved_at_utc
            ) VALUES (?, ?, ?, ?)
        """, (
            paper_candidate, candidate,
            analysis_id, saved_at_utc
        ))

    # The sequence counter may advance but never decrease.
    conn.execute("""
        INSERT INTO registry.dataid_sequences (
            original_dataid, highest_number
        ) VALUES (?, ?)
        ON CONFLICT(original_dataid) DO UPDATE SET
            highest_number = MAX(
                dataid_sequences.highest_number,
                excluded.highest_number
            )
    """, (original_dataid, number))

    return candidate

def read_historical_dataids(database_path, source_kind):
    """Read existing DataIDs without modifying the source database."""
    if source_kind == "AUDIT":
        table = "audit_records"
        column = "dataid"
    elif source_kind in ("INDIVIDUAL", "AVG"):
        table = "measurement_sets"
        column = "image_name"
    else:
        raise ValueError(f"Unknown historical source kind: {source_kind}")

    from pathlib import Path

    path = Path(database_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(path)

    # SQLite read-only mode prevents accidental creation or modification.
    uri = path.as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        if table not in tables:
            return []

        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM {table}"
        ).fetchall()

        return sorted(
            dataid for (dataid,) in rows
            if isinstance(dataid, str) and dataid
        )

def inventory_historical_database(
    conn, database_path, database_name, source_kind, inventory_at_utc
):
    """Register historical DataIDs without modifying their source database.

    Requires the central registry to be attached as 'registry'
    and an active SQLite transaction. Does not commit.
    """
    if not conn.in_transaction:
        raise RuntimeError("Historical inventory requires a transaction")

    initialize_registry(conn)

    dataids = read_historical_dataids(database_path, source_kind)

    for dataid in dataids:
        # Reserve the literal identifier. Existing reservations
        # and assignments are never replaced.
        conn.execute("""
            INSERT OR IGNORE INTO registry.historical_reservations (
                dataid, first_database, inventory_at_utc
            ) VALUES (?, ?, ?)
        """, (dataid, database_name, inventory_at_utc))

        # Preserve every collection and companion-file location.
        conn.execute("""
            INSERT OR IGNORE INTO registry.historical_locations (
                dataid, database_name, source_kind
            ) VALUES (?, ?, ?)
        """, (dataid, database_name, source_kind))

    return len(dataids)

def read_attached_historical_dataids(conn, schema, source_kind):
    """Read historical DataIDs through an existing SQLite connection."""

    if schema not in ("main", "individual", "avg"):
        raise ValueError(f"Invalid attached schema: {schema}")

    if source_kind == "AUDIT":
        table, column = "audit_records", "dataid"
    elif source_kind in ("INDIVIDUAL", "AVG"):
        table, column = "measurement_sets", "image_name"
    else:
        raise ValueError(f"Invalid source kind: {source_kind}")

    tables = {
        row[0]
        for row in conn.execute(
            f"SELECT name FROM {schema}.sqlite_master "
            "WHERE type='table'"
        )
    }

    if table not in tables:
        return []

    rows = conn.execute(
        f"SELECT DISTINCT {column} FROM {schema}.{table}"
    ).fetchall()

    return sorted(
        dataid for (dataid,) in rows
        if isinstance(dataid, str) and dataid
    )

def register_historical_dataids(
    conn, dataids, database_name, source_kind, inventory_at_utc
):
    """Register historical identifiers within the caller's transaction.

    Does not commit or modify source measurement databases.
    """
    if not conn.in_transaction:
        raise RuntimeError("Historical registration requires a transaction")

    initialize_registry(conn)

    count = 0

    for dataid in dataids:
        if not isinstance(dataid, str) or not dataid:
            continue

        conn.execute("""
            INSERT OR IGNORE INTO registry.historical_reservations (
                dataid, first_database, inventory_at_utc
            ) VALUES (?, ?, ?)
        """, (dataid, database_name, inventory_at_utc))

        conn.execute("""
            INSERT OR IGNORE INTO registry.historical_locations (
                dataid, database_name, source_kind
            ) VALUES (?, ?, ?)
        """, (dataid, database_name, source_kind))

        count += 1

    return count

def inventory_analysis_directory(conn, analysis_dir, inventory_at_utc):
    """Inventory existing measurement and audit databases.

    Uses the current transaction for attached databases and
    read-only connections for other databases. Does not commit.
    """
    from pathlib import Path

    if not conn.in_transaction:
        raise RuntimeError("Inventory requires an active transaction")

    initialize_registry(conn)

    folder = Path(analysis_dir).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)

    attached = {
        Path(path).resolve(): schema
        for _, schema, path in conn.execute("PRAGMA database_list")
        if path and schema in ("main", "individual", "avg")
    }

    total = 0

    for path in sorted(folder.glob("*.db")):
        # The central registry is not a measurement collection.
        if path.name == "StampZ_DataID_Registry.db":
            continue
        if path.stem.endswith("_AUDIT"):
            kind = "AUDIT"
            collection = path.stem[:-6]
        elif path.stem.endswith("_AVG"):
            kind = "AVG"
            collection = path.stem[:-4]
        else:
            kind = "INDIVIDUAL"
            collection = path.stem

        if path.resolve() in attached:
            dataids = read_attached_historical_dataids(
                conn, attached[path.resolve()], kind
            )
        else:
            dataids = read_historical_dataids(path, kind)

        # Assignments already recorded by the permanent registry
        # must not be relabeled as historical reservations.
        historical = []

        for dataid in dataids:
            assigned = conn.execute("""
                SELECT 1
                FROM registry.dataid_assignments
                WHERE assigned_dataid = ?
            """, (dataid,)).fetchone()

            if not assigned:
                historical.append(dataid)

        total += register_historical_dataids(
            conn, historical, collection, kind, inventory_at_utc
        )

    return total