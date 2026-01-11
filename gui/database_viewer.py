#!/usr/bin/env python3
"""Database viewer for StampZ color analysis data."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sqlite3
import csv
import shutil
from typing import Optional, List, Dict
from datetime import datetime

class DatabaseViewer:
    """GUI for viewing and managing color analysis database entries."""
    
    def __init__(self, parent: tk.Tk):
        # Store parent reference
        self.parent = parent
        """Initialize the database viewer window.
        
        Args:
            parent: Parent tkinter window
        """
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("StampZ Database Viewer")
        
        # Set size and position
        dialog_width = 2000
        dialog_height = 600
        
        # Get screen dimensions
        screen_width = parent.winfo_screenwidth()
        screen_height = parent.winfo_screenheight()
        
        # Calculate position
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        self.dialog.minsize(800, 500)
        
        # Configure as independent window
        self.dialog.wm_transient(None)  # Make window independent
        self.dialog.attributes('-topmost', False)  # Allow window to go behind other windows
        
        # Initialize variables
        self.current_sample_set = None
        self.measurements = []
        self.selected_items = set()
        
        # Column visibility state - True means visible
        self.column_visibility = {
            "set_id": False,           # Hidden by default
            "image_name": True,        # Always visible
            "measurement_date": False, # Hidden by default
            "point": False,            # Hidden by default
            "l_value": True,           # Visible by default
            "a_value": True,           # Visible by default
            "b_value": True,           # Visible by default
            "rgb_r": True,             # Visible by default
            "rgb_g": True,             # Visible by default
            "rgb_b": True,             # Visible by default
            "x_pos": False,            # Hidden by default
            "y_pos": False,            # Hidden by default
            "shape": False,            # Hidden by default
            "size": False,             # Hidden by default
            "notes": False             # Hidden by default
        }
        
        self._create_widgets()
        self._load_sample_sets()
    
    def _create_widgets(self):
        """Create and arrange the GUI widgets."""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Data source selector at the very top
        source_frame = ttk.Frame(main_frame)
        source_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(source_frame, text="Data Source:").pack(side=tk.LEFT, padx=(0, 5))
        self.data_source = tk.StringVar(value="color_analysis")
        ttk.Radiobutton(source_frame, text="Color Analysis", variable=self.data_source, 
                       value="color_analysis", command=self._on_source_changed).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(source_frame, text="Color Libraries", variable=self.data_source, 
                       value="color_libraries", command=self._on_source_changed).pack(side=tk.LEFT, padx=5)
        
        # Top controls - two rows
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Top row - Sample set and basic controls
        top_row = ttk.Frame(controls_frame)
        top_row.pack(fill=tk.X, pady=(0, 5))
        
        # Bottom row - Filtering and sorting
        filter_frame = ttk.Frame(controls_frame)
        filter_frame.pack(fill=tk.X)
        
        # Filter controls
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        self.filter_combo = ttk.Combobox(filter_frame, values=['Set ID', 'Image Name', 'Date', 'Notes'], width=15)
        self.filter_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.filter_combo.set('Image Name')
        
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=20)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_var.trace('w', self._apply_filter)
        
        # Sort controls
        ttk.Label(filter_frame, text="Sort by:").pack(side=tk.LEFT, padx=(10, 5))
        self.sort_combo = ttk.Combobox(filter_frame, values=['Set ID', 'Image Name', 'Date', 'Point'], width=15)
        self.sort_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.sort_combo.set('Date')
        
        self.sort_order = tk.BooleanVar(value=False)  # False = descending (newest first)
        ttk.Radiobutton(filter_frame, text="Asc", variable=self.sort_order, value=True, command=self._apply_sort).pack(side=tk.LEFT)
        ttk.Radiobutton(filter_frame, text="Desc", variable=self.sort_order, value=False, command=self._apply_sort).pack(side=tk.LEFT, padx=(0, 10))
        
        # Sample set selection
        ttk.Label(controls_frame, text="Sample Set:").pack(side=tk.LEFT, padx=(0, 5))
        self.sample_set_combo = ttk.Combobox(controls_frame, state="readonly", width=30)
        self.sample_set_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.sample_set_combo.bind("<<ComboboxSelected>>", self._on_sample_set_changed)
        
        # Buttons
        ttk.Button(controls_frame, text="Columns...", command=self._toggle_columns).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Refresh", command=self._refresh_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Export CSV", command=self._export_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Import CSV", command=self._import_from_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Manage Backups", command=self._manage_backups).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Delete Selected", command=self._delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Clear All", command=self._clear_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Delete Database", command=self._delete_sample_set).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Manage Templates", command=self._open_template_manager).pack(side=tk.LEFT, padx=5)
        
        # Create treeview with scrollbars
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        self.tree = ttk.Treeview(tree_frame, selectmode="extended")
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.tree.grid(column=0, row=0, sticky="nsew")
        vsb.grid(column=1, row=0, sticky="ns")
        hsb.grid(column=0, row=1, sticky="ew")
        
        # Configure grid weights
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        # Configure treeview columns
        columns = [
            "set_id", "image_name", "measurement_date", "point", "l_value", "a_value", "b_value",
            "rgb_r", "rgb_g", "rgb_b", "x_pos", "y_pos",
            "shape", "size", "notes"
        ]
        
        self.tree["columns"] = columns
        self.tree["show"] = "headings"  # Hide the first empty column
        
        # Configure column headings and widths
        self.column_configs = {
            "set_id": ("Set ID", 20),
            "image_name": ("Image", 80),
            "measurement_date": ("Date/Time", 130),
            "point": ("Point", 50),
            "l_value": ("L*", 30),
            "a_value": ("a*", 30),
            "b_value": ("b*", 30),
            "rgb_r": ("R", 30),
            "rgb_g": ("G", 30),
            "rgb_b": ("B", 30),
            "x_pos": ("X", 30),
            "y_pos": ("Y", 30),
            "shape": ("Shape", 40),
            "size": ("Size", 20),
            "notes": ("Notes", 640)
        }
        
        for col, (heading, width) in self.column_configs.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, minwidth=50)
        
        # Set initial displaycolumns based on visibility
        self._update_displayed_columns()
        
        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        
        # Status bar
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))
    
    def _load_sample_sets(self):
        """Load available databases into the combobox based on selected data source."""
        try:
            from utils.path_utils import get_color_analysis_dir, get_color_libraries_dir
            
            if self.data_source.get() == "color_analysis":
                from utils.color_analysis_db import ColorAnalysisDB
                data_dir = get_color_analysis_dir()
                databases = ColorAnalysisDB.get_all_sample_set_databases(data_dir)
                source_type = "sample sets"
            else:  # color_libraries
                data_dir = get_color_libraries_dir()
                if os.path.exists(data_dir):
                    # Color libraries have different naming - look for _library.db files
                    databases = []
                    for f in os.listdir(data_dir):
                        if f.endswith('_library.db'):
                            # Remove _library.db suffix to get library name
                            databases.append(f[:-11])
                        elif f.endswith('.db') and not f.endswith('_library.db'):
                            # Also include other .db files without suffix
                            databases.append(f[:-3])
                else:
                    databases = []
                source_type = "color libraries"
            
            print(f"DEBUG: Loading {source_type} from: {data_dir}")
            print(f"DEBUG: Found {len(databases)} {source_type}: {databases}")
            
            if databases:
                self.sample_set_combo["values"] = databases
                self.sample_set_combo.set(databases[0])
                self._on_sample_set_changed(None)  # Load first database
            else:
                # Clear the dropdown and show appropriate message
                self.sample_set_combo["values"] = []
                self.sample_set_combo.set("")
                self.current_sample_set = None
                # Clear any existing data in the tree
                self.tree.delete(*self.tree.get_children())
                self.status_var.set(f"No {source_type} found. Please run color analysis first.")
        
        except Exception as e:
            print(f"DEBUG: Error loading sample sets: {str(e)}")
            messagebox.showerror("Error", f"Failed to load sample sets: {str(e)}")
    
    def _on_source_changed(self):
        """Handle data source change."""
        self._load_sample_sets()
        # Update column headings based on source
        if self.data_source.get() == "color_libraries":
            self.tree.heading("image_name", text="Color Name")
            self.tree.heading("measurement_date", text="")
            self.tree.heading("point", text="")
        else:
            self.tree.heading("image_name", text="Image")
            self.tree.heading("measurement_date", text="Date/Time")
            self.tree.heading("point", text="Point")
    
    def _on_sample_set_changed(self, event):
        """Handle database selection change."""
        selected = self.sample_set_combo.get()
        if selected:
            self.current_sample_set = selected
            self._refresh_data()
    
    def _apply_filter(self, *args):
        """Apply the current filter to the displayed data."""
        filter_text = self.filter_var.get().strip().lower()
        filter_field = self.filter_combo.get()
        
        # Show all items if filter is empty
        if not filter_text:
            for item in self.tree.get_children():
                self.tree.reattach(item, '', 'end')
            return
        
        # Map combo selection to column index
        field_map = {
            'Set ID': 0,
            'Image Name': 1,
            'Date': 2,
            'Notes': 14  # Adjust based on your column indices
        }
        
        col_idx = field_map.get(filter_field, 1)  # Default to Image Name
        
        # Hide items that don't match filter
        for item in self.tree.get_children():
            value = str(self.tree.item(item)['values'][col_idx]).lower()
            if filter_text not in value:
                self.tree.detach(item)
            else:
                self.tree.reattach(item, '', 'end')
        
        self._apply_sort()  # Maintain sort order after filtering
    
    def _apply_sort(self):
        """Sort the currently visible items."""
        sort_field = self.sort_combo.get()
        ascending = self.sort_order.get()
        
        # Map combo selection to column index
        # Define columns list at class level for consistent reference
        columns = [
            "set_id", "image_name", "measurement_date", "point", "l_value", "a_value", "b_value",
            "rgb_r", "rgb_g", "rgb_b", "x_pos", "y_pos", "shape", "size", "notes"
        ]
        
        field_map = {
            'Set ID': 0,  # set_id column index
            'Image Name': 1,  # image_name column index
            'Date': 2,  # measurement_date column index
            'Point': 3  # point column index
        }
        
        col_idx = field_map.get(sort_field, 2)  # Default to Date
        
        # Get all visible items
        items = [(self.tree.item(item)['values'][col_idx], item) for item in self.tree.get_children()]
        
        # Sort items
        items.sort(reverse=not ascending)
        
        # Rearrange items in the tree
        for idx, (_, item) in enumerate(items):
            self.tree.move(item, '', idx)
    
    def _refresh_data(self):
        """Refresh the treeview with current database data."""
        if not self.current_sample_set:
            return
        
        try:
            # Clear existing items
            self.tree.delete(*self.tree.get_children())
            
            # Get current directory
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            if self.data_source.get() == "color_analysis":
                from utils.color_analysis_db import ColorAnalysisDB
                db = ColorAnalysisDB(self.current_sample_set)
                self.measurements = db.get_all_measurements()
                
                # Add to treeview
                for measurement in self.measurements:
                    # Map data to correct columns based on column definitions
                    # columns = ["set_id", "image_name", "measurement_date", "point", "l_value", "a_value", "b_value",
                    #           "rgb_r", "rgb_g", "rgb_b", "x_pos", "y_pos", "shape", "size", "notes"]
                    # Check if this is an averaged measurement and format point display accordingly
                    coordinate_point = measurement.get('coordinate_point', '')
                    is_averaged = measurement.get('is_averaged', False)
                    
                    # Format the point column to show "AVERAGE" instead of "999"
                    if coordinate_point == 999 or is_averaged:
                        point_display = "AVERAGE"
                    else:
                        point_display = str(coordinate_point)
                    
                    values = [
                        measurement.get('set_id', ''),           # set_id column
                        measurement.get('image_name', ''),       # image_name column 
                        measurement.get('measurement_date', ''), # measurement_date column
                        point_display,                           # point column - show "AVERAGE" for 999/averaged
                        f"{measurement.get('l_value', 0):.3f}",  # l_value column
                        f"{measurement.get('a_value', 0):.3f}",  # a_value column
                        f"{measurement.get('b_value', 0):.3f}",  # b_value column
                        f"{measurement.get('rgb_r', 0):.2f}",    # rgb_r column
                        f"{measurement.get('rgb_g', 0):.2f}",    # rgb_g column
                        f"{measurement.get('rgb_b', 0):.2f}",    # rgb_b column
                        f"{measurement.get('x_position', 0):.1f}", # x_pos column
                        f"{measurement.get('y_position', 0):.1f}", # y_pos column
                        measurement.get('sample_type', ''),      # shape column
                        measurement.get('sample_size', ''),      # size column
                        measurement.get('notes', '')             # notes column
                    ]
                    # Use measurement ID as the item ID for easier deletion
                    item_id = measurement.get('id', '')
                    self.tree.insert('', 'end', iid=str(item_id), values=values)
                
                self.status_var.set(f"Loaded {len(self.measurements)} measurements from {self.current_sample_set}")
            
            else:  # color_libraries
                from utils.path_utils import get_color_libraries_dir
                data_dir = get_color_libraries_dir()
                
                # Try different naming conventions for color libraries
                db_path = None
                if os.path.exists(os.path.join(data_dir, f"{self.current_sample_set}_library.db")):
                    db_path = os.path.join(data_dir, f"{self.current_sample_set}_library.db")
                elif os.path.exists(os.path.join(data_dir, f"{self.current_sample_set}.db")):
                    db_path = os.path.join(data_dir, f"{self.current_sample_set}.db")
                
                if not db_path or not os.path.exists(db_path):
                    raise Exception(f"Database file not found: {self.current_sample_set}")
                if os.path.getsize(db_path) == 0:
                    raise Exception(f"Database file is empty: {self.current_sample_set}\nTry creating a color library first.")
                
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    # First get the table name
                    cursor.execute("SELECT * FROM library_colors")
                    colors = cursor.fetchall()
                    
                    for color in colors:
                        # Adjust these indices based on your color library schema
                        values = [
                            color[0],  # ID
                            color[1],  # Name
                            color[11],  # date_added
                            "",  # No point number
                            f"{float(color[3]):.3f}",  # lab_l
                            f"{float(color[4]):.3f}",  # lab_a
                            f"{float(color[5]):.3f}",  # lab_b
                            f"{float(color[6]):.2f}",  # rgb_r
                            f"{float(color[7]):.2f}",  # rgb_g
                            f"{float(color[8]):.2f}",  # rgb_b
                            "",  # No position
                            "",
                            "",  # No shape
                            "",  # No size
                            color[12] if color[12] else ""  # notes
                        ]
                        self.tree.insert('', 'end', values=values)
                    
                    self.status_var.set(f"Loaded {len(colors)} colors from {self.current_sample_set}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")
    
    def _on_selection_changed(self, event):
        """Handle treeview selection changes."""
        self.selected_items = set(self.tree.selection())
        num_selected = len(self.selected_items)
        self.status_var.set(f"Selected {num_selected} item{'s' if num_selected != 1 else ''}")
    
    def _clear_all_data(self):
        """Clear all data from the current database."""
        if not self.current_sample_set:
            messagebox.showinfo("No Database Selected", "Please select a database first")
            return
        
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if self.data_source.get() == "color_analysis":
            if not messagebox.askyesno("Confirm Clear All",
                                      f"Clear ALL measurements from {self.current_sample_set}?\n\n"
                                      "This action cannot be undone."):
                return
            
            try:
                from utils.color_analysis_db import ColorAnalysisDB
                db = ColorAnalysisDB(self.current_sample_set)
                if db.clear_all_measurements():
                    self._refresh_data()
                    messagebox.showinfo("Success", "All measurements cleared from database")
                else:
                    messagebox.showerror("Error", "Failed to clear measurements")
            
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear measurements: {str(e)}")
        
        else:  # color_libraries
            if not messagebox.askyesno("Confirm Delete Library",
                                      f"Delete color library '{self.current_sample_set}'?\n\n"
                                      "This action cannot be undone."):
                return
            
            try:
                db_path = os.path.join(current_dir, "data", "color_libraries", self.current_sample_set)
                if os.path.exists(db_path):
                    os.remove(db_path)
                self._load_sample_sets()  # Refresh the database list
                messagebox.showinfo("Success", f"Color library '{self.current_sample_set}' has been deleted")
            
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete color library: {str(e)}")

    def _delete_sample_set(self):
        """Delete the entire sample set database and its related coordinate template."""
        if not self.current_sample_set:
            messagebox.showinfo("No Sample Set Selected", "Please select a sample set first")
            return
        
        if self.data_source.get() == "color_analysis":
            if not messagebox.askyesno("⚠️ WARNING: PERMANENT DATABASE DELETION",
                                      f"You are about to PERMANENTLY DELETE the entire database:\n"
                                      f"'{self.current_sample_set}'\n\n"
                                      "This will delete:\n"
                                      "• All color measurements\n"
                                      "• The sample set database file\n"
                                      "• The coordinate template (if it exists)\n\n"
                                      "⚠️ THIS ACTION IS PERMANENT AND CANNOT BE UNDONE!\n\n"
                                      "Are you absolutely sure you want to proceed?",
                                      icon='warning'):
                return
            
            try:
                from utils.color_analysis_db import ColorAnalysisDB
                from utils.coordinate_db import CoordinateDB
                from utils.path_utils import get_color_analysis_dir
                
                # Delete the color analysis database file
                data_dir = get_color_analysis_dir()
                db_path = os.path.join(data_dir, f"{self.current_sample_set}.db")
                
                if os.path.exists(db_path):
                    os.remove(db_path)
                    print(f"DEBUG: Deleted color analysis database: {db_path}")
                
                # Also try to delete the coordinate template
                try:
                    coord_db = CoordinateDB()
                    if coord_db.delete_coordinate_set(self.current_sample_set):
                        print(f"DEBUG: Deleted coordinate template: {self.current_sample_set}")
                    else:
                        print(f"DEBUG: No coordinate template found for: {self.current_sample_set}")
                except Exception as coord_e:
                    print(f"DEBUG: Error deleting coordinate template: {coord_e}")
                    # Don't fail the whole operation if coordinate deletion fails
                
                # Refresh the sample set list
                self._load_sample_sets()
                messagebox.showinfo("Success", 
                                   f"Sample set '{self.current_sample_set}' has been completely deleted.\n\n"
                                   "This included the color measurements database and coordinate template.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete sample set: {str(e)}")
        
        else:  # color_libraries
            if not messagebox.askyesno("⚠️ WARNING: PERMANENT LIBRARY DELETION",
                                      f"You are about to PERMANENTLY DELETE the entire library:\n"
                                      f"'{self.current_sample_set}'\n\n"
                                      "This will permanently delete the entire library file.\n\n"
                                      "⚠️ THIS ACTION IS PERMANENT AND CANNOT BE UNDONE!\n\n"
                                      "Are you absolutely sure you want to proceed?",
                                      icon='warning'):
                return
            
            try:
                from utils.path_utils import get_color_libraries_dir
                data_dir = get_color_libraries_dir()
                
                # Try different naming conventions for color libraries
                db_path = None
                if os.path.exists(os.path.join(data_dir, f"{self.current_sample_set}_library.db")):
                    db_path = os.path.join(data_dir, f"{self.current_sample_set}_library.db")
                elif os.path.exists(os.path.join(data_dir, f"{self.current_sample_set}.db")):
                    db_path = os.path.join(data_dir, f"{self.current_sample_set}.db")
                
                if db_path and os.path.exists(db_path):
                    os.remove(db_path)
                    print(f"DEBUG: Deleted color library: {db_path}")
                
                # Refresh the sample set list
                self._load_sample_sets()
                messagebox.showinfo("Success", f"Color library '{self.current_sample_set}' has been deleted")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete color library: {str(e)}")
    
    def _open_template_manager(self):
        """Open the Template Manager window."""
        from gui.template_manager import TemplateManager
        TemplateManager(self.parent)
    
    def _delete_selected(self):
        """Delete selected items from database."""
        if not self.selected_items:
            messagebox.showinfo("No Selection", "Please select items to delete")
            return
        
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if self.data_source.get() == "color_analysis":
            if not messagebox.askyesno("Confirm Delete",
                                      f"Delete {len(self.selected_items)} selected measurements?\n\n"
                                      "This action cannot be undone."):
                return
            
            try:
                from utils.color_analysis_db import ColorAnalysisDB
                db = ColorAnalysisDB(self.current_sample_set)
                
                # Get the IDs of selected items (using item IIDs which are the database IDs)
                selected_ids = list(self.selected_items)
                
                # Delete from database
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.cursor()
                    deleted_count = 0
                    for measurement_id in selected_ids:
                        print(f"DEBUG: Attempting to delete measurement with ID: {measurement_id}")
                        cursor.execute(
                            "DELETE FROM color_measurements WHERE id = ?",
                            (measurement_id,)
                        )
                        deleted_count += cursor.rowcount
                        print(f"DEBUG: Rows affected: {cursor.rowcount}")
                    conn.commit()
                    print(f"DEBUG: Total deleted rows: {deleted_count}")
                    
                    if deleted_count == 0:
                        messagebox.showwarning("Delete Warning", 
                                             f"No rows were deleted. The selected items may no longer exist in the database.")
                        self._refresh_data()  # Refresh to show current state
                        return
                
                # Refresh display
                self._refresh_data()
                messagebox.showinfo("Success", f"Deleted {len(selected_ids)} measurements")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete measurements: {str(e)}")
        
        else:  # color_libraries
            if not messagebox.askyesno("Confirm Delete",
                                      f"Delete {len(self.selected_items)} selected colors?\n\n"
                                      "This action cannot be undone."):
                return
            
            try:
                db_path = os.path.join(current_dir, "data", "color_libraries", self.current_sample_set)
                
                # Get the IDs of selected items
                selected_ids = []
                for item_id in self.selected_items:
                    values = self.tree.item(item_id)['values']
                    if values:
                        selected_ids.append(values[0])  # First column is ID
                
                # Delete from database
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    for color_id in selected_ids:
                        cursor.execute(
                            "DELETE FROM library_colors WHERE id = ?",
                            (color_id,)
                        )
                    conn.commit()
                
                # Refresh display
                self._refresh_data()
                messagebox.showinfo("Success", f"Deleted {len(selected_ids)} colors")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete colors: {str(e)}")
    
    def _export_to_csv(self):
        """Export current database view to CSV file."""
        if not self.current_sample_set:
            messagebox.showinfo("No Database Selected", "Please select a database first")
            return
        
        try:
            # Get suggested filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{self.current_sample_set}_{timestamp}.csv"
            
            # Ask user for save location
            filepath = filedialog.asksaveasfilename(
                title="Export Database to CSV",
                defaultextension=".csv",
                filetypes=[
                    ('CSV files', '*.csv'),
                    ('All files', '*.*')
                ],
                initialfile=default_filename
            )
            
            if not filepath:
                return
            
            # Export based on data source
            if self.data_source.get() == "color_analysis":
                success = self._export_color_analysis_to_csv(filepath)
            else:  # color_libraries
                success = self._export_color_library_to_csv(filepath)
            
            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Database exported successfully!\n\n"
                    f"File: {os.path.basename(filepath)}\n\n"
                    f"You can now edit this file in a spreadsheet application \n"
                    f"and reimport it using the 'Import CSV' button."
                )
            else:
                messagebox.showerror("Export Failed", "Failed to export database to CSV")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export database:\n\n{str(e)}")
    
    def _export_color_analysis_to_csv(self, filepath: str) -> bool:
        """Export color analysis database to CSV (respects normalization preference)."""
        try:
            from utils.color_analysis_db import ColorAnalysisDB
            db = ColorAnalysisDB(self.current_sample_set)
            measurements = db.get_all_measurements()
            
            if not measurements:
                messagebox.showinfo("No Data", "No measurements found to export")
                return False
            
            # Check user preferences for normalization
            try:
                from utils.user_preferences import get_preferences_manager
                prefs = get_preferences_manager()
                use_normalized = prefs.get_export_normalized_values()
            except:
                use_normalized = False
            
            # Define CSV headers based on normalization preference
            if use_normalized:
                headers = [
                    'id', 'set_id', 'image_name', 'measurement_date', 'coordinate_point',
                    'l_norm', 'a_norm', 'b_norm', 'r_norm', 'g_norm', 'b_norm_rgb',
                    'x_position', 'y_position', 'sample_type', 'sample_size', 'notes', 'is_averaged'
                ]
            else:
                headers = [
                    'id', 'set_id', 'image_name', 'measurement_date', 'coordinate_point',
                    'l_value', 'a_value', 'b_value', 'rgb_r', 'rgb_g', 'rgb_b',
                    'x_position', 'y_position', 'sample_type', 'sample_size', 'notes', 'is_averaged'
                ]
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                
                for measurement in measurements:
                    # Get values from database
                    l_val = measurement.get('l_value', 0) or 0
                    a_val = measurement.get('a_value', 0) or 0
                    b_val = measurement.get('b_value', 0) or 0
                    r_val = measurement.get('rgb_r', 0) or 0
                    g_val = measurement.get('rgb_g', 0) or 0
                    b_rgb = measurement.get('rgb_b', 0) or 0
                    
                    # Detect if data is ALREADY normalized (0-1 range) vs raw
                    # Plot_3D imports SHOULD be converted to raw, but legacy data might be stored normalized
                    is_already_normalized = False
                    if l_val <= 1.0 and abs(a_val) <= 1.0 and abs(b_val) <= 1.0:
                        # Values are in 0-1 range, likely already normalized
                        is_already_normalized = True
                    
                    if use_normalized:
                        if is_already_normalized:
                            # Data is already in 0-1 range, use as-is (legacy Plot_3D import)
                            l_norm = round(l_val, 4)
                            a_norm = round(a_val, 4)
                            b_norm = round(b_val, 4)
                            r_norm = round(r_val, 4)
                            g_norm = round(g_val, 4)
                            b_rgb_norm = round(b_rgb, 4)
                        else:
                            # Normalize raw values for Plot_3D compatibility (0-1 range)
                            # L*: 0-100 → 0-1
                            l_norm = round(l_val / 100.0, 4) if l_val else 0.0
                            # a*, b*: -128 to +127 → 0-1
                            a_norm = round((a_val + 128.0) / 255.0, 4)
                            b_norm = round((b_val + 128.0) / 255.0, 4)
                            # RGB: 0-255 → 0-1
                            r_norm = round(r_val / 255.0, 4) if r_val else 0.0
                            g_norm = round(g_val / 255.0, 4) if g_val else 0.0
                            b_rgb_norm = round(b_rgb / 255.0, 4) if b_rgb else 0.0
                        
                        row = [
                            measurement.get('id', ''),
                            measurement.get('set_id', ''),
                            measurement.get('image_name', ''),
                            measurement.get('measurement_date', ''),
                            measurement.get('coordinate_point', ''),
                            l_norm,
                            a_norm,
                            b_norm,
                            r_norm,
                            g_norm,
                            b_rgb_norm,
                            measurement.get('x_position', ''),
                            measurement.get('y_position', ''),
                            measurement.get('sample_type', ''),
                            measurement.get('sample_size', ''),
                            measurement.get('notes', ''),
                            measurement.get('is_averaged', '')
                        ]
                    else:
                        # Export raw values
                        row = [
                            measurement.get('id', ''),
                            measurement.get('set_id', ''),
                            measurement.get('image_name', ''),
                            measurement.get('measurement_date', ''),
                            measurement.get('coordinate_point', ''),
                            l_val,
                            a_val,
                            b_val,
                            r_val,
                            g_val,
                            b_rgb,
                            measurement.get('x_position', ''),
                            measurement.get('y_position', ''),
                            measurement.get('sample_type', ''),
                            measurement.get('sample_size', ''),
                            measurement.get('notes', ''),
                            measurement.get('is_averaged', '')
                        ]
                    
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Error exporting color analysis to CSV: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _export_color_library_to_csv(self, filepath: str) -> bool:
        """Export color library database to CSV."""
        try:
            from utils.color_library import ColorLibrary
            library = ColorLibrary(self.current_sample_set)
            colors = library.get_all_colors()
            
            if not colors:
                messagebox.showinfo("No Data", "No colors found to export")
                return False
            
            # Use the same format as ColorLibrary.export_library method
            headers = ['name', 'description', 'lab_l', 'lab_a', 'lab_b', 'category', 'source', 'notes']
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                
                for color in colors:
                    row = [
                        color.name,
                        color.description,
                        color.lab[0],  # L*
                        color.lab[1],  # a*
                        color.lab[2],  # b*
                        color.category,
                        color.source,
                        color.notes or ''
                    ]
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Error exporting color library to CSV: {e}")
            return False
    
    def _import_from_csv(self):
        """Import CSV data back into the database with validation and safety checks."""
        if not self.current_sample_set:
            messagebox.showinfo("No Database Selected", "Please select a database first")
            return
        
        try:
            # Ask user to select CSV file
            filepath = filedialog.askopenfilename(
                title="Import CSV to Database",
                filetypes=[
                    ('CSV files', '*.csv'),
                    ('All files', '*.*')
                ]
            )
            
            if not filepath:
                return
            
            # Show import options dialog
            import_options = self._show_import_options_dialog()
            if not import_options:
                return
            
            # Create backup before import if requested
            backup_path = None
            if import_options['create_backup']:
                backup_path = self._create_database_backup()
                if not backup_path:
                    messagebox.showerror("Backup Failed", "Could not create backup. Import cancelled.")
                    return
            
            # Import based on data source
            if self.data_source.get() == "color_analysis":
                success = self._import_color_analysis_from_csv(filepath, import_options)
            else:  # color_libraries
                success = self._import_color_library_from_csv(filepath, import_options)
            
            if success:
                self._refresh_data()
                backup_msg = f"\n\nBackup created: {os.path.basename(backup_path)}" if backup_path else ""
                messagebox.showinfo(
                    "Import Successful",
                    f"CSV data imported successfully!{backup_msg}\n\n"
                    f"Database has been updated with the imported data."
                )
            else:
                messagebox.showerror("Import Failed", "Failed to import CSV data")
                
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV data:\n\n{str(e)}")
    
    def _show_import_options_dialog(self) -> Optional[Dict]:
        """Show dialog for import options."""
        dialog = tk.Toplevel(self.dialog)
        dialog.title("Import Options")
        dialog.geometry("400x300")
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+{}+{}".format(
            self.dialog.winfo_rootx() + 50,
            self.dialog.winfo_rooty() + 50
        ))
        
        # Variables for options
        create_backup = tk.BooleanVar(value=True)
        replace_mode = tk.StringVar(value="replace")
        validate_data = tk.BooleanVar(value=True)
        
        result = {}
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Import CSV Options", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Backup option
        backup_frame = ttk.LabelFrame(main_frame, text="Safety", padding="5")
        backup_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(backup_frame, text="Create backup before import (recommended)", 
                       variable=create_backup).pack(anchor=tk.W)
        
        # Replace mode
        mode_frame = ttk.LabelFrame(main_frame, text="Import Mode", padding="5")
        mode_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(mode_frame, text="Replace existing data", variable=replace_mode, 
                       value="replace").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Append to existing data", variable=replace_mode, 
                       value="append").pack(anchor=tk.W)
        
        # Validation option
        validation_frame = ttk.LabelFrame(main_frame, text="Validation", padding="5")
        validation_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(validation_frame, text="Validate data before import", 
                       variable=validate_data).pack(anchor=tk.W)
        
        # Info text
        info_text = (
            "• Replace mode will clear existing data first\n"
            "• Append mode will add to existing data\n"
            "• Validation checks for data format and ranges"
        )
        ttk.Label(main_frame, text=info_text, font=("Arial", 9), foreground="gray").pack(pady=10)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def on_import():
            result.update({
                'create_backup': create_backup.get(),
                'replace_mode': replace_mode.get(),
                'validate_data': validate_data.get()
            })
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(button_frame, text="Import", command=on_import).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return result if result else None
    
    def _create_database_backup(self) -> Optional[str]:
        """Create a backup of the current database."""
        try:
            if self.data_source.get() == "color_analysis":
                from utils.path_utils import get_color_analysis_dir
                source_dir = get_color_analysis_dir()
                source_file = os.path.join(source_dir, f"{self.current_sample_set}.db")
            else:  # color_libraries
                from utils.path_utils import get_color_libraries_dir
                source_dir = get_color_libraries_dir()
                # Try different naming conventions
                source_file = None
                if os.path.exists(os.path.join(source_dir, f"{self.current_sample_set}_library.db")):
                    source_file = os.path.join(source_dir, f"{self.current_sample_set}_library.db")
                elif os.path.exists(os.path.join(source_dir, f"{self.current_sample_set}.db")):
                    source_file = os.path.join(source_dir, f"{self.current_sample_set}.db")
                
                if not source_file:
                    raise Exception(f"Database file not found: {self.current_sample_set}")
            
            if not os.path.exists(source_file):
                raise Exception(f"Database file not found: {source_file}")
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{os.path.basename(source_file)}.backup_{timestamp}"
            backup_path = os.path.join(source_dir, backup_filename)
            
            # Copy the file
            shutil.copy2(source_file, backup_path)
            
            print(f"Created backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def _import_color_analysis_from_csv(self, filepath: str, options: Dict) -> bool:
        """Import color analysis data from CSV."""
        try:
            # Validate CSV format first
            if options['validate_data'] and not self._validate_color_analysis_csv(filepath):
                return False
            
            from utils.color_analysis_db import ColorAnalysisDB
            db = ColorAnalysisDB(self.current_sample_set)
            
            # Clear existing data if replace mode
            if options['replace_mode'] == 'replace':
                if not db.clear_all_measurements():
                    raise Exception("Failed to clear existing measurements")
            
            # Read and import CSV data
            with open(filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                imported_count = 0
                # Track measurement sets to create them as needed
                created_sets = {}
                
                for row in reader:
                    # Skip empty rows
                    if not any(row.values()):
                        continue
                    
                    try:
                        # Handle set_id - create measurement set if needed
                        image_name = row.get('image_name', 'Imported_Image')
                        set_id = row.get('set_id')
                        
                        if set_id:
                            set_id = int(set_id)
                            # Create measurement set if not exists (keyed by image_name)
                            if image_name not in created_sets:
                                existing_set_id = db.create_measurement_set(image_name, "Imported from CSV")
                                created_sets[image_name] = existing_set_id
                            # Use the actual set_id from the created/existing set
                            actual_set_id = created_sets[image_name]
                        else:
                            # No set_id in CSV, create one
                            if image_name not in created_sets:
                                actual_set_id = db.create_measurement_set(image_name, "Imported from CSV")
                                created_sets[image_name] = actual_set_id
                            else:
                                actual_set_id = created_sets[image_name]
                        
                        # Import measurement (without image_name parameter)
                        success = db.save_color_measurement(
                            set_id=actual_set_id,
                            coordinate_point=int(row['coordinate_point']) if row.get('coordinate_point') else 1,
                            x_pos=float(row['x_position']) if row.get('x_position') else 0,
                            y_pos=float(row['y_position']) if row.get('y_position') else 0,
                            l_value=float(row['l_value']),
                            a_value=float(row['a_value']),
                            b_value=float(row['b_value']),
                            rgb_r=float(row['rgb_r']),
                            rgb_g=float(row['rgb_g']),
                            rgb_b=float(row['rgb_b']),
                            sample_type=row.get('sample_type', 'circle'),
                            sample_size=row.get('sample_size', '10x10'),
                            sample_anchor=row.get('sample_anchor', 'center'),
                            notes=row.get('notes', '')
                        )
                        
                        if success:
                            imported_count += 1
                            print(f"Successfully imported row {imported_count}: {image_name}, point {row.get('coordinate_point')}")
                        else:
                            print(f"Failed to save measurement for row: {row}")
                    except (ValueError, TypeError) as e:
                        print(f"Error importing row: {e}")
                        print(f"Row data: {row}")
                        print(f"Problematic values - set_id: {row.get('set_id')}, coord_point: {row.get('coordinate_point')}")
                        continue
                    except Exception as e:
                        print(f"Unexpected error importing row: {e}")
                        print(f"Row data: {row}")
                        continue
            
            print(f"Import complete: {imported_count} measurements imported successfully")
            if imported_count == 0:
                print("No measurements were imported. Check the CSV format and data.")
            return imported_count > 0
            
        except Exception as e:
            print(f"Error importing color analysis from CSV: {e}")
            return False
    
    def _import_color_library_from_csv(self, filepath: str, options: Dict) -> bool:
        """Import color library data from CSV."""
        try:
            # Validate CSV format first
            if options['validate_data'] and not self._validate_color_library_csv(filepath):
                return False
            
            from utils.color_library import ColorLibrary
            library = ColorLibrary(self.current_sample_set)
            
            # For color libraries, we use the existing import_library method
            # which handles replace vs append logic
            replace_existing = (options['replace_mode'] == 'replace')
            
            imported_count = library.import_library(
                filename=filepath,
                replace_existing=replace_existing
            )
            
            return imported_count > 0
            
        except Exception as e:
            print(f"Error importing color library from CSV: {e}")
            return False
    
    def _validate_color_analysis_csv(self, filepath: str) -> bool:
        """Validate color analysis CSV format."""
        try:
            required_headers = ['l_value', 'a_value', 'b_value', 'rgb_r', 'rgb_g', 'rgb_b']
            recommended_headers = ['image_name', 'coordinate_point', 'x_position', 'y_position']
            
            with open(filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                headers = reader.fieldnames
                
                print(f"CSV headers found: {headers}")
                
                # Check for required headers
                missing_headers = [h for h in required_headers if h not in headers]
                if missing_headers:
                    messagebox.showerror(
                        "Invalid CSV Format",
                        f"Missing required columns:\n\n{', '.join(missing_headers)}\n\n"
                        f"Required columns: {', '.join(required_headers)}"
                    )
                    return False
                
                # Warn about missing recommended headers
                missing_recommended = [h for h in recommended_headers if h not in headers]
                if missing_recommended:
                    if not messagebox.askyesno(
                        "Missing Recommended Columns",
                        f"The following recommended columns are missing:\n\n{', '.join(missing_recommended)}\n\n"
                        f"This may result in incomplete data import. Continue anyway?"
                    ):
                        return False
                
                # Validate a few rows for data format
                row_count = 0
                for row in reader:
                    if row_count >= 5:  # Check first 5 rows
                        break
                    
                    try:
                        # Try to convert numeric values
                        float(row['l_value'])
                        float(row['a_value']) 
                        float(row['b_value'])
                        float(row['rgb_r'])
                        float(row['rgb_g'])
                        float(row['rgb_b'])
                        
                        # Validate optional numeric fields if present
                        if row.get('x_position'):
                            float(row['x_position'])
                        if row.get('y_position'):
                            float(row['y_position'])
                        if row.get('coordinate_point'):
                            int(row['coordinate_point'])
                        
                        row_count += 1
                    except (ValueError, KeyError) as e:
                        messagebox.showerror(
                            "Invalid Data Format",
                            f"Invalid numeric data in row {row_count + 2}:\n\n{str(e)}"
                        )
                        return False
            
            print(f"CSV validation passed for {row_count} sample rows")
            return True
            
        except Exception as e:
            messagebox.showerror("Validation Error", f"Failed to validate CSV:\n\n{str(e)}")
            return False
    
    def _validate_color_library_csv(self, filepath: str) -> bool:
        """Validate color library CSV format."""
        try:
            required_headers = ['name', 'lab_l', 'lab_a', 'lab_b']
            
            with open(filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                headers = reader.fieldnames
                
                # Check for required headers
                missing_headers = [h for h in required_headers if h not in headers]
                if missing_headers:
                    messagebox.showerror(
                        "Invalid CSV Format",
                        f"Missing required columns:\n\n{', '.join(missing_headers)}\n\n"
                        f"Required columns: {', '.join(required_headers)}"
                    )
                    return False
                
                # Validate a few rows
                row_count = 0
                for row in reader:
                    if row_count >= 5:  # Check first 5 rows
                        break
                    
                    try:
                        # Check name is not empty
                        if not row['name'].strip():
                            raise ValueError("Empty color name")
                        
                        # Try to convert Lab values
                        float(row['lab_l'])
                        float(row['lab_a']) 
                        float(row['lab_b'])
                        row_count += 1
                    except (ValueError, KeyError) as e:
                        messagebox.showerror(
                            "Invalid Data Format",
                            f"Invalid data in row {row_count + 2}:\n\n{str(e)}"
                        )
                        return False
            
            return True
            
        except Exception as e:
            messagebox.showerror("Validation Error", f"Failed to validate CSV:\n\n{str(e)}")
            return False
    
    def _manage_backups(self):
        """Show backup management dialog to view and delete backup files."""
        try:
            # Get backup files for current database
            backup_files = self._get_backup_files()
            
            if not backup_files:
                messagebox.showinfo(
                    "No Backups Found",
                    "No backup files found for the current database."
                )
                return
            
            # Create backup management dialog
            dialog = tk.Toplevel(self.dialog)
            dialog.title("Backup Management")
            dialog.geometry("600x400")
            dialog.transient(self.dialog)
            dialog.grab_set()
            
            # Center the dialog
            dialog.geometry("+{}+{}".format(
                self.dialog.winfo_rootx() + 100,
                self.dialog.winfo_rooty() + 100
            ))
            
            # Main frame
            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_text = f"Backup files for: {self.current_sample_set}"
            ttk.Label(main_frame, text=title_text, font=("Arial", 12, "bold")).pack(pady=(0, 10))
            
            # Info label
            info_text = (
                "Backup files are created automatically before CSV imports.\n"
                "You can safely delete old backups to save disk space."
            )
            ttk.Label(main_frame, text=info_text, font=("Arial", 9)).pack(pady=(0, 10))
            
            # Listbox frame with scrollbar
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            # Listbox for backup files
            backup_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, font=("Arial", 10))
            backup_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=backup_listbox.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            backup_listbox.config(yscrollcommand=scrollbar.set)
            
            # Populate listbox with backup files (newest first)
            backup_files.sort(key=lambda x: x['timestamp'], reverse=True)
            for backup in backup_files:
                display_text = f"{backup['filename']} ({backup['size']}) - {backup['date']}"
                backup_listbox.insert(tk.END, display_text)
            
            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            def delete_selected_backups():
                selected_indices = backup_listbox.curselection()
                if not selected_indices:
                    messagebox.showinfo("No Selection", "Please select backup files to delete.")
                    return
                
                selected_files = [backup_files[i] for i in selected_indices]
                file_list = "\n".join([f"• {f['filename']}" for f in selected_files])
                
                if messagebox.askyesno(
                    "Confirm Delete",
                    f"Delete {len(selected_files)} backup file(s)?\n\n{file_list}\n\n"
                    "This action cannot be undone."
                ):
                    deleted_count = 0
                    for backup_file in selected_files:
                        try:
                            os.remove(backup_file['full_path'])
                            deleted_count += 1
                            print(f"Deleted backup: {backup_file['filename']}")
                        except Exception as e:
                            print(f"Error deleting {backup_file['filename']}: {e}")
                    
                    if deleted_count > 0:
                        messagebox.showinfo(
                            "Delete Complete",
                            f"Successfully deleted {deleted_count} backup file(s)."
                        )
                        dialog.destroy()
                    else:
                        messagebox.showerror("Delete Failed", "No backup files were deleted.")
            
            def delete_all_backups():
                if messagebox.askyesno(
                    "Confirm Delete All",
                    f"Delete ALL {len(backup_files)} backup files for {self.current_sample_set}?\n\n"
                    "This action cannot be undone."
                ):
                    deleted_count = 0
                    for backup_file in backup_files:
                        try:
                            os.remove(backup_file['full_path'])
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting {backup_file['filename']}: {e}")
                    
                    messagebox.showinfo(
                        "Delete Complete",
                        f"Successfully deleted {deleted_count} backup file(s)."
                    )
                    dialog.destroy()
            
            def restore_backup():
                selected_indices = backup_listbox.curselection()
                if len(selected_indices) != 1:
                    messagebox.showinfo("Selection Error", "Please select exactly one backup file to restore.")
                    return
                
                backup_file = backup_files[selected_indices[0]]
                
                if messagebox.askyesno(
                    "Confirm Restore",
                    f"Restore backup: {backup_file['filename']}?\n\n"
                    "This will replace the current database with the backup.\n"
                    "Current data will be lost unless you create a backup first."
                ):
                    try:
                        # Get current database path
                        current_db_path = self._get_current_database_path()
                        if not current_db_path:
                            messagebox.showerror("Error", "Could not determine current database path.")
                            return
                        
                        # Copy backup over current database
                        shutil.copy2(backup_file['full_path'], current_db_path)
                        
                        # Refresh the display
                        self._refresh_data()
                        
                        messagebox.showinfo(
                            "Restore Complete",
                            f"Successfully restored backup: {backup_file['filename']}\n\n"
                            "The database has been updated."
                        )
                        dialog.destroy()
                        
                    except Exception as e:
                        messagebox.showerror(
                            "Restore Failed",
                            f"Failed to restore backup:\n\n{str(e)}"
                        )
            
            # Buttons
            ttk.Button(button_frame, text="Delete Selected", command=delete_selected_backups).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Delete All", command=delete_all_backups).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Restore Selected", command=restore_backup).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to manage backups:\n\n{str(e)}")
    
    def _get_backup_files(self) -> List[Dict]:
        """Get list of backup files for current database."""
        try:
            backup_files = []
            
            if self.data_source.get() == "color_analysis":
                from utils.path_utils import get_color_analysis_dir
                data_dir = get_color_analysis_dir()
                db_filename = f"{self.current_sample_set}.db"
            else:  # color_libraries
                from utils.path_utils import get_color_libraries_dir
                data_dir = get_color_libraries_dir()
                # Try different naming conventions
                if os.path.exists(os.path.join(data_dir, f"{self.current_sample_set}_library.db")):
                    db_filename = f"{self.current_sample_set}_library.db"
                else:
                    db_filename = f"{self.current_sample_set}.db"
            
            if not os.path.exists(data_dir):
                return backup_files
            
            # Find backup files
            backup_pattern = f"{db_filename}.backup_"
            for filename in os.listdir(data_dir):
                if filename.startswith(backup_pattern):
                    full_path = os.path.join(data_dir, filename)
                    
                    # Extract timestamp from filename
                    timestamp_str = filename[len(backup_pattern):]
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        # Fallback to file modification time
                        timestamp = datetime.fromtimestamp(os.path.getmtime(full_path))
                        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Get file size
                    size_bytes = os.path.getsize(full_path)
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                    
                    backup_files.append({
                        'filename': filename,
                        'full_path': full_path,
                        'timestamp': timestamp,
                        'date': date_str,
                        'size': size_str
                    })
            
            return backup_files
            
        except Exception as e:
            print(f"Error getting backup files: {e}")
            return []
    
    def _get_current_database_path(self) -> Optional[str]:
        """Get the path to the current database file."""
        try:
            if self.data_source.get() == "color_analysis":
                from utils.path_utils import get_color_analysis_dir
                data_dir = get_color_analysis_dir()
                return os.path.join(data_dir, f"{self.current_sample_set}.db")
            else:  # color_libraries
                from utils.path_utils import get_color_libraries_dir
                data_dir = get_color_libraries_dir()
                # Try different naming conventions
                if os.path.exists(os.path.join(data_dir, f"{self.current_sample_set}_library.db")):
                    return os.path.join(data_dir, f"{self.current_sample_set}_library.db")
                else:
                    return os.path.join(data_dir, f"{self.current_sample_set}.db")
                    
        except Exception as e:
            print(f"Error getting current database path: {e}")
            return None
    
    def _update_displayed_columns(self):
        """Update the treeview to show/hide columns based on visibility settings."""
        # Build list of visible columns in order
        visible_cols = []
        for col in self.tree["columns"]:
            if self.column_visibility.get(col, True):  # Default to True if not in dict
                visible_cols.append(col)
        
        # Update the treeview's displaycolumns
        self.tree["displaycolumns"] = visible_cols
    
    def _toggle_columns(self):
        """Open dialog to toggle column visibility."""
        dialog = tk.Toplevel(self.dialog)
        dialog.title("Column Visibility")
        dialog.geometry("350x450")
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+{}+{}".format(
            self.dialog.winfo_rootx() + 50,
            self.dialog.winfo_rooty() + 50
        ))
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Column Visibility", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Info text
        ttk.Label(main_frame, text="Select which columns to display:", font=("Arial", 9), foreground="gray").pack(pady=(0, 10))
        
        # Scrollable frame for checkboxes
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create checkboxes for each column (except image_name which is always visible)
        checkbox_vars = {}
        column_labels = {
            "set_id": "Set ID",
            "measurement_date": "Date/Time",
            "point": "Point",
            "l_value": "L* (Lightness)",
            "a_value": "a* (Red-Green)",
            "b_value": "b* (Yellow-Blue)",
            "rgb_r": "R (Red)",
            "rgb_g": "G (Green)",
            "rgb_b": "B (Blue)",
            "x_pos": "X Position",
            "y_pos": "Y Position",
            "shape": "Shape Type",
            "size": "Sample Size",
            "notes": "Notes"
        }
        
        for col, label in column_labels.items():
            checkbox_vars[col] = tk.BooleanVar(value=self.column_visibility[col])
            ttk.Checkbutton(
                scrollable_frame,
                text=label,
                variable=checkbox_vars[col]
            ).pack(anchor=tk.W, padx=10, pady=3)
        
        # Pack scrollable area
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def apply_visibility():
            # Update visibility settings
            for col, var in checkbox_vars.items():
                self.column_visibility[col] = var.get()
            
            # Update displayed columns in treeview
            self._update_displayed_columns()
            
            dialog.destroy()
        
        def reset_defaults():
            # Reset to default visibility
            for col in checkbox_vars.keys():
                if col in ["l_value", "a_value", "b_value", "rgb_r", "rgb_g", "rgb_b", "image_name"]:
                    checkbox_vars[col].set(True)
                else:
                    checkbox_vars[col].set(False)
        
        ttk.Button(button_frame, text="Apply", command=apply_visibility).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Reset to Defaults", command=reset_defaults).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
