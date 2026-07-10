#!/usr/bin/env python3
"""
Stamp Catalog Manager for StampZ-III.

Opens as a Toplevel window from within StampZ (or standalone).
Provides a full data-entry UI for the three-table catalog database:
  Directory  → countries
  Stamps     → one row per physical stamp (shared fields)
  Catalog_Numbers → per-catalog cross-references
"""

import shutil
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import os

from utils.path_utils import get_base_data_dir

DB_NAME = "StampZ_Interface.db"


def _catalog_db_path() -> str:
    """Return the path to the stamp-catalog database.

    Uses the same data-directory logic as the rest of StampZ so
    the file lives inside the app's data folder (bundled on first
    install) instead of being dropped on the user's Desktop.

    On first launch (or after an upgrade that adds the catalog for
    the first time), the bundled seed database is copied into the
    user data directory so new users start with the full Directory
    table and any stamps/catalog numbers shipped with the build.
    """
    data_dir = get_base_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, DB_NAME)

    if not os.path.exists(db_path) or _is_empty_catalog(db_path):
        _seed_from_bundle(db_path)

    return db_path


def _is_empty_catalog(db_path: str) -> bool:
    """Return True if the DB exists but the Directory table has no rows."""
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM Directory"
            ).fetchone()
            return row is None or row[0] == 0
    except Exception:
        return True


def _seed_from_bundle(db_path: str) -> None:
    """Copy the bundled seed database to the user's data directory."""
    if getattr(sys, 'frozen', False):
        # Running inside a PyInstaller bundle
        bundle_db = os.path.join(sys._MEIPASS, 'data', DB_NAME)
    else:
        # Running from source — DB is in the project's data/ dir
        bundle_db = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', DB_NAME,
        )

    if os.path.exists(bundle_db):
        shutil.copy2(bundle_db, db_path)

STAMP_TYPES = [
    'Definitive', 'Commemorative', 'Airmail',
    'Postage Due', 'Fiscal', 'Semi-Postal', 'Official', 'General'
]

CATALOG_SYSTEMS = [
    'Scott', 'SG', 'Michel', 'Yvert & Tellier', 'Sassone',
    'AFA', 'FACIT', 'Spink|Maury', 'Unitrade', 'J. Barefoot',
    'Brusden White','Yang', 'Ma', 'Zumstein', 'Mundfil'
]


