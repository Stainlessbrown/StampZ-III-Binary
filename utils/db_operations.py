#!/usr/bin/env python3
"""Cross-database operations for StampZ color-analysis sample sets.

Each sample set in StampZ lives in its own SQLite file. This module
provides safe move/copy/merge primitives that operate at the SQL level
via ``ATTACH DATABASE`` so we never have to round-trip large numbers
of rows through Python.

All functions assume the standard StampZ color-analysis schema:

    measurement_sets(set_id PK, image_name, measurement_date, description)
    color_measurements(id PK, set_id FK, ... many columns ...)

Column lists are discovered at runtime via ``PRAGMA table_info`` so
the helpers continue to work as the schema grows.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Schema discovery
# --------------------------------------------------------------------------- #

def _table_columns(
    conn: sqlite3.Connection,
    table: str,
    schema: Optional[str] = None,
) -> List[str]:
    """Return the column names of ``table`` in declaration order.

    SQLite's PRAGMA table_info uses a leading ``schema.`` on the
    *PRAGMA itself*, not on the table argument:
        PRAGMA src.table_info(color_measurements)
    so we build the statement accordingly when a schema is supplied.
    """
    if schema:
        sql = f"PRAGMA {schema}.table_info({table})"
    else:
        sql = f"PRAGMA table_info({table})"
    cursor = conn.execute(sql)
    return [row[1] for row in cursor.fetchall()]


def _common_columns(
    dst_conn: sqlite3.Connection,
    table: str,
    src_alias: str = "src",
) -> List[str]:
    """Columns present in both the destination and attached source DB.

    Using the intersection means we never try to INSERT a column the
    destination doesn't have, and we don't drop data that exists on
    both sides. The primary key column is excluded so AUTOINCREMENT
    works as expected in the destination.
    """
    dst_cols = _table_columns(dst_conn, table)
    src_cols = _table_columns(dst_conn, table, schema=src_alias)
    common = [c for c in dst_cols if c in src_cols]
    # Drop the autoincrement PK so the destination assigns fresh IDs.
    return [c for c in common if c not in ("id", "set_id")] if table == "color_measurements" \
        else [c for c in common if c != "set_id"]


# --------------------------------------------------------------------------- #
# Read-only helpers
# --------------------------------------------------------------------------- #

def list_image_names(db_path: str) -> List[str]:
    """Distinct ``image_name`` values held in ``db_path``.

    Returns an empty list if the file doesn't exist or the table is
    missing (e.g. a freshly created but unused DB).
    """
    if not os.path.exists(db_path):
        return []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT image_name FROM measurement_sets "
                "ORDER BY image_name"
            )
            return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error:
        return []


def find_collisions(src_paths: Sequence[str]) -> Dict[str, List[str]]:
    """Identify image_names that appear in more than one source DB.

    Returns ``{image_name: [src_path, ...]}`` for every name that
    appears in two or more of the supplied databases. Useful for
    pre-flight checks before a merge so the caller can prompt the
    user to rename collisions.
    """
    by_name: Dict[str, List[str]] = {}
    for path in src_paths:
        for name in list_image_names(path):
            by_name.setdefault(name, []).append(path)
    return {name: paths for name, paths in by_name.items() if len(paths) > 1}


# --------------------------------------------------------------------------- #
# Single-set copy / delete / move
# --------------------------------------------------------------------------- #

def _copy_one_set(
    dst_conn: sqlite3.Connection,
    src_alias: str,
    image_name: str,
    *,
    rename_to: Optional[str] = None,
) -> int:
    """Copy a single ``measurement_set`` + its child rows.

    Assumes a source DB has already been ATTACHed as ``src_alias`` on
    ``dst_conn``. Returns the number of ``color_measurements`` rows
    copied (the parent set row is always 1).
    """
    final_name = rename_to or image_name

    # Pull source set rows that match (there may technically be more
    # than one row sharing an image_name if the user ran the same image
    # twice; copy each in order and stitch its children behind it).
    src_set_rows = dst_conn.execute(
        f"SELECT set_id, measurement_date, description "
        f"FROM {src_alias}.measurement_sets WHERE image_name = ?",
        (image_name,),
    ).fetchall()

    if not src_set_rows:
        return 0

    # Build a reusable column list for the children once.
    child_cols = _common_columns(dst_conn, "color_measurements", src_alias)
    child_col_list = ", ".join(child_cols)

    total_children = 0
    for src_set_id, src_date, src_desc in src_set_rows:
        # Insert the parent row first so we have a destination set_id.
        cursor = dst_conn.execute(
            "INSERT INTO measurement_sets (image_name, measurement_date, description) "
            "VALUES (?, ?, ?)",
            (final_name, src_date, src_desc),
        )
        new_set_id = cursor.lastrowid

        # Then bulk-copy the children, rewriting set_id to the new value.
        result = dst_conn.execute(
            f"INSERT INTO color_measurements (set_id, {child_col_list}) "
            f"SELECT ?, {child_col_list} FROM {src_alias}.color_measurements "
            f"WHERE set_id = ?",
            (new_set_id, src_set_id),
        )
        total_children += result.rowcount

    return total_children


def copy_measurement_set(
    src_path: str,
    dst_path: str,
    image_name: str,
    *,
    rename_to: Optional[str] = None,
) -> int:
    """Copy one image's measurement set from src DB to dst DB.

    The destination file must already exist with the correct schema
    (use ``ColorAnalysisDB(name)`` to create it). ``rename_to``
    rewrites the image_name on arrival when set.

    Returns the number of color_measurements rows copied.
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source database not found: {src_path}")
    if not os.path.exists(dst_path):
        raise FileNotFoundError(f"Destination database not found: {dst_path}")

    with sqlite3.connect(dst_path) as conn:
        conn.execute("ATTACH DATABASE ? AS src", (src_path,))
        try:
            conn.execute("BEGIN")
            copied = _copy_one_set(conn, "src", image_name, rename_to=rename_to)
            conn.execute("COMMIT")
            return copied
        except sqlite3.Error:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("DETACH DATABASE src")


