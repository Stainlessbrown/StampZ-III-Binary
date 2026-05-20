#!/usr/bin/env python3
"""
Stamp Catalog Manager for StampZ-III.

Opens as a Toplevel window from within StampZ (or standalone).
Provides a full data-entry UI for the three-table catalog database:
  Directory  → countries
  Stamps     → one row per physical stamp (shared fields)
  Catalog_Numbers → per-catalog cross-references
"""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import os

DB_PATH = os.path.expanduser("~/Desktop/StampZ_Interface.db")

STAMP_TYPES = [
    'Definitive', 'Commemorative', 'Airmail',
    'Postage Due', 'Fiscal', 'Semi-Postal', 'Official', 'General'
]

CATALOG_SYSTEMS = [
    'Scott', 'SG', 'Michel', 'Yvert', 'Sassone',
    'AFA', 'FACIT', 'Zumstein', 'Minkus', 'Maury'
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

        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

        self.current_stamp_id = None
        self._stamp_ids = []
        self._all_countries = []

        self._build_ui()
        self._load_countries()

        if not self._standalone:
            # Keep on top of parent and clean up DB on close
            self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        # ── Country / filter bar ──────────────────────────────────
        top = tk.Frame(self.root, pady=6, padx=8, bg="#f0f0f0")
        top.pack(fill=tk.X)

        tk.Label(top, text="Country:", font=("", 12, "bold"),
                 bg="#f0f0f0").pack(side=tk.LEFT)
        self.country_var = tk.StringVar()
        self.country_combo = ttk.Combobox(
            top, textvariable=self.country_var, width=36, state="readonly")
        self.country_combo.pack(side=tk.LEFT, padx=6)
        self.country_combo.bind("<<ComboboxSelected>>", self._on_country_select)

        tk.Label(top, text="  Filter:", bg="#f0f0f0").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace("w", self._filter_countries)
        tk.Entry(top, textvariable=self.filter_var, width=16).pack(
            side=tk.LEFT, padx=2)

        # ── Main pane ─────────────────────────────────────────────
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                              sashwidth=5, sashrelief=tk.RAISED)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # ── Left: stamp list ──────────────────────────────────────
        left = tk.Frame(main, width=240)
        main.add(left, minsize=200)

        tk.Label(left, text="Stamps", font=("", 10, "bold")).pack(
            anchor=tk.W, pady=(4, 0))

        # Search box
        search_row = tk.Frame(left)
        search_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(search_row, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_stamps)
        tk.Entry(search_row, textvariable=self.search_var,
                 width=18).pack(side=tk.LEFT, padx=2)
        tk.Button(search_row, text="✕", width=2,
                  command=lambda: self.search_var.set("")).pack(side=tk.LEFT)

        list_frame = tk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.stamp_list = tk.Listbox(list_frame, selectmode=tk.SINGLE,
                                     activestyle="dotbox",
                                     font=("Courier", 10))
        sb = tk.Scrollbar(list_frame, orient=tk.VERTICAL,
                          command=self.stamp_list.yview)
        self.stamp_list.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.stamp_list.pack(fill=tk.BOTH, expand=True)
        self.stamp_list.bind("<<ListboxSelect>>", self._on_stamp_select)

        btn_row = tk.Frame(left)
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(btn_row, text="+ New",
                  command=self._new_stamp,
                  font=("", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(btn_row, text="Duplicate",
                  command=self._duplicate_stamp).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(btn_row, text="Delete",
                  command=self._delete_stamp,
                  font=("", 10, "bold")).pack(side=tk.LEFT)

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
            ("Color",          "color_var",          "entry", None),
            ("Perf",           "perf_var",           "entry", None),
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
        self.notes_text = tk.Text(detail, width=32, height=3, font=("", 10))
        self.notes_text.grid(row=len(fields), column=1,
                             sticky=tk.W, padx=4, pady=2)

        # Save button
        tk.Button(right, text="  Save Stamp  ",
                  command=self._save_stamp,
                  font=("", 11, "bold"), relief=tk.RAISED,
                  padx=10, pady=4).pack(pady=6)

        # ── Catalog numbers ───────────────────────────────────────
        cat_frame = tk.LabelFrame(right, text="Catalog Numbers",
                                  padx=6, pady=6)
        cat_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        cols = ("System", "Number", "Notes")
        self.cat_tree = ttk.Treeview(cat_frame, columns=cols,
                                     show="headings", height=5)
        self.cat_tree.heading("System", text="Catalog System")
        self.cat_tree.heading("Number", text="Number")
        self.cat_tree.heading("Notes",  text="Notes")
        self.cat_tree.column("System", width=140)
        self.cat_tree.column("Number", width=100)
        self.cat_tree.column("Notes",  width=200)

        cat_sb = tk.Scrollbar(cat_frame, orient=tk.VERTICAL,
                              command=self.cat_tree.yview)
        self.cat_tree.config(yscrollcommand=cat_sb.set)
        cat_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cat_tree.pack(fill=tk.BOTH, expand=True)

        # Checkbox grid for catalog system selection
        cb_frame = tk.Frame(cat_frame)
        cb_frame.pack(fill=tk.X, pady=(6, 2))
        tk.Label(cb_frame, text="Systems:",
                 font=("", 9, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 6))

        self.cat_system_vars = {}
        for i, system in enumerate(CATALOG_SYSTEMS):
            var = tk.BooleanVar()
            self.cat_system_vars[system] = var
            row_num = i // 5
            col_num = (i % 5) + 1
            tk.Checkbutton(cb_frame, text=system, variable=var).grid(
                row=row_num, column=col_num, sticky=tk.W, padx=4)

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
                  font=("", 10, "bold")).pack(side=tk.LEFT, padx=(6, 2))
        tk.Button(add_row, text="Remove Selected",
                  command=self._remove_catalog_number).pack(side=tk.LEFT)

    # ── Country loading & filtering ───────────────────────────────

    def _load_countries(self):
        cur = self.conn.execute(
            "SELECT Country FROM Directory ORDER BY Country")
        self._all_countries = [r[0] for r in cur.fetchall()]
        self.country_combo["values"] = self._all_countries

    def _filter_countries(self, *args):
        term = self.filter_var.get().lower()
        filtered = [c for c in self._all_countries if term in c.lower()]
        self.country_combo["values"] = filtered
        if filtered:
            self.country_combo.set(filtered[0])
            self._load_stamps(filtered[0])
            self._clear_form()

    # ── Stamp list ────────────────────────────────────────────────

    def _on_country_select(self, event=None):
        self.search_var.set("")
        self._load_stamps(self.country_var.get())
        self._clear_form()

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
                "  OR date_issued LIKE ?) "
                "ORDER BY id",
                (country, term, term, term))
        else:
            cur = self.conn.execute(
                "SELECT id, denomination, description, date_issued "
                "FROM Stamps WHERE country=? ORDER BY id",
                (country,))

        for row in cur.fetchall():
            denom = row["denomination"] or ""
            desc  = row["description"]  or ""
            year  = row["date_issued"]  or ""
            label = f"{row['id']:>5}  {denom:>6}  {year:<6}  {desc}"
            self.stamp_list.insert(tk.END, label)
            self._stamp_ids.append(row["id"])

    def _filter_stamps(self, *args):
        country = self.country_var.get()
        if not country:
            return
        self._load_stamps(country, self.search_var.get())
        self._clear_form()

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
        self.field_vars["color_var"].set(row["color"] or "")
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
            "SELECT catalog_system, catalog_number, catalog_notes "
            "FROM Catalog_Numbers WHERE stamp_id=? "
            "ORDER BY catalog_system", (stamp_id,))
        for row in cur.fetchall():
            self.cat_tree.insert("", tk.END, values=(
                row["catalog_system"],
                row["catalog_number"],
                row["catalog_notes"] or ""))

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
        if not self.country_var.get():
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
        country = self.country_var.get()
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
            "color":          self.field_vars["color_var"].get() or None,
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
                        denomination=:denomination, color=:color,
                        perf=:perf, description=:description, notes=:notes
                    WHERE id=:id
                """, {**data, "id": self.current_stamp_id})
                self.conn.commit()
            else:
                cur = self.conn.execute("""
                    INSERT INTO Stamps
                        (country, stamp_type, date_issued, date_withdrawn,
                         denomination, color, perf, description, notes)
                    VALUES
                        (:country, :stamp_type, :date_issued, :date_withdrawn,
                         :denomination, :color, :perf, :description, :notes)
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
        self._load_stamps(self.country_var.get(), self.search_var.get())

    def _add_catalog_number(self):
        if not self.current_stamp_id:
            messagebox.showwarning(
                "Save First",
                "Please save the stamp before adding catalog numbers.")
            return
        checked = [s for s, v in self.cat_system_vars.items() if v.get()]
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
        system, number = str(values[0]), str(values[1])
        if not messagebox.askyesno("Confirm", f"Remove {system} #{number}?"):
            return
        self.conn.execute(
            "DELETE FROM Catalog_Numbers "
            "WHERE stamp_id=? AND catalog_system=? AND catalog_number=?",
            (self.current_stamp_id, system, number))
        self.conn.commit()
        self._load_catalog_numbers(self.current_stamp_id)

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
