
"""Audit-trail DataID naming utilities for StampZ-III.

This module handles duplicate DataID numbering while preserving
RAW (-r) and paper (-p) suffixes.

No database modifications are performed here.
"""

import re


def split_dataid(dataid):
    """Separate the base DataID from its RAW/paper suffixes."""
    suffix = ""

    if dataid.endswith("-r-p"):
        suffix = "-r-p"
    elif dataid.endswith("-r"):
        suffix = "-r"
    elif dataid.endswith("-p"):
        suffix = "-p"

    return dataid[:-len(suffix)] if suffix else dataid, suffix


def numbered_dataid(dataid, number):
    """Insert a sequence number before the RAW/paper suffix."""
    base, suffix = split_dataid(dataid)

    # Remove an existing trailing sequence number, if present.
    base = re.sub(r"\(\d+\)$", "", base)

    if number <= 1:
        return f"{base}{suffix}"

    return f"{base}({number}){suffix}"


def next_dataid(dataid, existing_names):
    """Return the next DataID using the highest existing number plus one.

    This function only examines names supplied to it.
    Persistent tracking of deleted numbers will be added separately.
    """
    base, suffix = split_dataid(dataid)
    base = re.sub(r"\(\d+\)$", "", base)

    highest = 0

    for existing in existing_names:
        existing_base, existing_suffix = split_dataid(existing)
        if existing_suffix != suffix:
            continue

        if existing_base == base:
            highest = max(highest, 1)
            continue

        match = re.fullmatch(re.escape(base) + r"\((\d+)\)", existing_base)
        if match:
            highest = max(highest, int(match.group(1)))

    return numbered_dataid(dataid, highest + 1)


# ------------------------------------------------------------
# Persistent DataID sequence tracking
# ------------------------------------------------------------

import sqlite3


def initialize_audit_sequences(conn, existing_names):
    """Create sequence table and reconcile it with existing DataIDs.

    The counter is never reduced, even if records have been deleted.
    Caller controls the transaction.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_sequences (
            base_dataid TEXT PRIMARY KEY,
            highest_number INTEGER NOT NULL
        )
    """)

    families = {}

    for dataid in existing_names:
        base, suffix = split_dataid(dataid)

        # Remove an existing sequence number.
        match = re.fullmatch(r"(.*)\((\d+)\)", base)

        if match:
            base = match.group(1)
            number = int(match.group(2))
        else:
            number = 1

        # RAW and paper variants share one numbering family.
        family = f"{base}{'-r' if '-r' in suffix else ''}"

        families[family] = max(
            families.get(family, 0), number
        )

    for family, highest in families.items():
        conn.execute("""
            INSERT INTO audit_sequences (base_dataid, highest_number)
            VALUES (?, ?)
            ON CONFLICT(base_dataid) DO UPDATE SET
                highest_number = MAX(
                    highest_number,
                    excluded.highest_number
                )
        """, (family, highest))


def allocate_audit_dataid(conn, dataid):
    """Allocate the next DataID within an active transaction.

    Caller must COMMIT or ROLLBACK.
    """
    base, suffix = split_dataid(dataid)
    base = re.sub(r"\(\d+\)$", "", base)

    family = f"{base}{'-r' if '-r' in suffix else ''}"

    row = conn.execute("""
        SELECT highest_number
        FROM audit_sequences
        WHERE base_dataid = ?
    """, (family,)).fetchone()

    highest = row[0] if row else 0
    next_number = highest + 1

    conn.execute("""
        INSERT INTO audit_sequences (base_dataid, highest_number)
        VALUES (?, ?)
        ON CONFLICT(base_dataid) DO UPDATE SET
            highest_number = excluded.highest_number
    """, (family, next_number))

    return numbered_dataid(dataid, next_number)
