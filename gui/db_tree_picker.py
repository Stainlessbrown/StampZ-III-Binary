"""
db_tree_picker.py — Collapsible tree picker for Color Analysis databases.

Opens as a modal dialog showing databases organised into user-defined groups.
Groups are collapsed by default; click the arrow to expand.
Right-click a database to move it to a group or create a new group.
Double-click (or Enter) to select a database.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


class DBTreePickerDialog:
    """
    Modal dialog with a collapsible ttk.Treeview for selecting a database.

    Usage:
        picker = DBTreePickerDialog(parent, groups_manager, all_db_names)
        selected = picker.result   # None if cancelled
    """

    def __init__(self, parent, groups_manager, all_db_names, title="Select Database"):
        self.result = None
        self.groups_manager = groups_manager
        self.all_db_names = all_db_names

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("380x480")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_ui()
        self._populate_tree()

        # Centre over parent
        self.dialog.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{px}+{py}")

        self.dialog.wait_window()

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # Search bar
        search_frame = ttk.Frame(self.dialog)
        search_frame.pack(fill=tk.X, padx=8, pady=(8, 2))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._populate_tree())
        ttk.Entry(search_frame, textvariable=self._search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0)
        )

        # Tree + scrollbar
        frame = ttk.Frame(self.dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.tree = ttk.Treeview(frame, selectmode="browse", show="tree")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_enter)
        self.tree.bind("<Button-2>", self._on_right_click)   # macOS
        self.tree.bind("<Button-3>", self._on_right_click)   # Windows/Linux
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Selected item feedback
        self._selected_label_var = tk.StringVar(value="Nothing selected")
        ttk.Label(
            self.dialog,
            textvariable=self._selected_label_var,
            foreground="darkblue",
            font=("Arial", 9, "italic")
        ).pack(pady=(0, 2))
        ttk.Label(
            self.dialog,
            text="Single-click to select  •  Double-click to open  •  Expand folder first",
            foreground="gray"
        ).pack(pady=(0, 4))

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="New Group…", command=self._new_group).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Assign to Group…", command=self._assign_selected_to_group).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Select", command=self._confirm_selection).pack(side=tk.RIGHT, padx=4)

    # ── Tree Population ────────────────────────────────────────────────────

    def _populate_tree(self):
        """Rebuild the tree, applying any active search filter."""
        query = self._search_var.get().strip().lower()

        # Remember which groups were open
        expanded = {
            self.tree.item(iid, "text")
            for iid in self.tree.get_children()
            if self.tree.item(iid, "open")
        }

        self.tree.delete(*self.tree.get_children())

        display = self.groups_manager.build_display_order(self.all_db_names)

        for group, members in display.items():
            filtered = [m for m in members if query in m.lower()] if query else members
            if not filtered and query:
                continue
            group_iid = self.tree.insert(
                "", "end", text=f"📁  {group}",
                open=(group in expanded or bool(query))
            )
            for db in filtered:
                self.tree.insert(group_iid, "end", text=db, tags=("db",))

        # If searching, expand all
        if query:
            for iid in self.tree.get_children():
                self.tree.item(iid, open=True)

    # ── Selection Handling ─────────────────────────────────────────────────

    def _on_tree_select(self, event):
        """Update the selected label when tree selection changes."""
        db = self._get_selected_db()
        if db:
            self._selected_label_var.set(f"Selected: {db}")
        else:
            self._selected_label_var.set("Nothing selected (expand a folder and click a database)")

    def _get_selected_db(self):
        """Return the selected database name, or None if a group folder is selected."""
        # Try tree selection first, then focused item
        sel = self.tree.selection()
        item = sel[0] if sel else self.tree.focus()
        if not item:
            return None
        # DB items have a parent group node; group nodes have no parent
        parent = self.tree.parent(item)
        if parent:  # has parent = it's a DB item, not a group folder
            return self.tree.item(item, "text")
        return None

    def _confirm_selection(self):
        db = self._get_selected_db()
        if db:
            self.result = db
            self.dialog.destroy()
        else:
            messagebox.showwarning(
                "No Selection",
                "Please select a database (not a group folder).",
                parent=self.dialog
            )

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item and "db" in self.tree.item(item, "tags"):
            self.result = self.tree.item(item, "text")
            self.dialog.destroy()

    def _on_enter(self, event):
        self._confirm_selection()

    # ── Right-click Context Menu ───────────────────────────────────────────

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)

        is_db = "db" in self.tree.item(item, "tags")
        is_group = not is_db

        menu = tk.Menu(self.dialog, tearoff=0)

        if is_db:
            db_name = self.tree.item(item, "text")
            current_group = self.groups_manager.get_group_for(db_name)
            menu.add_command(
                label="Move to Group…",
                command=lambda: self._move_to_group(db_name)
            )
            if current_group and current_group != "Ungrouped":
                menu.add_command(
                    label="Remove from Group",
                    command=lambda: self._remove_from_group(db_name)
                )

        if is_group:
            group_name = self.tree.item(item, "text").replace("📁  ", "")
            if group_name != "Ungrouped":
                menu.add_command(
                    label="Rename Group…",
                    command=lambda: self._rename_group(group_name)
                )
                menu.add_command(
                    label="Delete Group",
                    command=lambda: self._delete_group(group_name)
                )

        menu.tk_popup(event.x_root, event.y_root)

    # ── Group Management Actions ───────────────────────────────────────────

    def _new_group(self):
        name = simpledialog.askstring(
            "New Group", "Group name:", parent=self.dialog
        )
        if name and name.strip():
            section = self.groups_manager._data.setdefault("color_analysis", {})
            if name.strip() not in section:
                section[name.strip()] = []
            self.groups_manager._save()
            self._populate_tree()

    def _assign_selected_to_group(self):
        """Assign the currently selected database to a group."""
        db = self._get_selected_db()
        if not db:
            messagebox.showinfo(
                "No Database Selected",
                "Please click a database name first, then click Assign to Group.",
                parent=self.dialog
            )
            return
        self._move_to_group(db)

    def _move_to_group(self, db_name: str):
        groups = self.groups_manager.get_sorted_groups()
        if not groups:
            messagebox.showinfo(
                "No Groups",
                "No groups exist yet. Use 'New Group\u2026' to create one first.",
                parent=self.dialog
            )
            return

        # Show a listbox of existing groups
        win = tk.Toplevel(self.dialog)
        win.title(f"Assign '{db_name}' to Group")
        win.geometry("300x230")
        win.transient(self.dialog)
        win.grab_set()
        win.resizable(False, False)

        ttk.Label(win, text=f"Choose group for:").pack(padx=10, pady=(10, 0))
        ttk.Label(win, text=db_name, font=("Arial", 10, "bold")).pack(padx=10, pady=(0, 6))

        lb_frame = ttk.Frame(win)
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        lb = tk.Listbox(lb_frame, selectmode=tk.SINGLE, height=7)
        for g in groups:
            lb.insert(tk.END, g)
        lb.pack(fill=tk.BOTH, expand=True)
        lb.selection_set(0)

        def confirm():
            sel = lb.curselection()
            if sel:
                chosen = groups[sel[0]]
                self.groups_manager.set_group(db_name, chosen)
                self._populate_tree()
            win.destroy()

        lb.bind("<Double-1>", lambda e: confirm())
        btn_f = ttk.Frame(win)
        btn_f.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btn_f, text="Assign", command=confirm).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_f, text="Cancel", command=win.destroy).pack(side=tk.RIGHT)
        win.wait_window()

    def _remove_from_group(self, db_name: str):
        self.groups_manager.remove_from_group(db_name)
        self._populate_tree()

    def _rename_group(self, old_name: str):
        new_name = simpledialog.askstring(
            "Rename Group", f"New name for '{old_name}':",
            initialvalue=old_name, parent=self.dialog
        )
        if new_name and new_name.strip() and new_name.strip() != old_name:
            self.groups_manager.rename_group(old_name, new_name.strip())
            self._populate_tree()

    def _delete_group(self, group_name: str):
        if messagebox.askyesno(
            "Delete Group",
            f"Delete group '{group_name}'?\n"
            "Databases in this group will move to Ungrouped.",
            parent=self.dialog
        ):
            self.groups_manager.delete_group(group_name)
            self._populate_tree()
