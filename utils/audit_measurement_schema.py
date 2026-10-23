"""Schema preparation for StampZ coordinated audit saves.

Uses the caller's existing SQLite connection.
Never opens another connection or commits independently.
"""

def prepare_individual_schema(conn, schema="individual"):
    """Initialize individual measurement tables in an attached database."""

    if schema != "individual":
        raise ValueError("Expected individual database schema")

    if not conn.in_transaction:
        raise RuntimeError("Schema preparation requires a transaction")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.measurement_sets (
            set_id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_name TEXT NOT NULL,
            measurement_date TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            description TEXT
        )
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.color_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER NOT NULL,
            coordinate_point INTEGER NOT NULL,
            x_position REAL NOT NULL,
            y_position REAL NOT NULL,
            l_value REAL NOT NULL,
            a_value REAL NOT NULL,
            b_value REAL NOT NULL,
            rgb_r REAL NOT NULL,
            rgb_g REAL NOT NULL,
            rgb_b REAL NOT NULL,
            sample_type TEXT,
            sample_size TEXT,
            sample_anchor TEXT,
            measurement_date TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            notes TEXT,
            FOREIGN KEY(set_id) REFERENCES measurement_sets(set_id)
        )
    """)

    # Match the additional columns used by the audit measurement writer.
    columns = {
        # Analytical variability
        "rgb_r_stddev": "REAL",
        "rgb_g_stddev": "REAL",
        "rgb_b_stddev": "REAL",
        "lab_l_stddev": "REAL",
        "lab_a_stddev": "REAL",
        "lab_b_stddev": "REAL",

        # Plot_3D compatibility
        "marker_preference": "TEXT DEFAULT '.'",
        "color_preference": "TEXT DEFAULT 'blue'",
        "cluster_id": "INTEGER",
        "delta_e": "REAL",
        "centroid_x": "REAL",
        "centroid_y": "REAL",
        "centroid_z": "REAL",
        "sphere_color": "TEXT",
        "sphere_radius": "REAL",
        "trendline_valid": "BOOLEAN DEFAULT 1",
        "data_source": "TEXT DEFAULT 'stampz'",
    }

    existing = {
        row[1]
        for row in conn.execute(
            f"PRAGMA {schema}.table_info(color_measurements)"
        )
    }

    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(
                f"ALTER TABLE {schema}.color_measurements "
                f"ADD COLUMN {name} {column_type}"
            )

    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {schema}.idx_set_point
        ON color_measurements(set_id, coordinate_point)
    """)


def prepare_average_schema(conn, schema="avg"):
    """Initialize AVG measurement tables in an attached database."""

    if schema != "avg":
        raise ValueError("Expected AVG database schema")

    if not conn.in_transaction:
        raise RuntimeError("Schema preparation requires a transaction")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.measurement_sets (
            set_id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_name TEXT NOT NULL,
            measurement_date TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            description TEXT
        )
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.color_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER NOT NULL,
            coordinate_point INTEGER NOT NULL,
            x_position REAL NOT NULL,
            y_position REAL NOT NULL,
            l_value REAL NOT NULL,
            a_value REAL NOT NULL,
            b_value REAL NOT NULL,
            rgb_r REAL NOT NULL,
            rgb_g REAL NOT NULL,
            rgb_b REAL NOT NULL,
            sample_type TEXT,
            sample_size TEXT,
            sample_anchor TEXT,
            measurement_date TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            notes TEXT,
            is_averaged BOOLEAN DEFAULT 1,
            source_samples_count INTEGER,
            source_sample_ids TEXT,
            FOREIGN KEY(set_id) REFERENCES measurement_sets(set_id)
        )
    """)

    required_columns = {
        "is_averaged": "BOOLEAN DEFAULT 1",
        "source_samples_count": "INTEGER",
        "source_sample_ids": "TEXT",
    }

    existing = {
        row[1]
        for row in conn.execute(
            f"PRAGMA {schema}.table_info(color_measurements)"
        )
    }

    for name, column_type in required_columns.items():
        if name not in existing:
            conn.execute(
                f"ALTER TABLE {schema}.color_measurements "
                f"ADD COLUMN {name} {column_type}"
            )

    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {schema}.idx_set_point
        ON color_measurements(set_id, coordinate_point)
    """)
