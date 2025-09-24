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

        # Open
        ttk.Button(self.side, text="Open Data (ODS/XLSX/CSV)", command=self._open_file).pack(fill=tk.X, pady=4)
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
        A = (0.0, 0.0)
        B = (1.0, 0.0)
        C = (0.5, h)
        # Draw triangle
        self.ax.plot([A[0], B[0]], [A[1], B[1]], color='black', lw=1.0)
        self.ax.plot([B[0], C[0]], [B[1], C[1]], color='black', lw=1.0)
        self.ax.plot([C[0], A[0]], [C[1], A[1]], color='black', lw=1.0)
        # Ticks or grid (simple)
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_xlim(-0.05, 1.05)
        self.ax.set_ylim(-0.05, h + 0.05)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_xlabel('a* proportion')
        self.ax.set_ylabel('b* proportion')

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