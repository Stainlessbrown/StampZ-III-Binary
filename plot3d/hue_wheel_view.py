#!/usr/bin/env python3
"""
Hue Wheel Polar Plot Viewer for StampZ Color Analysis
Visualizes L*C*h color data on a polar plot (hue wheel)
"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd


class HueWheelViewer:
    """Polar plot viewer for L*C*h color data."""
    
    def __init__(self, parent=None, dataframe=None, title="Hue Wheel Analysis"):
        """
        Initialize the Hue Wheel Viewer.
        
        Args:
            parent: Parent tkinter window
            dataframe: DataFrame containing L*C*h data (columns N, O, P expected)
            title: Window title
        """
        self.parent = parent
        self.df = dataframe
        self.title = title
        
        # Validate data
        if self.df is None or self.df.empty:
            messagebox.showerror("No Data", "No color data available for hue wheel visualization.")
            return
        
        # Check for L*C*h columns (expected in columns N, O, P)
        # Column names might vary, so check both by name and by position
        self._identify_lch_columns()
        
        if not self._has_valid_lch_data():
            messagebox.showwarning(
                "Missing Data",
                "L*C*h data not found in the expected columns.\n\n"
                "Expected:\n"
                "• Column N: Lightness (L*)\n"
                "• Column O: Chroma (C*)\n"
                "• Column P: Hue (h)\n\n"
                "Please ensure your data template includes L*C*h calculations."
            )
            return
        
        # Create window
        self._create_window()
        self._create_plot()
    
    def _identify_lch_columns(self):
        """Identify L*C*h columns in the dataframe."""
        # Try to find columns by name first
        col_names = [col.lower() for col in self.df.columns]
        
        # Look for lightness
        self.l_col = None
        for i, name in enumerate(col_names):
            if 'lightness' in name or 'l*' in name or name == 'l':
                self.l_col = self.df.columns[i]
                break
        
        # Look for chroma
        self.c_col = None
        for i, name in enumerate(col_names):
            if 'chroma' in name or 'c*' in name or name == 'c':
                self.c_col = self.df.columns[i]
                break
        
        # Look for hue
        self.h_col = None
        for i, name in enumerate(col_names):
            if 'hue' in name or name == 'h' or name == 'h*':
                self.h_col = self.df.columns[i]
                break
        
        # Fallback to positional if not found by name
        # Assuming columns N (13), O (14), P (15) in 0-indexed
        if self.l_col is None and len(self.df.columns) > 13:
            self.l_col = self.df.columns[13]
        if self.c_col is None and len(self.df.columns) > 14:
            self.c_col = self.df.columns[14]
        if self.h_col is None and len(self.df.columns) > 15:
            self.h_col = self.df.columns[15]
        
        print(f"DEBUG: Identified L*C*h columns: L={self.l_col}, C={self.c_col}, H={self.h_col}")
    
    def _has_valid_lch_data(self):
        """Check if we have valid L*C*h data."""
        if self.l_col is None or self.c_col is None or self.h_col is None:
            return False
        
        # Check if columns exist and have data
        try:
            l_data = pd.to_numeric(self.df[self.l_col], errors='coerce')
            c_data = pd.to_numeric(self.df[self.c_col], errors='coerce')
            h_data = pd.to_numeric(self.df[self.h_col], errors='coerce')
            
            # Check if we have at least one valid data point
            valid_count = (~l_data.isna() & ~c_data.isna() & ~h_data.isna()).sum()
            return valid_count > 0
        except Exception as e:
            print(f"DEBUG: Error checking L*C*h data: {e}")
            return False
    
    def _create_window(self):
        """Create the viewer window."""
        if self.parent:
            self.root = tk.Toplevel(self.parent)
        else:
            self.root = tk.Tk()
        
        self.root.title(self.title)
        self.root.geometry("900x800")
        
        # Create main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info label at top
        info_text = (
            "Hue Wheel: Angle = Hue (0-360°), Radius = Chroma, "
            "Color intensity = Lightness (L*). Use toolbar to zoom/pan."
        )
        info_label = ttk.Label(
            main_frame,
            text=info_text,
            font=("Arial", 10),
            foreground="gray"
        )
        info_label.pack(pady=(0, 10))
        
        # Marker size control
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(control_frame, text="Marker Size:").pack(side=tk.LEFT, padx=(0, 5))
        self.marker_size = tk.IntVar(value=50)
        marker_scale = ttk.Scale(
            control_frame,
            from_=10,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.marker_size,
            command=lambda v: self._create_plot()
        )
        marker_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(control_frame, textvariable=self.marker_size).pack(side=tk.LEFT, padx=(5, 0))
        
        # Create plot frame (constrained height to ensure buttons are visible)
        self.plot_frame = ttk.Frame(main_frame, height=600)
        self.plot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.plot_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Create toolbar frame between plot and buttons
        self.toolbar_frame = ttk.Frame(main_frame, relief=tk.RIDGE, borderwidth=2)
        self.toolbar_frame.pack(fill=tk.X, pady=(5, 5))
        
        # Create button frame at bottom (always visible)
        button_frame = ttk.Frame(main_frame, relief=tk.RAISED, borderwidth=1)
        button_frame.pack(fill=tk.X, pady=(5, 0), side=tk.BOTTOM)
        
        ttk.Button(
            button_frame,
            text="🔄 Refresh",
            command=self._create_plot,
            width=10
        ).pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="Close",
            command=self.root.destroy,
            width=10
        ).pack(side=tk.RIGHT, padx=5, pady=5)
    
    def _reset_zoom(self, ax):
        """Reset zoom to original view."""
        if hasattr(self, 'original_r_lim'):
            ax.set_ylim(self.original_r_lim)
            self.canvas.draw()
    
    def _setup_interactive_zoom(self, ax):
        """Setup interactive box zoom with mouse click and drag."""
        self.zoom_start = None
        self.zoom_rect_patch = None
        self.drag_threshold = 0.02  # Minimum movement to be considered a drag
        
        def on_press(event):
            if event.inaxes != ax or event.button != 1:  # Only left click
                return
            self.zoom_start = (event.xdata, event.ydata, event.x, event.y)  # Store both data and pixel coords
            print(f"DEBUG: Mouse down at theta={event.xdata:.2f}, r={event.ydata:.1f}")
            
        def on_motion(event):
            if self.zoom_start is None or event.inaxes != ax:
                return
            
            # Remove old rectangle if it exists
            if self.zoom_rect_patch is not None:
                self.zoom_rect_patch.remove()
                self.zoom_rect_patch = None
            
            if event.xdata is None or event.ydata is None:
                return
                
            # Draw zoom rectangle for visual feedback
            theta_start, r_start, _, _ = self.zoom_start  # Unpack all 4 values
            theta_end, r_end = event.xdata, event.ydata
            
            theta_min = min(theta_start, theta_end)
            theta_max = max(theta_start, theta_end)
            r_min = min(r_start, r_end)
            r_max = max(r_start, r_end)
            
            # Draw multiple lines to show the zoom box in polar coordinates
            # This is more reliable than Wedge patches
            from matplotlib.patches import Polygon
            
            # Create points along the zoom box boundary
            n_points = 20
            theta_range = np.linspace(theta_min, theta_max, n_points)
            
            # Build polygon points: outer arc, then inner arc reversed
            points = []
            # Outer arc
            for t in theta_range:
                points.append((t, r_max))
            # Inner arc (reversed)
            for t in reversed(theta_range):
                points.append((t, r_min))
            
            # Create polygon patch
            self.zoom_rect_patch = Polygon(
                points,
                closed=True,
                facecolor='yellow',
                edgecolor='red',
                alpha=0.3,
                linewidth=2
            )
            ax.add_patch(self.zoom_rect_patch)
            self.canvas.draw_idle()
            
        def on_release(event):
            # Remove visual feedback rectangle
            if self.zoom_rect_patch is not None:
                self.zoom_rect_patch.remove()
                self.zoom_rect_patch = None
            
            if self.zoom_start is None:
                self.canvas.draw_idle()
                return
            
            # Check if this was a drag or just a click
            theta_start, r_start, x_start, y_start = self.zoom_start
            
            if event.inaxes != ax:
                self.zoom_start = None
                self.canvas.draw_idle()
                return
                
            if event.xdata is None or event.ydata is None:
                self.zoom_start = None
                self.canvas.draw_idle()
                return
            
            # Calculate movement in pixels
            pixel_distance = np.sqrt((event.x - x_start)**2 + (event.y - y_start)**2)
            
            # If moved less than threshold, it's a click not a drag - let pick event handle it
            if pixel_distance < 5:  # Less than 5 pixels = click
                print(f"DEBUG: Click detected (moved {pixel_distance:.1f} pixels), not zooming")
                self.zoom_start = None
                self.canvas.draw_idle()
                return
            
            # Get zoom box corners
            theta_end, r_end = event.xdata, event.ydata
            
            # Ensure proper ordering
            theta_min = min(theta_start, theta_end)
            theta_max = max(theta_start, theta_end)
            r_min = min(r_start, r_end)
            r_max = max(r_start, r_end)
            
            print(f"DEBUG: Drag detected - Zoom box - theta: {np.rad2deg(theta_min):.1f}° to {np.rad2deg(theta_max):.1f}°, r: {r_min:.1f} to {r_max:.1f}")
            
            # Only zoom if dragged area is significant
            if abs(r_max - r_min) > 1 and abs(theta_max - theta_min) > 0.05:
                # Set new limits
                ax.set_ylim(r_min, r_max)
                ax.set_xlim(theta_min, theta_max)
                print(f"DEBUG: Zooming to selected region")
                self.canvas.draw()
            else:
                print(f"DEBUG: Zoom box too small, ignoring")
                self.canvas.draw_idle()
            
            self.zoom_start = None
        
        # Connect events
        self.canvas.mpl_connect('button_press_event', on_press)
        self.canvas.mpl_connect('motion_notify_event', on_motion)
        self.canvas.mpl_connect('button_release_event', on_release)
    
    def _setup_point_identification(self, ax):
        """Setup point identification on right-click."""
        self.annotation = None
        self.highlighted_point = None
        
        def on_pick(event):
            """Handle point click for identification."""
            print(f"DEBUG: Pick event triggered! Event type: {type(event)}")
            
            if not hasattr(self, 'point_data'):
                print(f"DEBUG: No point_data available")
                return
            
            # Get the indices of picked points
            print(f"DEBUG: event.ind = {event.ind}")
            ind = event.ind[0] if len(event.ind) > 0 else None
            if ind is None:
                print(f"DEBUG: No point index found")
                return
            
            print(f"DEBUG: Point index {ind} selected")
            
            # Clear previous highlight
            if self.highlighted_point is not None:
                self.highlighted_point.remove()
                self.highlighted_point = None
            
            # Clear previous annotation
            if self.annotation is not None:
                self.annotation.remove()
                self.annotation = None
            
            # Get point data
            theta_val = self.point_data['theta'][ind]
            r_val = self.point_data['r'][ind]
            h_val = self.point_data['h_values'][ind]
            c_val = self.point_data['c_values'][ind]
            l_val = self.point_data['l_values'][ind]
            
            # Get sample name/ID if available
            df_idx = self.point_data['indices'][ind]
            sample_name = "Unknown"
            if hasattr(self, 'df') and df_idx < len(self.df):
                row = self.df.iloc[df_idx]
                # Try common column names for sample ID
                for col in ['Sample', 'DataID', 'ID', 'Name']:
                    if col in row.index and pd.notna(row[col]):
                        sample_name = str(row[col])
                        break
            
            print(f"DEBUG: Clicked point - Sample: {sample_name}, Hue: {h_val:.1f}°, Chroma: {c_val:.1f}, L*: {l_val:.1f}")
            
            # Highlight the selected point
            self.highlighted_point = ax.scatter(
                [theta_val], [r_val],
                s=200, facecolors='none', edgecolors='red',
                linewidths=3, zorder=10
            )
            
            # Add annotation with point information
            annotation_text = f"{sample_name}\nH: {h_val:.1f}°\nC: {c_val:.1f}\nL*: {l_val:.1f}"
            self.annotation = ax.annotate(
                annotation_text,
                xy=(theta_val, r_val),
                xytext=(20, 20),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8, edgecolor='red'),
                fontsize=10,
                fontweight='bold',
                zorder=11
            )
            
            self.canvas.draw_idle()
        
        # Connect pick event
        self.canvas.mpl_connect('pick_event', on_pick)
    
    def _create_plot(self):
        """Create the polar hue wheel plot."""
        # Clear existing plot
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        
        # Close previous figure to prevent memory leak
        if hasattr(self, 'fig') and self.fig is not None:
            plt.close(self.fig)
        
        # Extract L*C*h data
        try:
            l_data = pd.to_numeric(self.df[self.l_col], errors='coerce')
            c_data = pd.to_numeric(self.df[self.c_col], errors='coerce')
            h_data = pd.to_numeric(self.df[self.h_col], errors='coerce')
            
            # Remove NaN values
            valid_mask = ~l_data.isna() & ~c_data.isna() & ~h_data.isna()
            l_values = l_data[valid_mask].values
            c_values = c_data[valid_mask].values
            h_values = h_data[valid_mask].values
            
            if len(h_values) == 0:
                messagebox.showwarning("No Data", "No valid L*C*h data points found.")
                return
            
            print(f"DEBUG: Plotting {len(h_values)} points on hue wheel")
            print(f"DEBUG: Hue range: {h_values.min():.1f}° to {h_values.max():.1f}°")
            print(f"DEBUG: Chroma range: {c_values.min():.1f} to {c_values.max():.1f}")
            print(f"DEBUG: Lightness range: {l_values.min():.1f} to {l_values.max():.1f}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract L*C*h data:\n{e}")
            return
        
        # Create figure with polar projection
        self.fig = plt.figure(figsize=(10, 10))
        ax = self.fig.add_subplot(111, projection='polar')
        
        # Draw colored hue wheel ring on outer edge
        # Create a ring of colors representing the full hue spectrum
        hue_angles = np.linspace(0, 360, 360)  # One point per degree
        hue_radians = np.deg2rad(hue_angles)
        max_chroma = np.max(c_values) * 1.1  # Match the data extent + padding
        ring_radius = np.full_like(hue_angles, max_chroma)
        
        # Convert hue to RGB colors
        # For each hue angle, create a color at full saturation and mid-lightness
        from matplotlib.colors import hsv_to_rgb
        ring_colors = []
        for h in hue_angles:
            # HSV: H in [0,1], S=1 (full saturation), V=0.9 (bright)
            hsv = np.array([h/360.0, 1.0, 0.9])
            rgb = hsv_to_rgb(hsv)
            ring_colors.append(rgb)
        
        # Plot the colored ring using scatter with small overlapping points
        ax.scatter(
            hue_radians,
            ring_radius,
            c=ring_colors,
            s=150,  # Size to ensure overlap and solid appearance
            alpha=0.8,
            edgecolors='none',
            zorder=1  # Behind data points
        )
        
        # Convert hue to radians
        theta = np.deg2rad(h_values)
        
        # Use chroma as radius
        r = c_values
        
        # Normalize lightness for color mapping (0-100 → 0-1)
        # Darker points = lower L*, lighter points = higher L*
        l_normalized = l_values / 100.0
        
        # Create scatter plot with pickable points
        # Use a colormap that shows lightness variation
        marker_size = getattr(self, 'marker_size', None)
        size_value = marker_size.get() if marker_size else 50
        
        # Store data for point identification
        self.point_data = {
            'theta': theta,
            'r': r,
            'h_values': h_values,
            'c_values': c_values,
            'l_values': l_values,
            'indices': valid_mask[valid_mask].index.tolist()  # Store original DataFrame indices
        }
        
        scatter = ax.scatter(
            theta,
            r,
            c=l_normalized,
            cmap='viridis',  # Viridis: dark purple (low L*) to bright yellow (high L*)
            s=size_value,  # Adjustable point size
            alpha=0.8,
            edgecolors='black',
            linewidth=0.5,
            zorder=2,  # In front of colored ring
            picker=True,  # Enable picking
            pickradius=5  # Click tolerance in pixels
        )
        
        # Add colorbar for lightness
        cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
        cbar.set_label('Lightness (L*)', rotation=270, labelpad=20, fontsize=12)
        # Fix colorbar labels more carefully to avoid warnings
        try:
            tick_locs = cbar.ax.get_yticks()
            cbar.ax.set_yticks(tick_locs)
            cbar.ax.set_yticklabels([f'{int(val*100)}' for val in tick_locs])
        except:
            pass  # Skip if colorbar formatting fails
        
        # Configure polar plot
        ax.set_theta_zero_location('N')  # 0° at top (red)
        ax.set_theta_direction(-1)  # Clockwise
        
        # Set radial limits - use full data range with padding
        max_chroma = np.max(r) * 1.1  # Add 10% padding
        ax.set_ylim(0, max_chroma)
        ax.set_ylabel('Chroma (C*)', fontsize=12, labelpad=30)
        
        # Add hue angle labels
        ax.set_xticks(np.deg2rad([0, 45, 90, 135, 180, 225, 270, 315]))
        ax.set_xticklabels(['0°\n(Red)', '45°', '90°\n(Yellow)', '135°', 
                           '180°\n(Green)', '225°', '270°\n(Blue)', '315°'])
        
        # Title
        ax.set_title(
            f'Hue Wheel Analysis\n{len(h_values)} color points',
            fontsize=14,
            fontweight='bold',
            pad=20
        )
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Embed plot in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add matplotlib toolbar
        # Clear any existing toolbar widgets
        for widget in self.toolbar_frame.winfo_children():
            widget.destroy()
        
        # Add reset button and instructions
        controls_left = ttk.Frame(self.toolbar_frame)
        controls_left.pack(side=tk.LEFT, padx=5, pady=2)
        
        ttk.Label(controls_left, text="Click & drag to zoom |").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_left, text="🏠 Reset View", command=lambda: self._reset_zoom(ax), width=12).pack(side=tk.LEFT, padx=2)
        
        # Store axis and original limits for zoom
        self.current_ax = ax
        self.original_r_lim = ax.get_ylim()
        
        # Enable interactive box zoom with mouse (left-click drag)
        self._setup_interactive_zoom(ax)
        
        # Enable point identification (click on points)
        self._setup_point_identification(ax)
        
        try:
            # Try to add matplotlib toolbar for Save functionality
            controls_right = ttk.Frame(self.toolbar_frame)
            controls_right.pack(side=tk.RIGHT, padx=5)
            toolbar = NavigationToolbar2Tk(self.canvas, controls_right)
            toolbar.update()
            # Hide non-working buttons, keep only Save and Configure
            for child in toolbar.winfo_children():
                try:
                    child_type = str(type(child))
                    # Keep the widget visible
                    pass
                except:
                    pass
            print(f"DEBUG: Toolbar created successfully")
        except Exception as e:
            print(f"DEBUG: Failed to create toolbar: {e}")
    
    def show(self):
        """Show the window (for standalone use)."""
        if hasattr(self, 'root'):
            self.root.mainloop()


def open_hue_wheel_view(parent=None, dataframe=None):
    """
    Convenience function to open hue wheel viewer.
    
    Args:
        parent: Parent window
        dataframe: DataFrame with L*C*h data
    """
    viewer = HueWheelViewer(parent=parent, dataframe=dataframe)
    return viewer


# Standalone testing
if __name__ == "__main__":
    # Create test data
    test_data = {
        'Sample': range(1, 21),
        'Lightness (L*)': np.random.uniform(30, 90, 20),
        'Chroma (C*)': np.random.uniform(10, 60, 20),
        'Hue (h)': np.random.uniform(0, 360, 20)
    }
    df = pd.DataFrame(test_data)
    
    viewer = HueWheelViewer(dataframe=df, title="Test Hue Wheel")
    viewer.show()
