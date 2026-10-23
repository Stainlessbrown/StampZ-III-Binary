"""DataID allocation for StampZ-III permanent audit saves.

The original DataID is literal and is never rewritten.
Subsequent saves use _(2), _(3), etc., before RAW/paper suffixes.

Sequence allocation occurs inside the caller's SQLite transaction.
"""

import sqlite3


def split_dataid(dataid):
    """Separate recognized RAW/paper suffixes."""
    if dataid.endswith("-r-p"):
        return dataid[:-4], "-r-p"
    if dataid.endswith("-r"):
        return dataid[:-2], "-r"
    if dataid.endswith("-p"):
        return dataid[:-2], "-p"
    return dataid, ""


def numbered_dataid(dataid, number):
    """Number a literal original DataID without stripping its text."""
    base, suffix = split_dataid(dataid)

    if number < 1:
        raise ValueError("DataID sequence must be positive")

    if number == 1:
        return dataid

    return f"{base}_({number}){suffix}"


def next_dataid(dataid, existing_names):
    """Find the next available identifier in a supplied collection."""
    existing = set(existing_names)
    number = 1

    while True:
        candidate = numbered_dataid(dataid, number)
        if candidate not in existing:
            return candidate
        number += 1


def initialize_audit_sequences(conn, existing_names=None):
    """Initialize persistent sequence storage.

    Do not infer families by parsing historical filenames.
    Existing counters are preserved.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_sequences (
            base_dataid TEXT PRIMARY KEY,
            highest_number INTEGER NOT NULL
        )
    """)


def _paper_variant(dataid):
    """Return the companion paper DataID."""
    if dataid.endswith("-r-p") or dataid.endswith("-p"):
        return dataid
    if dataid.endswith("-r"):
        return dataid[:-2] + "-r-p"
    return dataid + "-p"


def _name_exists(conn, candidate):
    """Check the audit archive and any attached measurement databases."""
    names = {candidate, _paper_variant(candidate)}

    # The permanent audit database is the primary connection.
    for name in names:
        row = conn.execute(
            "SELECT 1 FROM main.audit_records "
            "WHERE dataid = ? LIMIT 1",
            (name,)
        ).fetchone()
        if row:
            return True

    # Only inspect conventional databases actually attached.
    attached = {
        row[1] for row in conn.execute("PRAGMA database_list")
    }

    for schema in ("individual", "avg"):
        if schema not in attached:
            continue

        for name in names:
            row = conn.execute(
                f"SELECT 1 FROM {schema}.measurement_sets "
                "WHERE image_name = ? LIMIT 1",
                (name,)
            ).fetchone()
            if row:
                return True

    return False


def allocate_audit_dataid(conn, dataid):
    """Allocate a unique DataID inside an active audit transaction.

    The input is the exact original family name.
    No existing measurement or audit row is modified.
    """
    if not conn.in_transaction:
        raise RuntimeError("DataID allocation requires a transaction")

    if not isinstance(dataid, str) or not dataid.strip():
        raise ValueError("Original DataID cannot be empty")

    initialize_audit_sequences(conn)

    family = dataid

    row = conn.execute("""
        SELECT highest_number FROM audit_sequences
        WHERE base_dataid = ?
    """, (family,)).fetchone()

    number = (row[0] if row else 0) + 1

    while True:
        candidate = numbered_dataid(family, number)
        if not _name_exists(conn, candidate):
            break
        number += 1

    conn.execute("""
        INSERT INTO audit_sequences (base_dataid, highest_number)
        VALUES (?, ?)
        ON CONFLICT(base_dataid) DO UPDATE SET
            highest_number = MAX(
                audit_sequences.highest_number,
                excluded.highest_number
            )
    """, (family, number))

    return candidate