def delete_measurement_set(db_path: str, image_name: str) -> int:
    """Delete every measurement_set with this image_name and its children.

    Returns the number of color_measurements rows removed. The parent
    rows are removed too; the function is a no-op if nothing matches.
    """
    if not os.path.exists(db_path):
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")
        try:
            set_ids = [
                row[0] for row in conn.execute(
                    "SELECT set_id FROM measurement_sets WHERE image_name = ?",
                    (image_name,),
                ).fetchall()
            ]
            if not set_ids:
                conn.execute("ROLLBACK")
                return 0

            placeholders = ",".join("?" for _ in set_ids)
            child_result = conn.execute(
                f"DELETE FROM color_measurements WHERE set_id IN ({placeholders})",
                set_ids,
            )
            removed = child_result.rowcount

            conn.execute(
                f"DELETE FROM measurement_sets WHERE set_id IN ({placeholders})",
                set_ids,
            )
            conn.execute("COMMIT")
            return removed
        except sqlite3.Error:
            conn.execute("ROLLBACK")
            raise


def move_measurement_set(
    src_path: str,
    dst_path: str,
    image_name: str,
    *,
    rename_to: Optional[str] = None,
) -> int:
    """Move one image's measurement set from src to dst.

    Copies first, then deletes from the source only if the copy
    succeeded. Returns the number of child rows transferred.
    """
    copied = copy_measurement_set(
        src_path, dst_path, image_name, rename_to=rename_to
    )
    # If the copy yielded nothing, treat as a no-op (no source rows).
    if copied == 0 and not list_image_names(src_path).count(image_name):
        return 0
    delete_measurement_set(src_path, image_name)
    return copied


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #

def merge_databases(
    src_paths: Sequence[str],
    dst_path: str,
    *,
    rename_map: Optional[Dict[Tuple[str, str], str]] = None,
) -> int:
    """Build a fresh DB at ``dst_path`` from the contents of every source.

    The destination must already exist with the correct schema — the
    caller should create it via ``ColorAnalysisDB(name)`` so that
    every column (including future additions) is present.

    ``rename_map`` is keyed by ``(src_path, original_image_name)`` and
    supplies a replacement image_name to use when writing that set
    into the destination. Anything not in the map is copied verbatim.

    Source files are opened read-only via ``ATTACH`` and never
    mutated, matching the "non-destructive merge" guarantee.

    Returns the total number of color_measurements rows written.
    """
    if not os.path.exists(dst_path):
        raise FileNotFoundError(f"Destination database not found: {dst_path}")
    rename_map = rename_map or {}

    total = 0
    with sqlite3.connect(dst_path) as conn:
        for src_path in src_paths:
            if not os.path.exists(src_path):
                raise FileNotFoundError(f"Source database not found: {src_path}")

            conn.execute("ATTACH DATABASE ? AS src", (src_path,))
            try:
                conn.execute("BEGIN")
                names = [
                    row[0] for row in conn.execute(
                        "SELECT DISTINCT image_name FROM src.measurement_sets "
                        "ORDER BY image_name"
                    ).fetchall()
                ]
                for name in names:
                    final = rename_map.get((src_path, name), name)
                    total += _copy_one_set(conn, "src", name, rename_to=final)
                conn.execute("COMMIT")
            except sqlite3.Error:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.execute("DETACH DATABASE src")

    return total
