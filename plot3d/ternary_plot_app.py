import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle

from utils.data_file_manager import get_data_file_manager, DataFormat


class TernaryPlotWindow:
    """Simple ternary plot window with a side panel and convex hull toggle."""

    def __init__(self, parent=None):
        self.parent = parent
        # Create as a child window so it stays owned by the app
        self.root = tk.Toplevel(parent) if isinstance(parent, (tk.Tk, tk.Toplevel)) else tk.Toplevel()
        self.root.title("Ternary Plot")
        self.root.geometry("1000x680")
        try:
            self.root.attributes('-topmost', False)
        except Exception:
            pass

        # State
        self.df = pd.DataFrame(columns=['L*', 'a*', 'b*', 'DataID', 'Marker', 'Color'])
        self.show_hull = tk.BooleanVar(value=False)
        self.manager = get_data_file_manager()
        self.current_database = tk.StringVar(value="No database loaded")
        self.current_database_name = None  # Track actual database name for viewer

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

        # Open external file
        ttk.Button(self.side, text="Open Data (ODS/XLSX/CSV)", command=self._open_file).pack(fill=tk.X, pady=4)
        
        # Load from realtime database
        ttk.Button(self.side, text="Load from Realtime DB", command=self._load_from_realtime_db).pack(fill=tk.X, pady=4)
        
        # View current database
        ttk.Button(self.side, text="View Database Contents", command=self._view_database).pack(fill=tk.X, pady=4)
        
        # Refresh
        ttk.Button(self.side, text="Refresh Plot", command=self._render).pack(fill=tk.X, pady=4)

        # Current database indicator
        db_frame = ttk.LabelFrame(self.side, text="Current Database")
        db_frame.pack(fill=tk.X, pady=6)
        self.db_label = ttk.Label(db_frame, textvariable=self.current_database, 
                                 foreground='darkblue', font=('Arial', 9, 'bold'),
                                 wraplength=240)
        self.db_label.pack(anchor='w', padx=5, pady=3)
        
        # Convex hull
        hull_frame = ttk.Frame(self.side)
        hull_frame.pack(fill=tk.X, pady=6)
        ttk.Checkbutton(hull_frame, text="Show Convex Hull", variable=self.show_hull, command=self._render).pack(anchor='w')

        # Save plot image
        ttk.Button(self.side, text="Save Plot as PNG", command=self._save_png).pack(fill=tk.X, pady=8)

        ttk.Separator(self.side, orient='horizontal').pack(fill=tk.X, pady=8)
        ttk.Button(self.side, text="Exit", command=self.root.destroy).pack(fill=tk.X, pady=4)

        # Info
        info = (
            "Data Sources:\n"
            " - External files: ODS/XLSX/CSV\n"
            " - Realtime DB: Current session data\n\n"
            "Columns used:\n"
            " - L*, a*, b*, DataID, Marker, Color\n\n"
            "Notes:\n"
            " - Data is normalized to sum=1 for ternary projection\n"
            " - Convex hull uses a simple 2D hull on projected points"
        )
        ttk.Label(self.side, text=info, wraplength=240, foreground='gray').pack(anchor='w', pady=(10, 0))

    def _build_plot(self):
        self.fig = plt.Figure(figsize=(6.5, 6.0), facecolor='white')
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

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
        try:
            # Read using DataFileManager and standardize to Plot3D first
            src_df = self.manager.read_external_file(path, DataFormat.PLOT3D)
            if src_df is None:
                messagebox.showerror("Error", "Failed to read file. Ensure dependencies for ODS/XLSX are installed.")
                return

            df = src_df.copy()
            if all(col in df.columns for col in ['Xnorm', 'Ynorm', 'Znorm']):
                # Convert normalized 0-1 to approximate L*,a*,b* ranges
                df['L*'] = pd.to_numeric(df['Xnorm'], errors='coerce') * 100.0
                df['a*'] = pd.to_numeric(df['Ynorm'], errors='coerce') * 255.0 - 128.0
                df['b*'] = pd.to_numeric(df['Znorm'], errors='coerce') * 255.0 - 128.0

            # Marker/Color/DataID defaults
            if 'Marker' not in df.columns:
                df['Marker'] = '.'
            if 'Color' not in df.columns:
                df['Color'] = 'blue'
            if 'DataID' not in df.columns:
                df['DataID'] = ''

            self.df = df[['L*', 'a*', 'b*', 'DataID', 'Marker', 'Color']].copy()
            
            # Update database indicator for external files
            import os
            filename = os.path.basename(path)
            self.current_database.set(f"{filename} ({len(self.df)} points)")
            self.current_database_name = path  # Store full path for external files
            
            self._render()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n\n{e}")

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
            
            # Convert to DataFrame with ternary-compatible columns
            import pandas as pd
            df_data = []
            for m in measurements:
                # Convert L*a*b* values - check if they're already in reasonable ranges
                l_val = m.get('l_value', 50)  # Default to mid-range if missing
                a_val = m.get('a_value', 0)
                b_val = m.get('b_value', 0)
                
                # If values seem to be normalized (0-1), convert to L*a*b* ranges
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
            # Import the RealtimePlot3DSheet interface
            from gui.realtime_plot3d_sheet import RealtimePlot3DSheet
            
            # Convert our L*a*b* data to the Plot_3D normalized format (0-1 range)
            plot3d_df = self._convert_to_plot3d_format(self.df.copy())
            
            # Open the RealtimePlot3DSheet with the converted data
            datasheet = RealtimePlot3DSheet(
                parent=self.root, 
                sample_set_name=f"Ternary Plot - {self.current_database_name}",
                load_initial_data=False  # We'll load our own data
            )
            
            # Override the refresh method to refresh Ternary Plot instead of StampZ
            original_refresh = datasheet._refresh_from_stampz
            def ternary_refresh(*args, **kwargs):
                print("DEBUG: Ternary Plot refresh triggered")
                try:
                    # Reload data from current database
                    self._load_from_realtime_db()
                    messagebox.showinfo("Refresh Complete", "Ternary Plot data refreshed from database.")
                except Exception as e:
                    messagebox.showerror("Refresh Error", f"Failed to refresh Ternary Plot data:\n\n{e}")
            datasheet._refresh_from_stampz = ternary_refresh
            
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
    
    def _convert_to_plot3d_format(self, df):
        """Convert L*a*b* data to Plot_3D normalized format."""
        plot3d_df = pd.DataFrame()
        
        # Convert L*a*b* to normalized Xnorm, Ynorm, Znorm (0-1 range)
        if all(col in df.columns for col in ['L*', 'a*', 'b*']):
            # Normalize L* (0-100) to Xnorm (0-1)
            l_values = pd.to_numeric(df['L*'], errors='coerce').fillna(50)  # Default mid-range
            plot3d_df['Xnorm'] = np.clip(l_values / 100.0, 0, 1)
            
            # Normalize a* (-128 to +127) to Ynorm (0-1)
            a_values = pd.to_numeric(df['a*'], errors='coerce').fillna(0)  # Default neutral
            plot3d_df['Ynorm'] = np.clip((a_values + 128) / 255.0, 0, 1)
            
            # Normalize b* (-128 to +127) to Znorm (0-1)
            b_values = pd.to_numeric(df['b*'], errors='coerce').fillna(0)  # Default neutral
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
        plot3d_df['∆E'] = 0.0
        
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
    def _render(self):
        self.ax.clear()
        self._draw_ternary_axes()

        if self.df is None or self.df.empty:
            self.ax.set_title("No data loaded", fontsize=11)
            self.canvas.draw_idle()
            return

        # Convert L*, a*, b* to normalized proportions (non-negative then normalize)
        df = self.df.copy()
        a_shift = df['a*'].min()
        b_shift = df['b*'].min()
        L = pd.to_numeric(df['L*'], errors='coerce').fillna(0).clip(lower=0)
        A = (pd.to_numeric(df['a*'], errors='coerce').fillna(0) - a_shift).clip(lower=0)
        B = (pd.to_numeric(df['b*'], errors='coerce').fillna(0) - b_shift).clip(lower=0)

        total = (L + A + B).replace(0, np.nan)
        Lp = (L / total).fillna(0)
        Ap = (A / total).fillna(0)
        Bp = (B / total).fillna(0)

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
        
        # Use smaller marker size to reduce boundary issues
        marker_size = 25  # Reduced from 40
        
        for i in range(len(df)):
            m = markers.iloc[i]
            c = colors.iloc[i]
            
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
                
            self.ax.scatter([x[i]], [y[i]], s=adjusted_size, 
                          marker=m if str(m) else '.', 
                          c=c if str(c) else 'blue', 
                          edgecolors='black', linewidths=0.2, alpha=0.9)

        # Convex hull
        if self.show_hull.get() and len(x) >= 3:
            hull_idx = self._convex_hull_2d(np.stack([x, y], axis=1))
            hx = x[hull_idx + [hull_idx[0]]]
            hy = y[hull_idx + [hull_idx[0]]]
            self.ax.plot(hx, hy, '-', color='darkred', lw=1.2, alpha=0.9, label='Convex Hull')
            self.ax.legend(loc='upper right')

        self.ax.set_title("Ternary Plot", fontsize=12)
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
        
        # L* label (bottom left vertex)
        self.ax.text(A[0] - label_offset, A[1] - label_offset, 'L*', 
                    fontsize=14, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.8))
        
        # a* label (bottom right vertex)
        self.ax.text(B[0] + label_offset, B[1] - label_offset, 'a*', 
                    fontsize=14, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.8))
        
        # b* label (top vertex)
        self.ax.text(C[0], C[1] + label_offset, 'b*', 
                    fontsize=14, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightcoral', alpha=0.8))
        
        # Add edge labels (midpoints of sides) - positioned well outside triangle
        mid_offset = 0.08  # Increased from 0.04
        
        # Bottom edge label (L* - a*)
        mid_AB = ((A[0] + B[0])/2, (A[1] + B[1])/2 - mid_offset)
        self.ax.text(mid_AB[0], mid_AB[1], 'L* ← → a*', 
                    fontsize=10, ha='center', va='center', style='italic',
                    color='darkblue')
        
        # Right edge label (a* - b*)
        mid_BC = ((B[0] + C[0])/2 + mid_offset, (B[1] + C[1])/2)  # Increased offset
        self.ax.text(mid_BC[0], mid_BC[1], 'a* ↔ b*', 
                    fontsize=10, ha='center', va='center', style='italic',
                    rotation=-60, color='darkgreen')  # Fixed rotation to match edge
        
        # Left edge label (b* - L*)
        mid_CA = ((C[0] + A[0])/2 - mid_offset, (C[1] + A[1])/2)  # Increased offset
        self.ax.text(mid_CA[0], mid_CA[1], 'b* ↔ L*', 
                    fontsize=10, ha='center', va='center', style='italic',
                    rotation=60, color='darkred')  # Fixed rotation to match edge
        
        # Add tick marks and percentage labels
        self._add_ternary_tick_marks(A, B, C)
        
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
        # Tick positions (0%, 20%, 40%, 60%, 80%, 100%)
        ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        tick_labels = ['0%', '20%', '40%', '60%', '80%', '100%']
        
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