class StampCatalogManager:
    """
    Stamp catalog data-entry window.

    Can be launched from StampZ via open_catalog_database() or run
    standalone.  Pass a tk.Tk or tk.Toplevel as ``parent``; if None
    a new Tk root is created (standalone mode).
    """

    def __init__(self, parent=None):
        if parent is None:
            self.root = tk.Tk()
            self._standalone = True
        else:
            self.root = tk.Toplevel(parent)
            self._standalone = False

        self.root.title("Stamp Catalog Database")
        self.root.geometry("1020x760")
        self.root.minsize(820, 600)

        self.conn = sqlite3.connect(_catalog_db_path())
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

        self.current_stamp_id = None
        self._stamp_ids = []
        self._all_countries = []
        self._current_country = None   # stored so save works after focus leaves listbox

        self._build_ui()
        self._load_countries()

        if not self._standalone:
            # Keep on top of parent and clean up DB on close
            self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Schema bootstrap ────────────────────────────────────────

    def _ensure_schema(self):
        """Create the catalog tables if they don't already exist.

        This is a safety net for fresh installs where the bundled DB
        was not yet copied or is empty.  It is idempotent.
        """
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS "Directory" (
                "Country"         TEXT UNIQUE,
                "Parent_Country"  INTEGER,
                "Year-start"      INTEGER,
                "Year_end"        INTEGER,
                "primary_catalog" TEXT,
                PRIMARY KEY("Country")
            );

            CREATE TABLE IF NOT EXISTS "Stamps" (
                "id"               INTEGER PRIMARY KEY AUTOINCREMENT,
                "country"          TEXT    NOT NULL,
                "stamp_type"       TEXT    NOT NULL DEFAULT 'General'
                                         CHECK(stamp_type IN (
                                             'Definitive','Commemorative','Airmail',
                                             'Postage Due','Fiscal','Semi-Postal',
                                             'Official','General'
                                         )),
                "date_issued"      TEXT,
                "date_withdrawn"   TEXT,
                "denomination"     TEXT,
                "color"            TEXT,
                "perf"             TEXT,
                "description"      TEXT,
                "notes"            TEXT,
                "parent_stamp_id"  INTEGER,
                FOREIGN KEY ("country")         REFERENCES "Directory"("Country"),
                FOREIGN KEY ("parent_stamp_id") REFERENCES "Stamps"("id")
            );

            CREATE TABLE IF NOT EXISTS "Catalog_Numbers" (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                stamp_id        INTEGER NOT NULL,
                catalog_system  TEXT    NOT NULL,
                catalog_edition TEXT    NOT NULL DEFAULT '',
                catalog_number  TEXT    NOT NULL,
                catalog_notes   TEXT,
                described_color TEXT,
                FOREIGN KEY (stamp_id) REFERENCES Stamps(id),
                UNIQUE(stamp_id, catalog_system, catalog_edition, catalog_number)
            );

            CREATE INDEX IF NOT EXISTS idx_cat_stamp
                ON Catalog_Numbers(stamp_id);
            CREATE INDEX IF NOT EXISTS idx_cat_lookup
                ON Catalog_Numbers(catalog_system, catalog_edition, catalog_number);
        """)

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        # ── Main pane ─────────────────────────────────────────────
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                              sashwidth=5, sashrelief=tk.RAISED)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # ── Left panel: countries + stamps ────────────────────────
        left = tk.Frame(main, width=260)
        main.add(left, minsize=200)
        left.pack_propagate(False)

        # Countries section
        tk.Label(left, text="Countries",
                 font=("", 14, "bold")).pack(anchor=tk.W, pady=(4, 0))

        clist_frame = tk.Frame(left)
        clist_frame.pack(fill=tk.BOTH, expand=True)

        self.country_list = tk.Listbox(clist_frame, selectmode=tk.SINGLE,
                                       activestyle="dotbox",
                                       font=("", 14), height=8)
        csb = tk.Scrollbar(clist_frame, orient=tk.VERTICAL,
                           command=self.country_list.yview)
        self.country_list.config(yscrollcommand=csb.set)
        csb.pack(side=tk.RIGHT, fill=tk.Y)
        self.country_list.pack(fill=tk.BOTH, expand=True)
        self.country_list.bind("<ButtonRelease-1>", self._on_country_click)

        # Add-country row
        add_country_row = tk.Frame(left)
        add_country_row.pack(fill=tk.X, pady=(2, 4))
        tk.Button(add_country_row, text="+ Country",
                  command=self._pick_new_country).pack(side=tk.LEFT)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        # Stamps section
        self.stamps_label = tk.Label(left, text="Stamps",
                                     font=("", 14, "bold"))
        self.stamps_label.pack(anchor=tk.W)

        # Search box
        search_row = tk.Frame(left)
        search_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(search_row, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_stamps)
        tk.Entry(search_row, textvariable=self.search_var,
                 width=14).pack(side=tk.LEFT, padx=2)
        tk.Button(search_row, text="✕", width=2,
                  command=lambda: self.search_var.set("")).pack(side=tk.LEFT)

        list_frame = tk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.stamp_list = tk.Listbox(list_frame, selectmode=tk.SINGLE,
                                     activestyle="dotbox",
                                     font=("Courier", 14))
        sb = tk.Scrollbar(list_frame, orient=tk.VERTICAL,
                          command=self.stamp_list.yview)
        self.stamp_list.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.stamp_list.pack(fill=tk.BOTH, expand=True)
        self.stamp_list.bind("<<ListboxSelect>>", self._on_stamp_select)
        self.stamp_list.bind("<ButtonRelease-1>", self._on_stamp_click)

        btn_row1 = tk.Frame(left)
        btn_row1.pack(fill=tk.X, pady=(4, 1))
        tk.Button(btn_row1, text="+ New",
                  command=self._new_stamp,
                  font=("", 14, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(btn_row1, text="Duplicate",
                  command=self._duplicate_stamp).pack(side=tk.LEFT)
        btn_row2 = tk.Frame(left)
        btn_row2.pack(fill=tk.X, pady=(0, 4))
        tk.Button(btn_row2, text="Delete",
                  command=self._delete_stamp,
                  font=("", 14, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(btn_row2, text="Merge…",
                  command=self._merge_stamps,
                  font=("", 14, "bold")).pack(side=tk.LEFT)

        # ── Right: detail form ────────────────────────────────────
        right = tk.Frame(main)
        main.add(right, minsize=540)

        detail = tk.LabelFrame(right, text="Stamp Details", padx=8, pady=6)
        detail.pack(fill=tk.X, padx=4, pady=(4, 2))

        fields = [
            ("Stamp Type",     "type_var",          "combo", STAMP_TYPES),
            ("Date Issued",    "date_issued_var",    "entry", None),
            ("Date Withdrawn", "date_withdrawn_var", "entry", None),
            ("Denomination",   "denom_var",          "entry", None),
            ("Perf/Imperf",    "perf_var",           "entry", None),
            ("Description",    "desc_var",           "entry", None),
        ]

        self.field_vars = {}
        for i, (label, varname, widget, options) in enumerate(fields):
            tk.Label(detail, text=label + ":", anchor=tk.W,
                     width=15).grid(row=i, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar()
            self.field_vars[varname] = var
            if widget == "combo":
                w = ttk.Combobox(detail, textvariable=var,
                                 values=options, state="readonly", width=30)
            else:
                w = tk.Entry(detail, textvariable=var, width=32)
            w.grid(row=i, column=1, sticky=tk.W, padx=4, pady=2)

        tk.Label(detail, text="Notes:", anchor=tk.W,
                 width=15).grid(row=len(fields), column=0,
                                sticky=tk.NW, pady=2)
        self.notes_text = tk.Text(detail, width=32, height=3, font=("", 14))
        self.notes_text.grid(row=len(fields), column=1,
                             sticky=tk.W, padx=4, pady=2)

        # Save button
        tk.Button(right, text="  Save Stamp  ",
                  command=self._save_stamp,
                  font=("", 15, "bold"), relief=tk.RAISED,
                  padx=10, pady=4).pack(pady=6)

        # ── Catalog numbers ───────────────────────────────────────
        cat_frame = tk.LabelFrame(right, text="Catalog Numbers",
                                  padx=6, pady=6)
        cat_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        cols = ("System", "Edition", "Number", "Color", "Notes")
        self.cat_tree = ttk.Treeview(cat_frame, columns=cols,
                                     show="headings", height=5)
        self.cat_tree.heading("System",  text="Catalog System")
        self.cat_tree.heading("Edition", text="Edition")
        self.cat_tree.heading("Number",  text="Number")
        self.cat_tree.heading("Color",   text="Described Color")
        self.cat_tree.heading("Notes",   text="Notes")
        self.cat_tree.column("System",  width=140)
        self.cat_tree.column("Edition", width=70)
        self.cat_tree.column("Number",  width=70)
        self.cat_tree.column("Color",   width=120)
        self.cat_tree.column("Notes",   width=140)

        cat_sb = tk.Scrollbar(cat_frame, orient=tk.VERTICAL,
                              command=self.cat_tree.yview)
        self.cat_tree.config(yscrollcommand=cat_sb.set)
        cat_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cat_tree.pack(fill=tk.BOTH, expand=True)

        # Checkbox grid for catalog system selection
        cb_frame = tk.Frame(cat_frame)
        cb_frame.pack(fill=tk.X, pady=(6, 2))
        tk.Label(cb_frame, text="Systems:",
                 font=("", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 6))

        self.cat_system_vars = {}
        for i, system in enumerate(CATALOG_SYSTEMS):
            var = tk.BooleanVar()
            self.cat_system_vars[system] = var
            row_num = i // 5
            col_num = (i % 5) + 1
            tk.Checkbutton(cb_frame, text=system, variable=var).grid(
                row=row_num, column=col_num, sticky=tk.W, padx=4)

        # "Other" catalog row — free-text for catalogs not in the checkbox list
        other_row = tk.Frame(cat_frame)
        other_row.pack(fill=tk.X, pady=(4, 0))
        self.cat_other_var = tk.BooleanVar()
        tk.Checkbutton(other_row, text="Other catalog:",
                       variable=self.cat_other_var,
                       command=self._toggle_other_catalog).pack(side=tk.LEFT)
        self.cat_other_name_var = tk.StringVar()
        self.cat_other_entry = tk.Entry(other_row,
                                        textvariable=self.cat_other_name_var,
                                        width=22, state=tk.DISABLED)
        self.cat_other_entry.pack(side=tk.LEFT, padx=4)

        # Number / notes / buttons row
        add_row = tk.Frame(cat_frame)
        add_row.pack(fill=tk.X, pady=(2, 0))

        tk.Label(add_row, text="Number:").pack(side=tk.LEFT)
        self.cat_num_var = tk.StringVar()
        tk.Entry(add_row, textvariable=self.cat_num_var,
                 width=10).pack(side=tk.LEFT, padx=2)

        tk.Label(add_row, text="Notes:").pack(side=tk.LEFT, padx=(6, 0))
        self.cat_notes_var = tk.StringVar()
        tk.Entry(add_row, textvariable=self.cat_notes_var,
                 width=18).pack(side=tk.LEFT, padx=2)

        tk.Button(add_row, text="Add to Checked",
                  command=self._add_catalog_number,
                  font=("", 12, "bold")).pack(side=tk.LEFT, padx=(6, 2))
        tk.Button(add_row, text="Remove Selected",
                  command=self._remove_catalog_number).pack(side=tk.LEFT)

    # ── Country loading ───────────────────────────────────────────

    def _load_countries(self):
        """Populate country list with only countries that have stamps."""
        self.country_list.delete(0, tk.END)
        cur = self.conn.execute(
            "SELECT DISTINCT country FROM Stamps "
            "ORDER BY country")
        self._listed_countries = [r[0] for r in cur.fetchall()]
        for c in self._listed_countries:
            self.country_list.insert(tk.END, c)
        # Also keep the full directory list for _pick_new_country
        cur2 = self.conn.execute(
            "SELECT Country FROM Directory WHERE Country IS NOT NULL ORDER BY Country")
        self._all_countries = [r[0] for r in cur2.fetchall()]

    def _on_country_click(self, event):
        idx = self.country_list.nearest(event.y)
        if 0 <= idx < len(self._listed_countries):
            self.country_list.selection_clear(0, tk.END)
            self.country_list.selection_set(idx)
            self._current_country = self._listed_countries[idx]
            self.stamps_label.config(text=f"Stamps — {self._current_country}")
            self.search_var.set("")
            self._load_stamps(self._current_country)

    def _pick_new_country(self):
        """Open a simple dialog to pick any country from the Directory."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Country")
        dialog.geometry("320x460")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Filter:").pack(anchor=tk.W, padx=8, pady=(8,0))
        fvar = tk.StringVar()
        fentry = tk.Entry(dialog, textvariable=fvar, width=30)
        fentry.pack(padx=8, pady=2)

        lb_frame = tk.Frame(dialog)
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        lb = tk.Listbox(lb_frame, font=("", 14))
        lbsb = tk.Scrollbar(lb_frame, command=lb.yview)
        lb.config(yscrollcommand=lbsb.set)
        lbsb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.pack(fill=tk.BOTH, expand=True)

        def refresh(*_):
            term = fvar.get().lower()
            lb.delete(0, tk.END)
            for c in self._all_countries:
                if term in c.lower():
                    lb.insert(tk.END, c)
        fvar.trace("w", refresh)
        refresh()
        fentry.focus_set()

        chosen = [None]

        def on_click(event):
            """Single click selects using pixel position (macOS reliable)."""
            idx = lb.nearest(event.y)
            if 0 <= idx < lb.size():
                lb.selection_clear(0, tk.END)
                lb.selection_set(idx)

        def on_select(event=None):
            sel = lb.curselection()
            if not sel:
                # Fallback: use first item if nothing selected
                if lb.size() > 0:
                    chosen[0] = lb.get(0)
                    dialog.destroy()
                return
            chosen[0] = lb.get(sel[0])
            dialog.destroy()

        lb.bind("<ButtonRelease-1>", on_click)
        lb.bind("<Double-Button-1>", on_select)
        lb.bind("<Return>", on_select)
        fentry.bind("<Return>", on_select)  # press Enter in filter to pick first match
        tk.Button(dialog, text="Select", command=on_select).pack(pady=6)
        dialog.wait_window()

        if chosen[0]:
            self._current_country = chosen[0]
            self.stamps_label.config(text=f"Stamps — {chosen[0]}")
            self.search_var.set("")
            self._load_stamps(chosen[0])
            # Add to country list if not already there
            if chosen[0] not in self._listed_countries:
                self._listed_countries.append(chosen[0])
                self._listed_countries.sort()
                self.country_list.delete(0, tk.END)
                for c in self._listed_countries:
                    self.country_list.insert(tk.END, c)

    # ── Stamp list ────────────────────────────────────────────────

    def _on_country_select(self, event=None):
        pass  # kept for compatibility

    def _catalog_summary(self, stamp_id):
        """Return a compact string of catalog numbers for a stamp, e.g. 'Scott #173  SG #200'."""
        cur = self.conn.execute(
            "SELECT catalog_system, catalog_number "
            "FROM Catalog_Numbers WHERE stamp_id=? "
            "ORDER BY catalog_system, catalog_number LIMIT 3",
            (stamp_id,))
        parts = [f"{r[0]} #{r[1]}" for r in cur.fetchall()]
        if not parts:
            return ""
        # Check if there are more than 3
        total = self.conn.execute(
            "SELECT COUNT(*) FROM Catalog_Numbers WHERE stamp_id=?",
            (stamp_id,)).fetchone()[0]
        summary = "  ".join(parts)
        if total > 3:
            summary += f"  +{total - 3}"
        return f"  [{summary}]"

    def _load_stamps(self, country, search=""):
        self.stamp_list.delete(0, tk.END)
        self._stamp_ids.clear()

        if search:
            term = f"%{search.lower()}%"
            cur = self.conn.execute(
                "SELECT id, denomination, description, date_issued "
                "FROM Stamps WHERE country=? "
                "AND (LOWER(description) LIKE ? "
                "  OR LOWER(denomination) LIKE ? "
                "  OR date_issued LIKE ? "
                "  OR LOWER(COALESCE(stamp_type,'')) LIKE ? "
                "  OR LOWER(COALESCE(perf,'')) LIKE ?) "
                "ORDER BY id",
                (country, term, term, term, term, term))
        else:
            cur = self.conn.execute(
                "SELECT id, denomination, description, date_issued "
                "FROM Stamps WHERE country=? ORDER BY id",
                (country,))

        for row in cur.fetchall():
            denom = row["denomination"] or ""
            desc  = row["description"]  or ""
            year  = row["date_issued"]  or ""
            cats  = self._catalog_summary(row["id"])
            label = f"{row['id']:>5}  {denom:>6}  {year:<6}  {desc}{cats}"
            self.stamp_list.insert(tk.END, label)
            self._stamp_ids.append(row["id"])

        # Auto-select and load the first stamp
        if self._stamp_ids:
            self.stamp_list.selection_set(0)
            self.stamp_list.activate(0)
            self._load_stamp(self._stamp_ids[0])
        else:
            self._clear_form()

    def _filter_stamps(self, *args):
        if not self._current_country:
            return
        self._load_stamps(self._current_country, self.search_var.get())

    def _on_stamp_click(self, event):
        """Reliable macOS click handler using pixel position."""
        idx = self.stamp_list.nearest(event.y)
        if 0 <= idx < len(self._stamp_ids):
            self.stamp_list.selection_clear(0, tk.END)
            self.stamp_list.selection_set(idx)
            self._load_stamp(self._stamp_ids[idx])

    def _on_stamp_select(self, event=None):
        sel = self.stamp_list.curselection()
        if not sel:
            return
        self._load_stamp(self._stamp_ids[sel[0]])

    def _load_stamp(self, stamp_id):
        self.current_stamp_id = stamp_id
        row = self.conn.execute(
            "SELECT * FROM Stamps WHERE id=?", (stamp_id,)).fetchone()
        if not row:
            return
        self.field_vars["type_var"].set(row["stamp_type"] or "General")
        self.field_vars["date_issued_var"].set(row["date_issued"] or "")
        self.field_vars["date_withdrawn_var"].set(row["date_withdrawn"] or "")
        self.field_vars["denom_var"].set(row["denomination"] or "")
        self.field_vars["perf_var"].set(row["perf"] or "")
        self.field_vars["desc_var"].set(row["description"] or "")
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", row["notes"] or "")
        self._load_catalog_numbers(stamp_id)

    # ── Catalog numbers ───────────────────────────────────────────

    def _load_catalog_numbers(self, stamp_id):
        for row in self.cat_tree.get_children():
            self.cat_tree.delete(row)
        cur = self.conn.execute(
            "SELECT catalog_system, catalog_edition, catalog_number, "
            "       described_color, catalog_notes "
            "FROM Catalog_Numbers WHERE stamp_id=? "
            "ORDER BY catalog_system, catalog_edition, catalog_number", (stamp_id,))
        for row in cur.fetchall():
            self.cat_tree.insert("", tk.END, values=(
                row["catalog_system"],
                row["catalog_edition"]  or "",
                row["catalog_number"],
                row["described_color"]  or "",
                row["catalog_notes"]    or ""))

    # ── Form actions ──────────────────────────────────────────────

    def _clear_form(self):
        self.current_stamp_id = None
        for var in self.field_vars.values():
            var.set("")
        self.field_vars["type_var"].set("General")
        self.notes_text.delete("1.0", tk.END)
        for row in self.cat_tree.get_children():
            self.cat_tree.delete(row)

    def _new_stamp(self):
        if not self._current_country:
            messagebox.showwarning("No Country",
                                   "Please select a country first.")
            return
        self._clear_form()
        self.stamp_list.selection_clear(0, tk.END)

    def _duplicate_stamp(self):
        """Copy current stamp fields to a new blank entry for easy variant entry."""
        if not self.current_stamp_id:
            messagebox.showwarning("No Selection",
                                   "Select a stamp to duplicate.")
            return
        # Keep all field values but clear the id — user edits and saves as new
        self.current_stamp_id = None
        self.stamp_list.selection_clear(0, tk.END)
        # Clear catalog numbers (new stamp starts with none)
        for row in self.cat_tree.get_children():
            self.cat_tree.delete(row)
        messagebox.showinfo("Duplicated",
                            "Fields copied from selected stamp.\n"
                            "Edit as needed and click Save Stamp to create "
                            "a new entry.")

    def _save_stamp(self):
        country = self._current_country
        if not country:
            messagebox.showwarning("No Country",
                                   "Please select a country first.")
            return

        data = {
            "country":        country,
            "stamp_type":     self.field_vars["type_var"].get() or "General",
            "date_issued":    self.field_vars["date_issued_var"].get() or None,
            "date_withdrawn": self.field_vars["date_withdrawn_var"].get() or None,
            "denomination":   self.field_vars["denom_var"].get() or None,
            "perf":           self.field_vars["perf_var"].get() or None,
            "description":    self.field_vars["desc_var"].get() or None,
            "notes":          self.notes_text.get("1.0", tk.END).strip() or None,
        }

        try:
            if self.current_stamp_id:
                self.conn.execute("""
                    UPDATE Stamps SET
                        stamp_type=:stamp_type, date_issued=:date_issued,
                        date_withdrawn=:date_withdrawn,
                        denomination=:denomination,
                        perf=:perf, description=:description, notes=:notes
                    WHERE id=:id
                """, {**data, "id": self.current_stamp_id})
                self.conn.commit()
            else:
                cur = self.conn.execute("""
                    INSERT INTO Stamps
                        (country, stamp_type, date_issued, date_withdrawn,
                         denomination, perf, description, notes)
                    VALUES
                        (:country, :stamp_type, :date_issued, :date_withdrawn,
                         :denomination, :perf, :description, :notes)
                """, data)
                self.conn.commit()
                self.current_stamp_id = cur.lastrowid

            self._load_stamps(country, self.search_var.get())
            messagebox.showinfo("Saved", "Stamp saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_stamp(self):
        if not self.current_stamp_id:
            messagebox.showwarning("No Selection",
                                   "Select a stamp to delete.")
            return
        if not messagebox.askyesno(
                "Confirm Delete",
                "Delete this stamp and ALL its catalog numbers?"):
            return
        self.conn.execute(
            "DELETE FROM Catalog_Numbers WHERE stamp_id=?",
            (self.current_stamp_id,))
        self.conn.execute(
            "DELETE FROM Stamps WHERE id=?",
            (self.current_stamp_id,))
        self.conn.commit()
        self._clear_form()
        sel = self.country_list.curselection()
        if sel:
            self._load_stamps(self._listed_countries[sel[0]], self.search_var.get())
        self._load_countries()

    def _toggle_other_catalog(self):
        """Enable/disable the free-text catalog name entry."""
        if self.cat_other_var.get():
            self.cat_other_entry.config(state=tk.NORMAL)
            self.cat_other_entry.focus_set()
        else:
            self.cat_other_entry.config(state=tk.DISABLED)
            self.cat_other_name_var.set("")

    def _add_catalog_number(self):
        if not self.current_stamp_id:
            messagebox.showwarning(
                "Save First",
                "Please save the stamp before adding catalog numbers.")
            return
        checked = [s for s, v in self.cat_system_vars.items() if v.get()]

        # Include Other catalog if checked and named
        if self.cat_other_var.get():
            other_name = self.cat_other_name_var.get().strip()
            if other_name:
                checked.append(other_name)
            else:
                messagebox.showwarning("Other Catalog",
                                       "Please enter the catalog name in the Other field.")
                return

        number  = self.cat_num_var.get().strip()
        notes   = self.cat_notes_var.get().strip() or None

        if not checked:
            messagebox.showwarning("No System",
                                   "Please check at least one catalog system.")
            return
        if not number:
            messagebox.showwarning("Missing Number",
                                   "Please enter a catalog number.")
            return

        duplicates = []
        for system in checked:
            try:
                self.conn.execute(
                    "INSERT INTO Catalog_Numbers "
                    "(stamp_id, catalog_system, catalog_number, catalog_notes) "
                    "VALUES (?,?,?,?)",
                    (self.current_stamp_id, system, number, notes))
            except sqlite3.IntegrityError:
                duplicates.append(system)
        self.conn.commit()

        for var in self.cat_system_vars.values():
            var.set(False)
        self.cat_num_var.set("")
        self.cat_notes_var.set("")
        self._load_catalog_numbers(self.current_stamp_id)

        if duplicates:
            messagebox.showwarning(
                "Some Duplicates",
                f"Already existed (skipped): {', '.join(duplicates)}.\n"
                "All others were added.")

    def _remove_catalog_number(self):
        sel = self.cat_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection",
                                   "Select a catalog entry to remove.")
            return
        values = self.cat_tree.item(sel[0])["values"]
        system  = str(values[0])
        edition = str(values[1])
        number  = str(values[2])
        # values[3] = described_color, values[4] = notes
        if not messagebox.askyesno("Confirm", f"Remove {system} #{number}?"):
            return
        self.conn.execute(
            "DELETE FROM Catalog_Numbers "
            "WHERE stamp_id=? AND catalog_system=? "
            "AND catalog_edition=? AND catalog_number=?",
            (self.current_stamp_id, system, edition, number))
        self.conn.commit()
        self._load_catalog_numbers(self.current_stamp_id)

    def _merge_stamps(self):
        """Merge other stamps into the currently selected canonical stamp."""
        if not self.current_stamp_id:
            messagebox.showwarning("No Selection",
                                   "Select the CANONICAL stamp first, then click Merge.")
            return
        if not self._current_country:
            return

        # Load all stamps for this country except the current one
        cur = self.conn.execute(
            "SELECT id, denomination, description, date_issued "
            "FROM Stamps WHERE country=? AND id != ? ORDER BY id",
            (self._current_country, self.current_stamp_id))
        others = cur.fetchall()

        if not others:
            messagebox.showinfo("No Other Stamps",
                                "No other stamps to merge for this country.")
            return

        # Build dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Merge Stamps")
        dialog.geometry("480x420")
        dialog.transient(self.root)
        dialog.grab_set()

        # Show canonical stamp + its catalog entries
        canon_row = self.conn.execute(
            "SELECT denomination, description, date_issued FROM Stamps WHERE id=?",
            (self.current_stamp_id,)).fetchone()
        canon_cats = self.conn.execute(
            "SELECT catalog_system, catalog_edition, catalog_number "
            "FROM Catalog_Numbers WHERE stamp_id=? "
            "ORDER BY catalog_system, catalog_number",
            (self.current_stamp_id,)).fetchall()
        canon_cat_str = "  ".join(
            f"{r['catalog_system']}"
            f"{'('+r['catalog_edition']+')' if r['catalog_edition'] else ''}"
            f" #{r['catalog_number']}"
            for r in canon_cats[:8]
        )
        if len(canon_cats) > 8:
            canon_cat_str += f"  +{len(canon_cats)-8} more"

        header = tk.Frame(dialog, bg="#E8F0FE", bd=1, relief=tk.SOLID)
        header.pack(fill=tk.X, padx=10, pady=(10, 4))
        tk.Label(header,
                 text=f"\u2605 KEEP THIS (canonical):  "
                      f"{canon_row['denomination'] or ''}  "
                      f"{canon_row['date_issued'] or ''}  "
                      f"{canon_row['description'] or ''}",
                 font=("", 10, "bold"), fg="#003366",
                 bg="#E8F0FE", anchor=tk.W).pack(
            fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(header,
                 text=f"      {canon_cat_str}" if canon_cat_str else "      (no catalog entries yet)",
                 font=("Courier", 9), fg="#333",
                 bg="#E8F0FE", anchor=tk.W).pack(
            fill=tk.X, padx=8, pady=(0, 6))

        tk.Label(dialog,
                 text="Check stamps to absorb into the canonical "
                      "(their catalog entries will move over, then they are deleted):",
                 wraplength=460, justify=tk.LEFT).pack(
            anchor=tk.W, padx=10, pady=(0, 6))

        # Scrollable checklist
        outer = tk.Frame(dialog)
        outer.pack(fill=tk.BOTH, expand=True, padx=10)
        canvas = tk.Canvas(outer, borderwidth=0)
        vsb = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        check_vars = {}
        for row in others:
            # Get catalog entries for this stamp
            cats = self.conn.execute(
                "SELECT catalog_system, catalog_edition, catalog_number "
                "FROM Catalog_Numbers WHERE stamp_id=? "
                "ORDER BY catalog_system, catalog_number",
                (row['id'],)).fetchall()
            cat_count = len(cats)

            # Build compact catalog summary (e.g. "Scott #1  SG #1  Yvert #1")
            cat_summary = "  ".join(
                f"{r['catalog_system']}"
                f"{'('+r['catalog_edition']+')' if r['catalog_edition'] else ''}"
                f" #{r['catalog_number']}"
                for r in cats[:6]  # cap at 6 to avoid overflow
            )
            if cat_count > 6:
                cat_summary += f"  +{cat_count - 6} more"

            var = tk.BooleanVar()
            check_vars[row['id']] = var

            # Main line
            main_label = (f"ID {row['id']:>5}  "
                          f"{row['denomination'] or '':>6}  "
                          f"{row['date_issued'] or '':<8}  "
                          f"{row['description'] or ''}")

            # Frame per stamp so catalog line indents neatly
            item_frame = tk.Frame(inner)
            item_frame.pack(anchor=tk.W, fill=tk.X, pady=1)
            tk.Checkbutton(item_frame, text=main_label, variable=var,
                           anchor=tk.W).pack(anchor=tk.W)
            if cat_summary:
                tk.Label(item_frame,
                         text=f"      {cat_summary}",
                         font=("Courier", 12), fg="#555").pack(anchor=tk.W)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        def do_merge():
            to_merge = [sid for sid, v in check_vars.items() if v.get()]
            if not to_merge:
                messagebox.showwarning("Nothing Selected",
                                       "Check at least one stamp to merge.")
                return
            if not messagebox.askyesno(
                    "Confirm Merge",
                    f"Move all catalog entries from {len(to_merge)} stamp(s) "
                    f"into stamp ID {self.current_stamp_id}, "
                    f"then delete the merged stamps?\n\nThis cannot be undone."):
                return

            moved = 0
            for sid in to_merge:
                # Move catalog numbers — skip duplicates silently
                rows = self.conn.execute(
                    "SELECT catalog_system, catalog_edition, catalog_number, "
                    "       described_color, catalog_notes "
                    "FROM Catalog_Numbers WHERE stamp_id=?", (sid,)).fetchall()
                for r in rows:
                    try:
                        self.conn.execute(
                            "INSERT INTO Catalog_Numbers "
                            "(stamp_id, catalog_system, catalog_edition, "
                            " catalog_number, described_color, catalog_notes) "
                            "VALUES (?,?,?,?,?,?)",
                            (self.current_stamp_id,
                             r['catalog_system'], r['catalog_edition'],
                             r['catalog_number'], r['described_color'],
                             r['catalog_notes']))
                        moved += 1
                    except sqlite3.IntegrityError:
                        pass  # duplicate — already on canonical
                self.conn.execute(
                    "DELETE FROM Catalog_Numbers WHERE stamp_id=?", (sid,))
                self.conn.execute(
                    "DELETE FROM Stamps WHERE id=?", (sid,))

            self.conn.commit()
            dialog.destroy()
            self._load_stamps(self._current_country)
            self._load_catalog_numbers(self.current_stamp_id)
            messagebox.showinfo("Merged",
                                f"Merged {len(to_merge)} stamp(s). "
                                f"{moved} catalog entries moved.")

        btn_bar = tk.Frame(dialog)
        btn_bar.pack(fill=tk.X, padx=10, pady=8)
        tk.Button(btn_bar, text="Merge Selected", command=do_merge,
                  font=("", 14, "bold")).pack(side=tk.LEFT)
        tk.Button(btn_bar, text="Cancel",
                  command=dialog.destroy).pack(side=tk.RIGHT)

    def _on_close(self):
        self.conn.close()
        self.root.destroy()

    def run(self):
        """Enter the Tk main loop (standalone mode only)."""
        if self._standalone:
            self.root.mainloop()


# ── Standalone entry point ────────────────────────────────────────

if __name__ == "__main__":
    StampCatalogManager().run()
