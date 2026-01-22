import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Rectangle

from utils.data_file_manager import get_data_file_manager, DataFormat


class TernaryPlotWindow:
    """Simple ternary plot window with a side panel and convex hull toggle."""

    def __init__(self, parent=None):
        self.parent = parent
        # Create as a child window so it stays owned by the app
        self.root = tk.Toplevel(parent) if isinstance(parent, (tk.Tk, tk.Toplevel)) else tk.Toplevel()
        self.root.title("Ternary Plot")
        self.root.geometry("1400x900")
        try:
            self.root.attributes('-topmost', False)
        except Exception:
            pass

        # State
        self.df = pd.DataFrame(columns=['L*', 'a*', 'b*', 'DataID', 'Marker', 'Color'])
        self.show_hull = tk.BooleanVar(value=False)
        self.show_grid = tk.BooleanVar(value=True)
        self.use_rgb_labels = tk.BooleanVar(value=False)  # False = L*a*b*, True = RGB
        self.zoom_level = tk.DoubleVar(value=1.0)  # Zoom level for markers
        self.manager = get_data_file_manager()
        self.current_database = tk.StringVar(value="No database loaded")
        self.current_database_name = None  # Track actual database name for viewer
        self.current_sheet_name = None  # Track selected sheet name for multi-sheet files
        self.database_measurements = []  # Store raw database measurements for re-normalization
        self.data_source_type = None  # 'channel_rgb', 'channel_cmy', or 'color_analysis'
        
        # Point highlighting state
        self.plot_points = []  # Store plot coordinates for click detection
        self.highlighted_point = None  # Currently highlighted point index
        self.highlight_annotation = None  # Text annotation for highlighted point

        # Layout
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)

        self.side = ttk.Frame(container, width=260)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        self.main = ttk.Frame(container)
        self.main.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Controls
        self._build_side_panel()
        self._build_plot()

        # Initial empty plot
        self._render()

    def _build_side_panel(self):
        title = ttk.Label(self.side, text="Ternary Plot Controls", font=('Arial', 12, 'bold'))
        title.pack(anchor='w', pady=(0, 8))

        # Refresh data from current source (at top for easy access)
        ttk.Button(self.side, text="Refresh Data", command=self._refresh_data).pack(fill=tk.X, pady=4)
        
        ttk.Separator(self.side, orient='horizontal').pack(fill=tk.X, pady=4)
        
        # Open external file
        ttk.Button(self.side, text="Open Data (ODS/XLSX/CSV)", command=self._open_file).pack(fill=tk.X, pady=4)
        
        # Load from realtime database
        ttk.Button(self.side, text="Load from Realtime DB", command=self._load_from_realtime_db).pack(fill=tk.X, pady=4)
        
        # View current database
        ttk.Button(self.side, text="View Database Contents", command=self._view_database).pack(fill=tk.X, pady=4)

        # Current database indicator
        db_frame = ttk.LabelFrame(self.side, text="Current Database")
        db_frame.pack(fill=tk.X, pady=6)
        self.db_label = ttk.Label(db_frame, textvariable=self.current_database, 
                                 foreground='darkblue', font=('Arial', 9, 'bold'),
                                 wraplength=240)
        self.db_label.pack(anchor='w', padx=5, pady=3)
        
        # Display options
        options_frame = ttk.LabelFrame(self.side, text="Display Options")
        options_frame.pack(fill=tk.X, pady=6)
        ttk.Checkbutton(options_frame, text="Show Convex Hull", variable=self.show_hull, command=self._render).pack(anchor='w', padx=5, pady=2)
        ttk.Checkbutton(options_frame, text="Show Grid Lines", variable=self.show_grid, command=self._render).pack(anchor='w', padx=5, pady=2)
        # RGB toggle - will re-normalize data when changed
        self.rgb_toggle = ttk.Checkbutton(options_frame, text="Use RGB Data", variable=self.use_rgb_labels, command=self._on_data_type_toggle)
        self.rgb_toggle.pack(anchor='w', padx=5, pady=2)
        
        # Zoom control
        zoom_frame = ttk.Frame(options_frame)
        zoom_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(zoom_frame, text="Marker Size:").pack(side=tk.LEFT)
        zoom_scale = ttk.Scale(zoom_frame, from_=0.5, to=3.0, variable=self.zoom_level, 
                              orient=tk.HORIZONTAL, length=100, command=self._on_zoom_change)
        zoom_scale.pack(side=tk.LEFT, padx=(5,0))
        self.zoom_label = ttk.Label(zoom_frame, text=f"{self.zoom_level.get():.1f}x")
        self.zoom_label.pack(side=tk.LEFT, padx=(5,0))

        # Save plot image
        ttk.Button(self.side, text="Save Plot as PNG", command=self._save_png).pack(fill=tk.X, pady=8)

        ttk.Separator(self.side, orient='horizontal').pack(fill=tk.X, pady=8)
        ttk.Button(self.side, text="Exit", command=self.root.destroy).pack(fill=tk.X, pady=4)

        # Info
        info = (
            "Data Sources:\n"
            " - External files: ODS/XLSX/CSV\n"
            " - Realtime DB: Current session data\n\n"
            "Navigation:\n"
            " - Use toolbar: Pan, Zoom, Home, Back/Forward\n"
            " - Right Click points to highlight and show details\n\n"
            "Columns used:\n"
            " - L*, a*, b*, DataID, Marker, Color\n\n"
            "Notes:\n"
            " - Data normalized to sum=1 for ternary projection\n"
            " - Perfect for analyzing dense marker clusters"
        )
        ttk.Label(self.side, text=info, wraplength=240, foreground='gray').pack(anchor='w', pady=(10, 0))

    def _build_plot(self):
        self.fig = plt.Figure(figsize=(9.0, 8.5), facecolor='white')
        # Adjust subplot to use more of the figure area
        self.ax = self.fig.add_subplot(111)
        # Reduce margins to maximize plot area
        self.fig.subplots_adjust(left=0.05, right=0.95, top=0.90, bottom=0.10)  # Leave room for toolbar
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Add matplotlib navigation toolbar for pan/zoom
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.main)
        self.toolbar.update()
        
        # Bind click events for point highlighting
        self.canvas.mpl_connect('button_press_event', self._on_plot_click)
    
    def _on_zoom_change(self, value):
        """Handle zoom level changes."""
        self.zoom_label.config(text=f"{self.zoom_level.get():.1f}x")
        self._render()
    
    def _on_data_type_toggle(self):
        """Handle toggle between L*a*b* and RGB data for color analysis databases."""
        # Only re-normalize if we have color analysis data (which has both L*a*b* and RGB)
        if self.data_source_type == 'color_analysis' and self.database_measurements:
            print(f"DEBUG: Data type toggled to {'RGB' if self.use_rgb_labels.get() else 'L*a*b*'}")
            self._convert_measurements_to_dataframe()
            self._render()
        elif self.data_source_type in ['channel_rgb', 'channel_cmy']:
            # Channel data only has one data type - just re-render with same data
            print(f"DEBUG: Channel data ({self.data_source_type}) - toggle has no effect")
            self._render()
        else:
            # No data loaded yet - just re-render
            self._render()

    def _detect_data_source_type(self, measurements):
        """Detect whether database contains channel data or color analysis data."""
        if not measurements:
            return None
        
        # Sample first few measurements to determine type
        sample_size = min(10, len(measurements))
        
        channel_count = 0
        color_count = 0
        rgb_channel_count = 0
        cmy_channel_count = 0
        
        for m in measurements[:sample_size]:
            l_val = m.get('l_value', 0)
            sample_type = m.get('sample_type', '')
            
            if l_val == 0 or 'channel' in sample_type.lower():
                channel_count += 1
                # Distinguish RGB vs CMY by checking sample_type
                if 'rgb' in sample_type.lower():
                    rgb_channel_count += 1
                elif 'cmy' in sample_type.lower():
                    cmy_channel_count += 1
            else:
                color_count += 1
        
        # Determine type based on majority
        if channel_count > color_count:
            if cmy_channel_count > rgb_channel_count:
                return 'channel_cmy'
            else:
                return 'channel_rgb'
        else:
            return 'color_analysis'
    
    def _convert_measurements_to_dataframe(self):
        """Convert stored measurements to dataframe based on current toggle setting."""
        if not self.database_measurements:
            return
        
        df_data = []
        use_rgb = self.use_rgb_labels.get()
        
        for m in self.database_measurements:
            l_val = m.get('l_value', 50)
            a_val = m.get('a_value', 0)
            b_val = m.get('b_value', 0)
            sample_type = m.get('sample_type', '')
            
            # Detect if this is channel data
            is_channel = (l_val == 0 or 'channel' in sample_type.lower())
            
            if is_channel:
                # Channel data - always use RGB values (which contain R/G/B or C/M/Y)
                l_val = m.get('rgb_r', 0)
                a_val = m.get('rgb_g', 0)
                b_val = m.get('rgb_b', 0)
            elif use_rgb and self.data_source_type == 'color_analysis':
                # Color analysis with RGB toggle ON - use RGB values
                l_val = m.get('rgb_r', 0)
                a_val = m.get('rgb_g', 0)
                b_val = m.get('rgb_b', 0)
            else:
                # Color analysis with L*a*b* selected (default) - use L*a*b* values
                # Check if values are normalized and convert if needed
                if 0 <= l_val <= 1:
                    l_val = l_val * 100
                if -1 <= a_val <= 1:
                    a_val = a_val * 128
                if -1 <= b_val <= 1:
                    b_val = b_val * 128
            
            df_data.append({
                'L*': l_val,
                'a*': a_val,
                'b*': b_val,
                'DataID': m.get('image_name', '') + f"_pt{m.get('coordinate_point', '')}",
                'Marker': m.get('marker_preference', '.'),
                'Color': m.get('color_preference', 'blue')
            })
        
        self.df = pd.DataFrame(df_data)
        print(f"DEBUG: Converted {len(df_data)} measurements to dataframe (RGB mode: {use_rgb}, source type: {self.data_source_type})")
    
    def _ask_sheet_selection(self, sheet_names):
        """Ask user to select a sheet from a multi-sheet file.
        
        Args:
            sheet_names: List of available sheet names
            
        Returns:
            Selected sheet name, or None if cancelled
        """
        if not sheet_names:
            return None
        
        # If only one sheet, return it automatically
        if len(sheet_names) == 1:
            return sheet_names[0]
        
        print(f"Creating sheet selection dialog for {len(sheet_names)} sheets")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Sheet")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Add heading
        heading = tk.Label(dialog, 
                          text=f"This file contains {len(sheet_names)} sheets.\nWhich sheet would you like to open?", 
                          font=("Arial", 11, "bold"),
                          justify=tk.LEFT)
        heading.pack(pady=15, padx=10)
        
        # Variable to store selection
        result = tk.StringVar(value="")
        
        # Create scrollable listbox for sheet names
        list_frame = tk.Frame(dialog)
        list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, 
                            font=("Arial", 10),
                            yscrollcommand=scrollbar.set,
                            selectmode=tk.SINGLE,
                            height=8)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate listbox with sheet names
        for sheet in sheet_names:
            listbox.insert(tk.END, sheet)
        
        # Select first item by default
        listbox.selection_set(0)
        listbox.activate(0)
        
        def on_ok():
            selection_idx = listbox.curselection()
            if selection_idx:
                result.set(sheet_names[selection_idx[0]])
            else:
                result.set(sheet_names[0])  # Default to first sheet
            dialog.destroy()
        
        def on_cancel():
            result.set("")  # Empty means cancelled
            dialog.destroy()
        
        def on_double_click(event):
            on_ok()  # Double-click acts as OK
        
        listbox.bind('<Double-Button-1>', on_double_click)
        
        # Button frame
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ok_btn = tk.Button(btn_frame, text="Open", command=on_ok, width=12, font=("Arial", 10, "bold"))
        ok_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=on_cancel, width=12, font=("Arial", 10))
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        final_result = result.get() if result.get() else None
        print(f"Sheet selection dialog closed, returning: {final_result}")
        return final_result
    
    # === File handling ===
    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open Data File",
            filetypes=[
                ("ODS / Excel / CSV", "*.ods *.xlsx *.xls *.csv"),
                ("ODS", "*.ods"),
                ("Excel", "*.xlsx *.xls"),
                ("CSV", "*.csv")
            ]
        )
        if not path:
            return
        
        # Detect available sheets and ask user to select one (for multi-sheet files)
        sheet_name = None
        if path.endswith(('.ods', '.xlsx', '.xls')):
            try:
                from utils.external_data_importer import ExternalDataImporter
                importer = ExternalDataImporter()
                sheet_names = importer.get_sheet_names(path)
                
                if sheet_names and len(sheet_names) > 1:
                    sheet_name = self._ask_sheet_selection(sheet_names)
                    if not sheet_name:
                        print("User cancelled sheet selection")
                        return  # User cancelled
                    print(f"User selected sheet: {sheet_name}")
                    self.current_sheet_name = sheet_name  # Store for viewer
                elif sheet_names:
                    sheet_name = sheet_names[0]
                    self.current_sheet_name = sheet_name  # Store for viewer
                    print(f"Using single sheet: {sheet_name}")
            except Exception as sheet_error:
                print(f"Could not detect sheets: {sheet_error}. Using first sheet.")
        
        try:
            # Read using pandas directly with sheet support, then let DataFileManager standardize
            if path.endswith('.ods'):
                src_df = pd.read_excel(path, engine='odf', sheet_name=sheet_name or 0)
            elif path.endswith(('.xlsx', '.xls')):
                src_df = pd.read_excel(path, engine='openpyxl', sheet_name=sheet_name or 0)
            elif path.endswith('.csv'):
                src_df = pd.read_csv(path)
            else:
                src_df = self.manager.read_external_file(path, DataFormat.PLOT3D)
            if src_df is None:
                messagebox.showerror("Error", "Failed to read file. Ensure dependencies for ODS/XLSX are installed.")
                return

            df = src_df.copy()
            
            # CRITICAL FIX: Detect data format to prevent double conversion
            # Check if the file already contains L*a*b* columns with reasonable values
            has_lab_columns = all(col in df.columns for col in ['L*', 'a*', 'b*'])
            has_normalized_columns = all(col in df.columns for col in ['Xnorm', 'Ynorm', 'Znorm'])
            
            if has_lab_columns:
                # File already has L*a*b* data - use it directly
                print(f"DEBUG: File contains L*a*b* columns, using directly")
                l_values = pd.to_numeric(df['L*'], errors='coerce')
                a_values = pd.to_numeric(df['a*'], errors='coerce')
                b_values = pd.to_numeric(df['b*'], errors='coerce')
                
                # Verify the values are in reasonable L*a*b* ranges
                l_reasonable = l_values.between(0, 100).sum() > len(l_values) * 0.8
                a_reasonable = a_values.between(-128, 127).sum() > len(a_values) * 0.8  
                b_reasonable = b_values.between(-128, 127).sum() > len(b_values) * 0.8
                
                if l_reasonable and a_reasonable and b_reasonable:
                    print(f"DEBUG: L*a*b* values are in reasonable ranges, using as-is")
                    df['L*'] = l_values
                    df['a*'] = a_values
                    df['b*'] = b_values
                else:
                    print(f"DEBUG: L*a*b* values seem out of range, may be normalized format mislabeled")
                    # Treat as normalized data despite column names
                    df['L*'] = l_values * 100.0
                    df['a*'] = a_values * 255.0 - 128.0
                    df['b*'] = b_values * 255.0 - 128.0
                    
            elif has_normalized_columns:
                # File has Plot_3D normalized format - convert to L*a*b*
                print(f"DEBUG: File contains normalized columns, converting to L*a*b*")
                df['L*'] = pd.to_numeric(df['Xnorm'], errors='coerce') * 100.0
                df['a*'] = pd.to_numeric(df['Ynorm'], errors='coerce') * 255.0 - 128.0
                df['b*'] = pd.to_numeric(df['Znorm'], errors='coerce') * 255.0 - 128.0
            else:
                # Try to auto-detect from any numeric columns
                print(f"DEBUG: No standard columns found, attempting auto-detection")
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if len(numeric_cols) >= 3:
                    # Use first 3 numeric columns and assume they need conversion if values are 0-1
                    col1, col2, col3 = numeric_cols[:3]
                    val1 = pd.to_numeric(df[col1], errors='coerce')
                    val2 = pd.to_numeric(df[col2], errors='coerce')
                    val3 = pd.to_numeric(df[col3], errors='coerce')
                    
                    # Check if values are in 0-1 range (normalized) or larger ranges (L*a*b*)
                    if (val1.between(0, 1).sum() > len(val1) * 0.8 and 
                        val2.between(0, 1).sum() > len(val2) * 0.8 and 
                        val3.between(0, 1).sum() > len(val3) * 0.8):
                        print(f"DEBUG: Auto-detected normalized format in columns {col1}, {col2}, {col3}")
                        df['L*'] = val1 * 100.0
                        df['a*'] = val2 * 255.0 - 128.0
                        df['b*'] = val3 * 255.0 - 128.0
                    else:
                        print(f"DEBUG: Auto-detected L*a*b* format in columns {col1}, {col2}, {col3}")
                        df['L*'] = val1
                        df['a*'] = val2  
                        df['b*'] = val3
                else:
                    messagebox.showerror("Import Error", 
                        "Could not detect color data format.\n\n"
                        "Expected columns: L*, a*, b* (for Lab data) or Xnorm, Ynorm, Znorm (for normalized data)\n"
                        "Or at least 3 numeric columns for auto-detection.")
                    return

            # Marker/Color/DataID defaults
            if 'Marker' not in df.columns:
                df['Marker'] = '.'
            if 'Color' not in df.columns:
                df['Color'] = 'blue'
            if 'DataID' not in df.columns:
                df['DataID'] = [f"Point_{i+1}" for i in range(len(df))]

            self.df = df[['L*', 'a*', 'b*', 'DataID', 'Marker', 'Color']].copy()
            
            # Debug output
            print(f"DEBUG: Final L*a*b* ranges after import:")
            print(f"  L*: {self.df['L*'].min():.2f} to {self.df['L*'].max():.2f}")
            print(f"  a*: {self.df['a*'].min():.2f} to {self.df['a*'].max():.2f}")
            print(f"  b*: {self.df['b*'].min():.2f} to {self.df['b*'].max():.2f}")
            
            # Update database indicator for external files
            import os
            filename = os.path.basename(path)
            self.current_database.set(f"{filename} ({len(self.df)} points)")
            self.current_database_name = path  # Store full path for external files
            
            self._render()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\\n\\n{e}")
    
    def _open_file_by_path(self, path):
        """Reload file from a known path (used for refresh after external edits)."""
        try:
            # Detect sheet name if multi-sheet file
            sheet_name = None
            if path.endswith(('.ods', '.xlsx', '.xls')):
                try:
                    from utils.external_data_importer import ExternalDataImporter
                    importer = ExternalDataImporter()
                    sheet_names = importer.get_sheet_names(path)
                    if sheet_names:
                        sheet_name = sheet_names[0]  # Use first sheet for refresh
                except Exception:
                    pass
            
            # Read file
            if path.endswith('.ods'):
                src_df = pd.read_excel(path, engine='odf', sheet_name=sheet_name or 0)
            elif path.endswith(('.xlsx', '.xls')):
                src_df = pd.read_excel(path, engine='openpyxl', sheet_name=sheet_name or 0)
            elif path.endswith('.csv'):
                src_df = pd.read_csv(path)
            else:
                return
            
            df = src_df.copy()
            
            # Process data (same logic as _open_file)
            has_lab_columns = all(col in df.columns for col in ['L*', 'a*', 'b*'])
            has_normalized_columns = all(col in df.columns for col in ['Xnorm', 'Ynorm', 'Znorm'])
            
            if has_lab_columns:
                l_values = pd.to_numeric(df['L*'], errors='coerce')
                a_values = pd.to_numeric(df['a*'], errors='coerce')
                b_values = pd.to_numeric(df['b*'], errors='coerce')
                df['L*'] = l_values
                df['a*'] = a_values
                df['b*'] = b_values
            elif has_normalized_columns:
                df['L*'] = pd.to_numeric(df['Xnorm'], errors='coerce') * 100.0
                df['a*'] = pd.to_numeric(df['Ynorm'], errors='coerce') * 255.0 - 128.0
                df['b*'] = pd.to_numeric(df['Znorm'], errors='coerce') * 255.0 - 128.0
            
            # Set defaults
            if 'Marker' not in df.columns:
                df['Marker'] = '.'
            if 'Color' not in df.columns:
                df['Color'] = 'blue'
            if 'DataID' not in df.columns:
                df['DataID'] = [f"Point_{i+1}" for i in range(len(df))]
            
            self.df = df[['L*', 'a*', 'b*', 'DataID', 'Marker', 'Color']].copy()
            self._render()
            
        except Exception as e:
            print(f"ERROR: Failed to reload file: {e}")
            raise

    def _load_from_realtime_db(self):
        """Load data from the realtime datasheet database."""
        try:
            import sys
            import os
            from tkinter import messagebox, simpledialog
            
            # Import required modules with fallback
            try:
                from utils.path_utils import get_color_analysis_dir
            except Exception as e:
                # Fallback to hardcoded paths
                if sys.platform == 'darwin':
                    def get_color_analysis_dir():
                        return os.path.expanduser('~/Library/Application Support/StampZ-III/data/color_analysis')
                else:
                    def get_color_analysis_dir():
                        return os.path.join(os.getcwd(), 'data', 'color_analysis')
            
            try:
                from utils.color_analysis_db import ColorAnalysisDB
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import ColorAnalysisDB:\n\n{e}")
                return
            
            # Use proper path resolution for bundled apps
            db_dir = get_color_analysis_dir()
            
            if not os.path.exists(db_dir):
                messagebox.showerror("Error", 
                    "No color analysis databases found.\n\n"
                    "Please run color analysis first using the Sample tool.")
                return
            
            # Use ColorAnalysisDB's built-in database discovery
            try:
                available_databases = ColorAnalysisDB.get_all_sample_set_databases(db_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Database discovery failed:\n\n{e}")
                return
            
            if not available_databases:
                messagebox.showerror("Error", 
                    "No database files found in Application Support.\n\n"
                    "Please run color analysis first using the Sample tool.")
                return
            
            # Show available databases
            if len(available_databases) == 1:
                selected_db = available_databases[0]
            else:
                # Simple selection dialog
                selection_text = "Available databases:\n" + "\n".join([f"{i+1}. {name}" for i, name in enumerate(available_databases)])
                selection_text += "\n\nEnter number (1-{}):".format(len(available_databases))
                
                choice = simpledialog.askstring("Select Database", selection_text)
                if not choice:
                    return
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(available_databases):
                        selected_db = available_databases[idx]
                    else:
                        raise ValueError("Invalid selection")
                except (ValueError, IndexError):
                    messagebox.showerror("Error", "Invalid selection. Please try again.")
                    return
            
            # Load from selected database
            db = ColorAnalysisDB(selected_db)
            measurements = db.get_all_measurements()
            
            if not measurements:
                messagebox.showwarning("No Data", f"No measurements found in database '{selected_db}'.")
                self.current_database.set(f"{selected_db} (No data)")
                return
            
            # Update database indicator
            self.current_database.set(f"{selected_db} ({len(measurements)} points)")
            self.current_database_name = selected_db  # Store database name for viewer
            
            # Store raw measurements for re-normalization when toggle changes
            self.database_measurements = measurements
            
            # Detect data source type
            self.data_source_type = self._detect_data_source_type(measurements)
            print(f"DEBUG: Detected data source type: {self.data_source_type}")
            
            # Enable/disable RGB toggle based on data type
            if self.data_source_type in ['channel_rgb', 'channel_cmy']:
                # Channel data only has one data type - disable toggle
                self.rgb_toggle.configure(state='disabled')
                self.use_rgb_labels.set(True)  # Always "RGB" for channel data
                print(f"DEBUG: Channel data detected - toggle disabled")
            else:
                # Color analysis - enable toggle
                self.rgb_toggle.configure(state='normal')
                print(f"DEBUG: Color analysis data detected - toggle enabled")
            
            # Convert measurements to dataframe based on current toggle state
            self._convert_measurements_to_dataframe()
            self._render()
            
            messagebox.showinfo("Success", f"Loaded {len(measurements)} measurements from database.")
            
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"Failed to load from realtime database:\n\n{e}\n\nDetails:\n{traceback.format_exc()}")

    def _view_database(self):
        """Open the RealtimePlot3DSheet interface to view and edit current database contents."""
        if not self.current_database_name:
            messagebox.showwarning("No Database", "No database is currently loaded.")
            return
        
        if self.df is None or self.df.empty:
            messagebox.showwarning("No Data", "No data is available to view.")
            return
        
        try:
            # Check if this is an external file (not a database)
            import os
            print(f"\n=== VIEW DATABASE DEBUG ===")
            print(f"current_database_name: {self.current_database_name}")
            print(f"Type: {type(self.current_database_name)}")
            
            is_external_file = self.current_database_name and (
                self.current_database_name.endswith(('.ods', '.xlsx', '.xls', '.csv')) or 
                '/' in self.current_database_name  # Full file path
            )
            print(f"is_external_file: {is_external_file}")
            print(f"==========================\n")
            
            if is_external_file:
                # External file - open in system's default spreadsheet application
                print(f"DEBUG: Opening external file in system application: {self.current_database_name}")
                
                import subprocess
                import sys
                
                try:
                    if sys.platform == 'darwin':  # macOS
                        subprocess.run(['open', self.current_database_name], check=True)
                    elif sys.platform == 'win32':  # Windows
                        os.startfile(self.current_database_name)
                    else:  # Linux
                        subprocess.run(['xdg-open', self.current_database_name], check=True)
                    
                    sheet_info = f" (Sheet: {self.current_sheet_name})" if self.current_sheet_name else ""
                    messagebox.showinfo(
                        "External File Opened",
                        f"Opened {os.path.basename(self.current_database_name)}{sheet_info} in your default spreadsheet application.\n\n"
                        f"Note: The spreadsheet app will open to its default sheet.\n"
                        f"You selected: {self.current_sheet_name or 'first sheet'}\n\n"
                        f"After making changes:\n"
                        f"1. Save the file in your spreadsheet app\n"
                        f"2. Click 'Open Data (ODS/XLSX/CSV)' and reselect the same sheet to reload"
                    )
                    
                except Exception as e:
                    messagebox.showerror(
                        "Open Error",
                        f"Could not open file in system application:\n\n{e}\n\n"
                        f"Please open the file manually:\n{self.current_database_name}"
                    )
                
                return
            
            # Import the RealtimePlot3DSheet interface
            from gui.realtime_plot3d_sheet import RealtimePlot3DSheet
            
            # Convert our L*a*b* data to the Plot_3D normalized format (0-1 range)
            plot3d_df = self._convert_to_plot3d_format(self.df.copy())
            
            # Open the RealtimePlot3DSheet with the actual database name so it can refresh properly
            datasheet = RealtimePlot3DSheet(
                parent=self.root, 
                sample_set_name=self.current_database_name,  # Use actual database name for proper refresh
                load_initial_data=False  # We'll load our own data
            )
            
            # Override the refresh method to refresh Ternary Plot instead of StampZ
            original_refresh = datasheet._refresh_from_stampz
            def ternary_refresh(*args, **kwargs):
                print("DEBUG: Ternary Plot refresh triggered")
                try:
                    # Reload data silently (no popup messages)
                    from utils.color_analysis_db import ColorAnalysisDB
                    import pandas as pd
                    
                    db = ColorAnalysisDB(self.current_database_name)
                    measurements = db.get_all_measurements()
                    
                    if measurements:
                        # Store measurements and detect type
                        self.database_measurements = measurements
                        self.data_source_type = self._detect_data_source_type(measurements)
                        
                        # Update toggle state
                        if self.data_source_type in ['channel_rgb', 'channel_cmy']:
                            self.rgb_toggle.configure(state='disabled')
                            self.use_rgb_labels.set(True)
                        else:
                            self.rgb_toggle.configure(state='normal')
                        
                        # Convert using current toggle setting
                        self._convert_measurements_to_dataframe()
                        self.current_database.set(f"{self.current_database_name} ({len(measurements)} points)")
                        self._render()
                        print(f"DEBUG: Updated ternary plot with {len(measurements)} points")
                    
                    # Refresh datasheet with original method (avoid recursion)
                    original_refresh()
                    
                except Exception as e:
                    print(f"DEBUG: Refresh error: {e}")
                    messagebox.showerror("Refresh Error", f"Failed to refresh data: {e}")
            datasheet._refresh_from_stampz = ternary_refresh
            
            # Update the window title to show Ternary Plot context while keeping database functionality
            datasheet.window.title(f"Plot_3D: Ternary Plot - {self.current_database_name} - Normalized Data (0-1 Range)")
            
            # Update the refresh button's command and text for Ternary Plot context
            if hasattr(datasheet, 'refresh_btn') and datasheet.refresh_btn:
                datasheet.refresh_btn.configure(
                    command=ternary_refresh,
                    text="Refresh Ternary Plot"
                )
                print("DEBUG: Updated refresh button for Ternary Plot context")
            
            # Load our converted data into the datasheet
            if hasattr(datasheet, 'sheet') and len(plot3d_df) > 0:
                # Convert DataFrame to list format for tksheet
                data_values = plot3d_df.values.tolist()
                
                # Insert rows if needed (tksheet needs proper row count)
                current_rows = datasheet.sheet.get_total_rows()
                needed_rows = max(len(data_values) + 10, 50)  # Data + buffer
                
                if current_rows < needed_rows:
                    empty_rows = [[''] * len(plot3d_df.columns)] * (needed_rows - current_rows)
                    datasheet.sheet.insert_rows(rows=empty_rows, idx=current_rows)
                
                # Set the data row by row starting from data area (row 7, display row 8)
                data_start_row = 7  # Skip header and centroid rows
                for i, row_data in enumerate(data_values):
                    row_idx = data_start_row + i
                    if row_idx < datasheet.sheet.get_total_rows():
                        datasheet.sheet.set_row_data(row_idx, values=row_data)
                
                # Set proper column headers
                datasheet.sheet.headers(list(plot3d_df.columns))
                
                # CRITICAL: Apply formatting and validation after data is loaded
                try:
                    print("DEBUG: Applying formatting to loaded data...")
                    datasheet._apply_formatting()
                    print("DEBUG: Applying validation dropdowns...")
                    datasheet._setup_validation()
                    print("DEBUG: Formatting and validation applied successfully")
                except Exception as format_error:
                    print(f"DEBUG: Error applying formatting: {format_error}")
                
                # Force refresh to update display
                datasheet.sheet.refresh()
            
        except ImportError as e:
            messagebox.showerror("Import Error", 
                f"Could not import RealtimePlot3DSheet interface:\n\n{e}\n\n"
                "Falling back to simple table view.")
            # Fallback to simple view if import fails
            self._view_database_simple()
        except Exception as e:
            messagebox.showerror("Error", 
                f"Failed to open database viewer:\n\n{e}\n\n"
                "Please check the console for more details.")
            print(f"DEBUG: Error opening RealtimePlot3DSheet: {e}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
    
    def _refresh_data(self):
        """Refresh data from the current database and update the plot."""
        print(f"DEBUG: _refresh_data called with current_database_name: {self.current_database_name}")
        if not self.current_database_name:
            messagebox.showwarning("No Database", "No database is currently loaded.")
            return
        
        try:
            # Import required modules
            from utils.color_analysis_db import ColorAnalysisDB
            
            # Directly reload from the known database without selection dialog
            db = ColorAnalysisDB(self.current_database_name)
            measurements = db.get_all_measurements()
            
            if not measurements:
                messagebox.showwarning("No Data", f"No measurements found in database '{self.current_database_name}'.")
                return
            
            # Store raw measurements and detect type
            self.database_measurements = measurements
            self.data_source_type = self._detect_data_source_type(measurements)
            
            # Update toggle state based on data type
            if self.data_source_type in ['channel_rgb', 'channel_cmy']:
                self.rgb_toggle.configure(state='disabled')
                self.use_rgb_labels.set(True)
            else:
                self.rgb_toggle.configure(state='normal')
            
            # Convert measurements using current toggle setting
            self._convert_measurements_to_dataframe()
            self.current_database.set(f"{self.current_database_name} ({len(measurements)} points)")
            self._render()
            
            messagebox.showinfo("Refresh Complete", 
                f"Refreshed data from '{self.current_database_name}' and updated plot.")
                
        except Exception as e:
            messagebox.showerror("Refresh Error", 
                f"Failed to refresh data from database:\n\n{e}")
    
    def _on_plot_click(self, event):
        """Handle click events on the plot for point highlighting."""
        if event.inaxes != self.ax or not self.plot_points:
            return
        
        click_x, click_y = event.xdata, event.ydata
        if click_x is None or click_y is None:
            return
        
        # Find closest point to click location
        min_distance = float('inf')
        closest_point_idx = None
        
        for i, point in enumerate(self.plot_points):
            distance = math.sqrt((point['x'] - click_x)**2 + (point['y'] - click_y)**2)
            if distance < min_distance:
                min_distance = distance
                closest_point_idx = i
        
        # Only highlight if click is reasonably close to a point
        click_threshold = 0.05  # Adjust based on plot scale
        if min_distance < click_threshold:
            if self.highlighted_point == closest_point_idx:
                # Click on already highlighted point - deselect
                self.highlighted_point = None
            else:
                # Highlight new point
                self.highlighted_point = closest_point_idx
            
            # Refresh plot to show highlighting while preserving zoom
            self._render(preserve_zoom=True)
        else:
            # Click not near any point - clear selection
            if self.highlighted_point is not None:
                self.highlighted_point = None
                self._render(preserve_zoom=True)
    
    def _convert_to_plot3d_format(self, df):
        """Convert L*a*b* data to Plot_3D normalized format."""
        plot3d_df = pd.DataFrame()
        
        # Convert L*a*b* or RGB/CMY channel data to normalized Xnorm, Ynorm, Znorm (0-1 range)
        if all(col in df.columns for col in ['L*', 'a*', 'b*']):
            l_values = pd.to_numeric(df['L*'], errors='coerce').fillna(50)  # Default mid-range
            a_values = pd.to_numeric(df['a*'], errors='coerce').fillna(0)  # Default neutral
            b_values = pd.to_numeric(df['b*'], errors='coerce').fillna(0)  # Default neutral
            
            # Detect if this is channel data (RGB/CMY) vs L*a*b* color data
            # Channel data: values are in 0-255 range
            # L*a*b* data: L* in 0-100, a*/b* in -128 to +127
            l_in_rgb_range = (l_values >= 0).all() and (l_values <= 255).all() and (l_values.max() > 100 or (l_values > 1).any())
            a_in_rgb_range = (a_values >= 0).all() and (a_values <= 255).all()
            b_in_rgb_range = (b_values >= 0).all() and (b_values <= 255).all()
            
            if l_in_rgb_range and a_in_rgb_range and b_in_rgb_range:
                # Channel data (RGB or CMY) - values are 0-255, normalize by dividing by 255
                print(f"DEBUG: Detected channel data in Plot3D conversion (0-255 range)")
                plot3d_df['Xnorm'] = np.clip(l_values / 255.0, 0, 1)
                plot3d_df['Ynorm'] = np.clip(a_values / 255.0, 0, 1)
                plot3d_df['Znorm'] = np.clip(b_values / 255.0, 0, 1)
            else:
                # L*a*b* color data - apply L*a*b* normalization formulas
                print(f"DEBUG: Detected L*a*b* color data in Plot3D conversion")
                plot3d_df['Xnorm'] = np.clip(l_values / 100.0, 0, 1)
                plot3d_df['Ynorm'] = np.clip((a_values + 128) / 255.0, 0, 1)
                plot3d_df['Znorm'] = np.clip((b_values + 128) / 255.0, 0, 1)
        else:
            # If no L*a*b* data, create default values
            plot3d_df['Xnorm'] = 0.5
            plot3d_df['Ynorm'] = 0.5 
            plot3d_df['Znorm'] = 0.5
        
        # Set DataID from existing data or generate
        if 'DataID' in df.columns:
            plot3d_df['DataID'] = df['DataID']
        else:
            plot3d_df['DataID'] = [f"Point_{i+1}" for i in range(len(df))]
        
        # Add other Plot_3D columns with defaults
        plot3d_df['Cluster'] = 1
        plot3d_df['DeltaE'] = 0.0
        
        # Use marker and color from original data if available, with proper defaults
        if 'Marker' in df.columns:
            plot3d_df['Marker'] = df['Marker'].fillna('.').astype(str)
            # Ensure all markers are valid
            valid_markers = ['.', 'o', '*', '^', '<', '>', 'v', 's', 'D', '+', 'x']
            plot3d_df['Marker'] = plot3d_df['Marker'].apply(lambda x: x if x in valid_markers else '.')
        else:
            plot3d_df['Marker'] = '.'
            
        if 'Color' in df.columns:
            plot3d_df['Color'] = df['Color'].fillna('blue').astype(str)
            # Ensure all colors are valid
            valid_colors = ['red', 'blue', 'green', 'orange', 'purple', 'yellow', 'cyan', 'magenta', 'brown', 'pink', 'lime', 'navy', 'teal', 'gray']
            plot3d_df['Color'] = plot3d_df['Color'].apply(lambda x: x if x in valid_colors else 'blue')
        else:
            plot3d_df['Color'] = 'blue'
        
        # Add empty columns for Plot_3D features
        plot3d_df['Centroid_X'] = np.nan
        plot3d_df['Centroid_Y'] = np.nan
        plot3d_df['Centroid_Z'] = np.nan
        plot3d_df['Sphere'] = ''
        plot3d_df['Radius'] = np.nan
        
        return plot3d_df
    
    def _view_database_simple(self):
        """Fallback simple table view if RealtimePlot3DSheet is unavailable."""
        # Create a simple table view window (original implementation)
        viewer_window = tk.Toplevel(self.root)
        viewer_window.title(f"Database Contents - {self.current_database_name}")
        viewer_window.geometry("800x600")
        
        # Create a frame for the treeview and scrollbars
        tree_frame = ttk.Frame(viewer_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview with scrollbars
        columns = list(self.df.columns)
        tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings')
        
        # Configure column headings
        tree.heading('#0', text='Row')
        tree.column('#0', width=50)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        # Populate with data
        for idx, row in self.df.iterrows():
            values = [str(row[col]) if not pd.isna(row[col]) else '' for col in columns]
            tree.insert('', 'end', text=str(idx), values=values)
        
        tree.pack(fill=tk.BOTH, expand=True)

    def _save_png(self):
        path = filedialog.asksaveasfilename(
            title="Save Plot as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")]
        )
        if not path:
            return
        try:
            self.fig.savefig(path, dpi=150)
            messagebox.showinfo("Saved", f"Plot saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save plot:\n\n{e}")

    # === Plotting ===
    def _render(self, preserve_zoom=False):
        # Store current axis limits if preserving zoom
        if preserve_zoom:
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
        
        self.ax.clear()
        self._draw_ternary_axes()

        if self.df is None or self.df.empty:
            self.ax.set_title("No data loaded", fontsize=11)
            self.canvas.draw_idle()
            return

        # Convert L*, a*, b* to normalized proportions for ternary display
        df = self.df.copy()
        
        # Get L*a*b* values and handle missing data
        L = pd.to_numeric(df['L*'], errors='coerce').fillna(50.0)  # Default to mid-gray
        A = pd.to_numeric(df['a*'], errors='coerce').fillna(0.0)
        B = pd.to_numeric(df['b*'], errors='coerce').fillna(0.0)
        
        print(f"DEBUG: Ternary plot L*a*b* ranges before conversion:")
        print(f"  L*: {L.min():.2f} to {L.max():.2f}")
        print(f"  a*: {A.min():.2f} to {A.max():.2f}")
        print(f"  b*: {B.min():.2f} to {B.max():.2f}")
        
        # PROPER TERNARY CONVERSION: Use absolute values to create meaningful proportions
        # This preserves the actual color relationships without distorting the data
        
        # Method 1: Use L* directly and absolute values for a* and b*
        # This creates a meaningful ternary relationship based on color lightness and chromaticity
        L_component = L.clip(lower=0.1)  # Ensure minimum positive value
        A_component = A.abs().clip(lower=0.1)  # Use absolute value of a*
        B_component = B.abs().clip(lower=0.1)  # Use absolute value of b*
        
        # Normalize to create ternary coordinates (sum = 1)
        total = (L_component + A_component + B_component).replace(0, np.nan)
        Lp = (L_component / total).fillna(0.33)
        Ap = (A_component / total).fillna(0.33)
        Bp = (B_component / total).fillna(0.33)
        
        print(f"DEBUG: Ternary coordinates after conversion:")
        print(f"  Lp: {Lp.min():.3f} to {Lp.max():.3f}")
        print(f"  Ap: {Ap.min():.3f} to {Ap.max():.3f}")
        print(f"  Bp: {Bp.min():.3f} to {Bp.max():.3f}")
        print(f"  Sum check: {(Lp + Ap + Bp).min():.3f} to {(Lp + Ap + Bp).max():.3f}")

        # Project to 2D Cartesian in an equilateral triangle
        pts = self._barycentric_to_cartesian(Lp.values, Ap.values, Bp.values)
        x, y = pts[:, 0], pts[:, 1]
        
        # Constrain points to stay within triangle boundaries (add small inward margin)
        h = math.sqrt(3) / 2.0
        margin = 0.002  # Small inward margin to prevent edge overlap
        
        # Triangle vertices with margin
        A = (margin, margin)  # Bottom left  
        B = (1.0 - margin, margin)  # Bottom right
        C = (0.5, h - margin)  # Top
        
        # Clamp points to stay within the triangle with margin
        for i in range(len(x)):
            # Ensure point is within the triangle by checking barycentric coordinates
            # and adjusting if necessary
            px, py = x[i], y[i]
            
            # Convert back to barycentric to check bounds
            # Solve: px = B_coord * 1.0 + C_coord * 0.5, py = C_coord * h
            if py < margin:
                y[i] = margin
            elif py > h - margin:
                y[i] = h - margin
                
            if px < margin:
                x[i] = margin
            elif px > 1.0 - margin:
                x[i] = 1.0 - margin
                
            # Additional constraint for the slanted edges of the triangle
            # Left edge: points to the left of the line from A to C
            # Right edge: points to the right of the line from B to C
            
            # Left edge constraint: x >= (2*y - margin) (approximately)
            left_bound = 2 * (y[i] - margin) + margin
            if x[i] < left_bound:
                x[i] = left_bound
                
            # Right edge constraint: x <= 1 - 2*(y - margin) (approximately)
            right_bound = 1.0 - 2 * (y[i] - margin) - margin
            if x[i] > right_bound:
                x[i] = right_bound

        # Plot points with appropriate marker size based on position
        markers = df.get('Marker', pd.Series(['.'] * len(df))).fillna('.')
        colors = df.get('Color', pd.Series(['blue'] * len(df))).fillna('blue')
        
        # Clear previous point data for click detection
        self.plot_points = []
        
        # Use zoom level to control marker size
        base_marker_size = 25  # Base size
        marker_size = base_marker_size * self.zoom_level.get()
        
        for i in range(len(df)):
            m = markers.iloc[i]
            c = colors.iloc[i]
            
            # Store point coordinates and DataID for click detection
            data_id = df.iloc[i].get('DataID', f'Point_{i+1}')
            self.plot_points.append({
                'x': x[i], 'y': y[i], 
                'index': i, 
                'data_id': data_id,
                'marker': m,
                'color': c
            })
            
            # Further reduce marker size for points very close to triangle edges
            dist_to_edges = min(
                y[i],  # Distance to bottom edge
                abs(x[i] - 2*y[i]),  # Distance to left edge (approximate)
                abs(x[i] - (1.0 - 2*y[i]))  # Distance to right edge (approximate)
            )
            
            # Scale marker size based on distance to edges
            edge_threshold = 0.05
            if dist_to_edges < edge_threshold:
                adjusted_size = marker_size * (0.5 + 0.5 * (dist_to_edges / edge_threshold))
            else:
                adjusted_size = marker_size
            
            # Highlight selected point with larger size and different edge
            if self.highlighted_point == i:
                edge_color = 'red'
                edge_width = 2.0
                size_multiplier = 1.5
            else:
                edge_color = 'black'
                edge_width = 0.2
                size_multiplier = 1.0
                
            self.ax.scatter([x[i]], [y[i]], s=adjusted_size * size_multiplier, 
                          marker=m if str(m) else '.', 
                          c=c if str(c) else 'blue', 
                          edgecolors=edge_color, linewidths=edge_width, alpha=0.9)

        # Convex hull
        if self.show_hull.get() and len(x) >= 3:
            hull_idx = self._convex_hull_2d(np.stack([x, y], axis=1))
            hx = x[hull_idx + [hull_idx[0]]]
            hy = y[hull_idx + [hull_idx[0]]]
            self.ax.plot(hx, hy, '-', color='darkred', lw=1.2, alpha=0.9, label='Convex Hull')
            self.ax.legend(loc='upper right')

        # Update title to show highlighted point info
        if self.highlighted_point is not None and self.plot_points:
            highlighted_data = self.plot_points[self.highlighted_point]
            title = f"Ternary Plot - Selected: {highlighted_data['data_id']}"
        else:
            title = "Ternary Plot"
        
        self.ax.set_title(title, fontsize=12)
        
        # Restore zoom if preserving
        if preserve_zoom:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)
        
        self.canvas.draw_idle()

    def _draw_ternary_axes(self):
        # Equilateral triangle vertices
        h = math.sqrt(3) / 2.0
        A = (0.0, 0.0)      # Bottom left (L* vertex)
        B = (1.0, 0.0)      # Bottom right (a* vertex)
        C = (0.5, h)        # Top (b* vertex)
        
        # Draw triangle
        self.ax.plot([A[0], B[0]], [A[1], B[1]], color='black', lw=1.5)
        self.ax.plot([B[0], C[0]], [B[1], C[1]], color='black', lw=1.5)
        self.ax.plot([C[0], A[0]], [C[1], A[1]], color='black', lw=1.5)
        
        # Add axis labels around the perimeter
        label_offset = 0.08
        
        # Choose labels based on data type and toggle
        print(f"DEBUG: Label selection - data_source_type={self.data_source_type}, use_rgb_labels={self.use_rgb_labels.get()}")
        if self.data_source_type == 'channel_cmy':
            label1, label2, label3 = 'C', 'M', 'Y'
            color1, color2, color3 = 'cyan', 'magenta', 'yellow'
            print(f"DEBUG: Using CMY labels")
        elif self.data_source_type == 'channel_rgb' or self.use_rgb_labels.get():
            label1, label2, label3 = 'R', 'G', 'B'
            color1, color2, color3 = 'lightcoral', 'lightgreen', 'lightblue'
            print(f"DEBUG: Using RGB labels (channel_rgb={self.data_source_type == 'channel_rgb'}, toggle={self.use_rgb_labels.get()})")
        else:
            label1, label2, label3 = 'L*', 'a*', 'b*'
            color1, color2, color3 = 'lightblue', 'lightgreen', 'lightcoral'
            print(f"DEBUG: Using L*a*b* labels")
        
        # Label (bottom left vertex)
        self.ax.text(A[0] - label_offset, A[1] - label_offset, label1, 
                    fontsize=14, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=color1, alpha=0.8))
        
        # Label (bottom right vertex)
        self.ax.text(B[0] + label_offset, B[1] - label_offset, label2, 
                    fontsize=14, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=color2, alpha=0.8))
        
        # Label (top vertex)
        self.ax.text(C[0], C[1] + label_offset, label3, 
                    fontsize=14, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=color3, alpha=0.8))
        
        # Add edge labels (midpoints of sides) - positioned well outside triangle
        mid_offset = 0.08  # Increased from 0.04
        
        # Bottom edge label
        mid_AB = ((A[0] + B[0])/2, (A[1] + B[1])/2 - mid_offset)
        self.ax.text(mid_AB[0], mid_AB[1], f'{label1} ← → {label2}', 
                    fontsize=10, ha='center', va='center', style='italic',
                    color='darkblue')
        
        # Right edge label
        mid_BC = ((B[0] + C[0])/2 + mid_offset, (B[1] + C[1])/2)  # Increased offset
        self.ax.text(mid_BC[0], mid_BC[1], f'{label2} ↔ {label3}', 
                    fontsize=10, ha='center', va='center', style='italic',
                    rotation=-60, color='darkgreen')  # Fixed rotation to match edge
        
        # Left edge label
        mid_CA = ((C[0] + A[0])/2 - mid_offset, (C[1] + A[1])/2)  # Increased offset
        self.ax.text(mid_CA[0], mid_CA[1], f'{label3} ↔ {label1}', 
                    fontsize=10, ha='center', va='center', style='italic',
                    rotation=60, color='darkred')  # Fixed rotation to match edge
        
        # Add tick marks and percentage labels
        self._add_ternary_tick_marks(A, B, C)
        
        # Add grid lines if enabled
        if self.show_grid.get():
            self._draw_grid_lines(A, B, C)
        
        # Configure plot - provide extra space around triangle for markers
        self.ax.set_aspect('equal', adjustable='box')
        marker_padding = 0.03  # Extra space around triangle for markers at edges
        self.ax.set_xlim(-0.20, 1.20)  # Space for labels
        self.ax.set_ylim(-0.20, h + 0.20)  # Space for labels
        
        # Ensure the triangle drawing area has enough padding for edge markers
        self.ax.add_patch(Rectangle((-marker_padding, -marker_padding), 
                                  1.0 + 2*marker_padding, h + 2*marker_padding, 
                                  fill=False, edgecolor='none'))  # Invisible boundary for markers
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_xlabel('')  # Clear default labels
        self.ax.set_ylabel('')  # Clear default labels

    def _add_ternary_tick_marks(self, A, B, C):
        """Add tick marks and percentage labels along triangle edges."""
        # Tick positions (0.0, 0.1, 0.2, ..., 1.0)
        ticks = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        tick_labels = ['0.00', '0.10', '0.20', '0.30', '0.40', '0.50', '0.60', '0.70', '0.80', '0.90', '1.00']
        
        tick_length = 0.02  # Length of tick marks
        label_offset = 0.03  # Distance from edge for labels
        
        # Bottom edge (A to B): L* at A (0,0), a* at B (1,0)
        for i, t in enumerate(ticks):
            # Position along bottom edge
            tick_x = A[0] + t * (B[0] - A[0])  # 0 to 1
            tick_y = A[1] + t * (B[1] - A[1])  # 0 to 0
            
            # Tick mark pointing downward
            self.ax.plot([tick_x, tick_x], [tick_y, tick_y - tick_length], 
                        color='black', lw=1)
            
            # Labels (alternating L* and a* percentages)
            # L* decreases from 100% to 0% as we go from A to B
            l_percent = tick_labels[len(ticks)-1-i]
            # a* increases from 0% to 100% as we go from A to B  
            a_percent = tick_labels[i]
            
            if i % 2 == 0:  # Even positions: show both labels with better spacing
                self.ax.text(tick_x, tick_y - label_offset - 0.025, l_percent, 
                           fontsize=8, ha='center', va='center', color='blue')
                self.ax.text(tick_x, tick_y - label_offset - 0.005, a_percent, 
                           fontsize=8, ha='center', va='center', color='green')
        
        # Right edge (B to C): a* at B, b* at C
        for i, t in enumerate(ticks):
            # Position along right edge
            tick_x = B[0] + t * (C[0] - B[0])
            tick_y = B[1] + t * (C[1] - B[1])
            
            # Tick mark pointing perpendicular to edge (outward)
            edge_dx = C[0] - B[0]
            edge_dy = C[1] - B[1]
            # Perpendicular vector (rotate 90 degrees)
            perp_dx = edge_dy * tick_length
            perp_dy = -edge_dx * tick_length
            
            self.ax.plot([tick_x, tick_x + perp_dx], [tick_y, tick_y + perp_dy], 
                        color='black', lw=1)
            
            # Labels for a* and b*
            a_percent = tick_labels[len(ticks)-1-i]  # a* decreases B to C
            b_percent = tick_labels[i]              # b* increases B to C
            
            if i % 2 == 0:  # Even positions
                label_x = tick_x + perp_dx * 4.5  # Push further outside
                label_y = tick_y + perp_dy * 4.5
                # Right edge goes from bottom-right to top, so angle is about -60°
                self.ax.text(label_x, label_y + 0.03, a_percent, 
                           fontsize=8, ha='center', va='center', color='green', rotation=-60)
                self.ax.text(label_x, label_y - 0.03, b_percent, 
                           fontsize=8, ha='center', va='center', color='red', rotation=-60)
        
        # Left edge (C to A): b* at C, L* at A
        for i, t in enumerate(ticks):
            # Position along left edge
            tick_x = C[0] + t * (A[0] - C[0])
            tick_y = C[1] + t * (A[1] - C[1])
            
            # Tick mark pointing perpendicular to edge (outward)
            edge_dx = A[0] - C[0]
            edge_dy = A[1] - C[1]
            # Perpendicular vector (rotate 90 degrees clockwise for outward direction)
            perp_dx = edge_dy * tick_length  # Reversed sign
            perp_dy = -edge_dx * tick_length  # Reversed sign
            
            self.ax.plot([tick_x, tick_x + perp_dx], [tick_y, tick_y + perp_dy], 
                        color='black', lw=1)
            
            # Labels for b* and L*
            b_percent = tick_labels[len(ticks)-1-i]  # b* decreases C to A
            l_percent = tick_labels[i]              # L* increases C to A
            
            if i % 2 == 0:  # Even positions
                label_x = tick_x + perp_dx * 4.5  # Push even further outside
                label_y = tick_y + perp_dy * 4.5
                # Left edge goes from top to bottom-left, so angle is about 60°
                # Separate the labels more along the perpendicular direction
                self.ax.text(label_x - 0.04, label_y, b_percent, 
                           fontsize=8, ha='center', va='center', color='red', rotation=60)
                self.ax.text(label_x + 0.04, label_y, l_percent, 
                           fontsize=8, ha='center', va='center', color='blue', rotation=60)
    
    def _draw_grid_lines(self, A, B, C):
        """Draw grid lines parallel to each side of the triangle."""
        print("DEBUG: Drawing grid lines with 3 sets of parallel lines")
        # Grid positions at 10% intervals (excluding 0% and 100%)
        grid_positions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        
        for t in grid_positions:
            # Set 1: Lines parallel to side AB (bottom edge) - HORIZONTAL
            # Points at height t from bottom
            point1_x = A[0] + t * (C[0] - A[0])  # Point on AC at height t
            point1_y = A[1] + t * (C[1] - A[1])
            point2_x = B[0] + t * (C[0] - B[0])  # Point on BC at height t
            point2_y = B[1] + t * (C[1] - B[1])
            self.ax.plot([point1_x, point2_x], [point1_y, point2_y], 
                        color='lightgray', lw=0.5, alpha=0.7, zorder=0)
            
            # Set 2: Lines parallel to side BC (right edge G-B) - SLANT UP-LEFT
            # From left edge AC to bottom edge AB
            point1_x = A[0] + t * (C[0] - A[0])  # Point on AC
            point1_y = A[1] + t * (C[1] - A[1])
            point2_x = A[0] + t * (B[0] - A[0])  # Point on AB
            point2_y = A[1] + t * (B[1] - A[1])
            self.ax.plot([point1_x, point2_x], [point1_y, point2_y], 
                        color='lightgray', lw=0.5, alpha=0.7, zorder=0)
            
            # Set 3: Lines parallel to side AC (left edge B-R) - SLANT UP-RIGHT
            # From right edge BC to bottom edge AB (using reverse parameter)
            point1_x = B[0] + t * (C[0] - B[0])  # Point on BC
            point1_y = B[1] + t * (C[1] - B[1])
            point2_x = A[0] + (1-t) * (B[0] - A[0])  # Point on AB (reverse direction)
            point2_y = A[1] + (1-t) * (B[1] - A[1])
            self.ax.plot([point1_x, point2_x], [point1_y, point2_y], 
                        color='lightgray', lw=0.5, alpha=0.7, zorder=0)

    @staticmethod
    def _barycentric_to_cartesian(A, B, C):
        # Using vertices: A(0,0), B(1,0), C(0.5, sqrt(3)/2)
        h = math.sqrt(3) / 2.0
        x = B * 1.0 + C * 0.5  # A contributes 0 to x
        y = C * h               # Only C contributes to y
        return np.stack([x, y], axis=1)

    @staticmethod
    def _convex_hull_2d(points):
        # Andrew's monotone chain algorithm
        pts = sorted(map(tuple, points))
        if len(pts) <= 1:
            return list(range(len(pts)))

        def cross(o, a, b):
            return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

        lower = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        hull = lower[:-1] + upper[:-1]
        # Map back to original indices (may duplicate if identical points)
        hull_indices = []
        for hp in hull:
            for i, p in enumerate(points):
                if (abs(p[0]-hp[0]) < 1e-12) and (abs(p[1]-hp[1]) < 1e-12):
                    if i not in hull_indices:
                        hull_indices.append(i)
                        break
        return hull_indices


def open_ternary_plot_window(root):
    return TernaryPlotWindow(root)