import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
        
        # Refresh
        ttk.Button(self.side, text="Refresh Plot", command=self._render).pack(fill=tk.X, pady=4)

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
            self._render()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n\n{e}")

    def _load_from_realtime_db(self):
        """Load data from the realtime datasheet database."""
        try:
            # Import the database module
            from utils.color_analysis_db import ColorAnalysisDB
            import os
            import glob
            from tkinter import simpledialog
            
            # Find available databases
            db_dir = os.path.join(os.getcwd(), 'data', 'color_analysis')
            if not os.path.exists(db_dir):
                messagebox.showerror("Error", "No color analysis databases found.")
                return
            
            db_files = glob.glob(os.path.join(db_dir, '*.db'))
            if not db_files:
                messagebox.showerror("Error", "No database files found in data/color_analysis.")
                return
            
            # Show available databases
            db_names = [os.path.splitext(os.path.basename(f))[0] for f in db_files]
            if len(db_names) == 1:
                selected_db = db_names[0]
            else:
                # Simple selection dialog
                selection_text = "Available databases:\n" + "\n".join([f"{i+1}. {name}" for i, name in enumerate(db_names)])
                selection_text += "\n\nEnter number (1-{}):".format(len(db_names))
                
                choice = simpledialog.askstring("Select Database", selection_text)
                if not choice:
                    return
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(db_names):
                        selected_db = db_names[idx]
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
                return
            
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
            
            messagebox.showinfo("Success", f"Loaded {len(measurements)} measurements from '{selected_db}' database.")
            
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"Failed to load from realtime database:\n\n{e}\n\nDetails:\n{traceback.format_exc()}")

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

        # Plot points with marker and color
        markers = df.get('Marker', pd.Series(['.'] * len(df))).fillna('.')
        colors = df.get('Color', pd.Series(['blue'] * len(df))).fillna('blue')
        for i in range(len(df)):
            m = markers.iloc[i]
            c = colors.iloc[i]
            self.ax.scatter([x[i]], [y[i]], s=40, marker=m if str(m) else '.', c=c if str(c) else 'blue', edgecolors='black', linewidths=0.3, alpha=0.9)

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
        
        # Configure plot
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_xlim(-0.20, 1.20)  # More space for labels
        self.ax.set_ylim(-0.20, h + 0.20)  # More space for labels
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