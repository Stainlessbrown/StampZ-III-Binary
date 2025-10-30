"""
Gauge-Based Perforation Measurement UI for StampZ

Integrates the traditional gauge overlay system with the existing StampZ
perforation measurement workflow and data logging.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import os
from typing import Optional, Tuple, List
import threading

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our new gauge system
from final_perforation_gauge import FinalPerforationGauge

# Import existing logging functionality
try:
    from perforation_measurement_system import PerforationAnalysis, PerforationEdge, PerforationHole
    from utils.unified_data_logger import UnifiedDataLogger
except ImportError:
    print("Warning: Could not import some measurement system components")


class GaugePerforationDialog:
    """Dialog for gauge-based perforation measurement."""
    
    def __init__(self, parent, image_array: np.ndarray = None, image_filename: str = ""):
        self.parent = parent
        self.image_array = image_array
        self.image_filename = image_filename
        self.current_gauge_overlay = None
        self.overlay_orientation = 'horizontal'
        self.overlay_position = (0, 0)
        self.is_dragging = False
        self.drag_start = None
        self.scale_factor = 1.0
        self.gauge_system = None
        
        # Measured perforation values
        self.horizontal_measurement = None
        self.vertical_measurement = None
        
        # Create the dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("StampZ - Gauge Perforation Measurement")
        self.dialog.geometry("1200x800")
        self.dialog.resizable(True, True)
        
        # Bind window resize event to update image fitting
        self.dialog.bind('<Configure>', self._on_window_resize)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create UI components
        self._create_widgets()
        self._setup_layout()
        self._bind_events()
        
        # If we have an image, display it
        if image_array is not None:
            self._display_image(image_array)
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main container
        self.main_frame = ttk.Frame(self.dialog)
        
        # Left panel for image display
        self.image_frame = ttk.LabelFrame(self.main_frame, text="Stamp Image with Gauge Overlay")
        self.image_canvas = tk.Canvas(self.image_frame, bg='white', width=800, height=600)
        self.image_scrollbar_v = ttk.Scrollbar(self.image_frame, orient=tk.VERTICAL, command=self.image_canvas.yview)
        self.image_scrollbar_h = ttk.Scrollbar(self.image_frame, orient=tk.HORIZONTAL, command=self.image_canvas.xview)
        self.image_canvas.configure(yscrollcommand=self.image_scrollbar_v.set, xscrollcommand=self.image_scrollbar_h.set)
        
        # Right panel for controls and results
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Gauge Controls")
        
        # DPI Settings
        self.dpi_frame = ttk.Frame(self.control_frame)
        ttk.Label(self.dpi_frame, text="Image DPI:").pack(side=tk.LEFT)
        
        # Get default DPI from preferences
        default_dpi = "800"  # fallback
        try:
            from utils.user_preferences import get_preferences_manager
            prefs_manager = get_preferences_manager()
            default_dpi = str(prefs_manager.get_default_dpi())
        except:
            pass
            
        self.dpi_var = tk.StringVar(value=default_dpi)
        self.dpi_entry = ttk.Entry(self.dpi_frame, textvariable=self.dpi_var, width=8, state='readonly')
        self.dpi_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(self.dpi_frame, text="(Set in Preferences)", font=("TkDefaultFont", 9), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Color Scheme Selection removed - traditional white/black only
        
        # Gauge Orientation
        self.orientation_frame = ttk.Frame(self.control_frame)
        ttk.Label(self.orientation_frame, text="Gauge Orientation:").pack(side=tk.LEFT)
        
        self.orientation_var = tk.StringVar(value="horizontal")
        ttk.Radiobutton(self.orientation_frame, text="Horizontal", 
                       variable=self.orientation_var, value="horizontal",
                       command=self._change_orientation).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.orientation_frame, text="Vertical", 
                       variable=self.orientation_var, value="vertical",
                       command=self._change_orientation).pack(side=tk.LEFT, padx=5)
        
        # File Operations (moved to top for better workflow)
        self.file_frame = ttk.Frame(self.control_frame)
        self.load_image_btn = ttk.Button(
            self.file_frame,
            text="📁 Load Image", 
            command=self._load_image
        )
        self.fit_window_btn = ttk.Button(
            self.file_frame,
            text="🔍 Fit to Window (before gauge)",
            command=self._fit_to_window,
            state='disabled'
        )
        
        # Auto-fit checkbox
        self.auto_fit_var = tk.BooleanVar(value=False)  # Disable auto-fit by default to avoid scaling issues
        self.auto_fit_check = ttk.Checkbutton(
            self.file_frame,
            text="Auto-fit on resize",
            variable=self.auto_fit_var,
            command=self._toggle_auto_fit
        )
        
        # Gauge Control Buttons
        self.gauge_button_frame = ttk.Frame(self.control_frame)
        self.show_gauge_btn = ttk.Button(
            self.gauge_button_frame, 
            text="📏 Show Gauge",
            command=self._show_gauge
        )
        self.hide_gauge_btn = ttk.Button(
            self.gauge_button_frame,
            text="👁️ Hide Gauge", 
            command=self._hide_gauge,
            state='disabled'
        )
        self.center_gauge_btn = ttk.Button(
            self.gauge_button_frame,
            text="🎯 Center Gauge",
            command=self._center_gauge,
            state='disabled'
        )
        
        # Measurement Buttons
        self.measure_frame = ttk.Frame(self.control_frame)
        self.record_h_btn = ttk.Button(
            self.measure_frame,
            text="📊 Record Horizontal",
            command=self._record_horizontal_measurement,
            state='disabled'
        )
        self.record_v_btn = ttk.Button(
            self.measure_frame,
            text="📊 Record Vertical", 
            command=self._record_vertical_measurement,
            state='disabled'
        )
        
        # Save button
        self.save_frame = ttk.Frame(self.control_frame)
        self.save_data_btn = ttk.Button(
            self.save_frame,
            text="💾 Save Measurements",
            command=self._save_measurements,
            state='disabled'
        )
        
        # Direct entry fields for measurements
        self.entry_frame = ttk.LabelFrame(self.control_frame, text="Quick Entry")
        
        # Horizontal entry
        h_entry_frame = ttk.Frame(self.entry_frame)
        ttk.Label(h_entry_frame, text="Horizontal:").pack(side=tk.LEFT, padx=(0,5))
        self.h_entry_var = tk.StringVar()
        self.h_entry_var.trace_add('write', self._on_entry_change)
        self.h_entry = ttk.Entry(h_entry_frame, textvariable=self.h_entry_var, width=10)
        self.h_entry.pack(side=tk.LEFT)
        
        # Vertical entry  
        v_entry_frame = ttk.Frame(self.entry_frame)
        ttk.Label(v_entry_frame, text="Vertical:").pack(side=tk.LEFT, padx=(0,5))
        self.v_entry_var = tk.StringVar()
        self.v_entry_var.trace_add('write', self._on_entry_change)
        self.v_entry = ttk.Entry(v_entry_frame, textvariable=self.v_entry_var, width=10)
        self.v_entry.pack(side=tk.LEFT)
        
        # Notes field
        notes_label_frame = ttk.Frame(self.entry_frame)
        ttk.Label(notes_label_frame, text="Notes:").pack(anchor=tk.W)
        self.notes_text = tk.Text(self.entry_frame, height=3, width=30, wrap=tk.WORD)
        
        # Results display
        self.results_frame = ttk.LabelFrame(self.control_frame, text="Summary")
        self.results_text = tk.Text(self.results_frame, height=10, width=35, wrap=tk.WORD)
        self.results_scrollbar = ttk.Scrollbar(self.results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=self.results_scrollbar.set)
        
        # Instructions
        self.instructions_frame = ttk.LabelFrame(self.control_frame, text="Workflow")
        instructions = (
            "1. Load image\n"
            "2. Fit to Window (important!)\n"
            "3. Show gauge overlay\n" 
            "4. Drag to align with perforations\n"
            "5. Switch H/V & record both\n"
            "6. Save measurements"
        )
        self.instructions_label = ttk.Label(self.instructions_frame, text=instructions, 
                                          justify=tk.LEFT, font=("TkDefaultFont", 9))
        
        # Status
        self.status_var = tk.StringVar(value="Ready - Load image or show gauge")
        self.status_label = ttk.Label(self.control_frame, textvariable=self.status_var, foreground="blue")
        
        # Bottom buttons
        self.bottom_frame = ttk.Frame(self.main_frame)
        self.close_btn = ttk.Button(self.bottom_frame, text="Close", command=self._close_dialog)
        self.help_btn = ttk.Button(self.bottom_frame, text="Help", command=self._show_help)
    
    def _setup_layout(self):
        """Arrange widgets in the dialog."""
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left side - image display
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.image_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.image_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
        self.image_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Right side - controls
        self.control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0), ipadx=5)
        
        # Pack control sections in workflow order
        # File operations first (workflow steps 1-2)
        self.file_frame.pack(fill=tk.X, pady=5)
        self.load_image_btn.pack(fill=tk.X, pady=1)
        self.fit_window_btn.pack(fill=tk.X, pady=1)
        self.auto_fit_check.pack(fill=tk.X, pady=1)
        
        ttk.Separator(self.control_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        self.dpi_frame.pack(fill=tk.X, pady=3)
        self.orientation_frame.pack(fill=tk.X, pady=5)
        
        # Gauge buttons (workflow step 3)
        self.gauge_button_frame.pack(fill=tk.X, pady=5)
        self.show_gauge_btn.pack(fill=tk.X, pady=1)
        self.hide_gauge_btn.pack(fill=tk.X, pady=1)
        self.center_gauge_btn.pack(fill=tk.X, pady=1)
        
        ttk.Separator(self.control_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # Measurement buttons (workflow steps 4-5)
        self.measure_frame.pack(fill=tk.X, pady=5)
        self.record_h_btn.pack(fill=tk.X, pady=1)
        self.record_v_btn.pack(fill=tk.X, pady=1)
        
        ttk.Separator(self.control_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # Save button (workflow step 6)
        self.save_frame.pack(fill=tk.X, pady=5)
        self.save_data_btn.pack(fill=tk.X, pady=1)
        
        ttk.Separator(self.control_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # Quick entry fields
        self.entry_frame.pack(fill=tk.X, pady=5)
        h_entry_frame.pack(fill=tk.X, pady=2)
        v_entry_frame.pack(fill=tk.X, pady=2)
        notes_label_frame.pack(fill=tk.X, pady=(5,2))
        self.notes_text.pack(fill=tk.X, pady=2)
        
        # Results summary
        self.results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Instructions
        self.instructions_frame.pack(fill=tk.X, pady=3)
        self.instructions_label.pack(fill=tk.X, padx=5, pady=3)
        
        # Status
        self.status_label.pack(fill=tk.X, pady=2)
        
        # Bottom buttons
        self.bottom_frame.pack(fill=tk.X, pady=(10, 0))
        self.help_btn.pack(side=tk.LEFT)
        self.close_btn.pack(side=tk.RIGHT)
    
    def _bind_events(self):
        """Bind mouse events for gauge manipulation."""
        self.image_canvas.bind("<Button-1>", self._on_canvas_click)
        self.image_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.image_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        
        # Track resize events for auto-fitting
        self._resize_after_id = None
        
    def _on_window_resize(self, event):
        """Handle window resize events with debouncing."""
        # Only react to main dialog resize, not child widgets
        if event.widget != self.dialog:
            return
            
        # Debounce rapid resize events
        if self._resize_after_id:
            self.dialog.after_cancel(self._resize_after_id)
        
        # Schedule auto-fit after resize settles (500ms delay)
        self._resize_after_id = self.dialog.after(500, self._auto_fit_on_resize)
    
    def _auto_fit_on_resize(self):
        """Auto-fit image when window is resized (if auto-fit is enabled)."""
        self._resize_after_id = None
        # Only auto-fit if we have an image and user hasn't manually scaled
        if hasattr(self, 'base_image') and hasattr(self, '_auto_fit_enabled'):
            if self._auto_fit_enabled:
                self._fit_to_window()
        
    def _display_image(self, image_array: np.ndarray):
        """Display the image in the canvas."""
        try:
            # Validate input image
            if image_array is None or image_array.size == 0:
                return
                
            # Convert from BGR to RGB if needed (OpenCV uses BGR, PIL uses RGB)
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                # Use cv2 for proper conversion to maintain exact compatibility
                import cv2
                display_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            else:
                display_array = image_array
            
            # Convert to PIL Image
            self.base_image = Image.fromarray(display_array)
            
            # Calculate scale factor to fit in canvas
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()
            
            if canvas_width <= 1:  # Canvas not yet sized
                canvas_width = 600
                canvas_height = 500
            
            img_width, img_height = self.base_image.size
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            # Allow scaling up for small images, but be reasonable about it
            max_scale = 3.0  # Allow up to 3x scaling
            self.scale_factor = min(scale_x, scale_y, max_scale)
            
            # Create display image
            if self.scale_factor < 1.0:
                display_size = (int(img_width * self.scale_factor), int(img_height * self.scale_factor))
                self.display_image = self.base_image.resize(display_size, Image.LANCZOS)
            else:
                self.display_image = self.base_image.copy()
            
            # Display the image
            self._update_canvas_display()
            
            # Initialize gauge system with current DPI
            dpi = int(self.dpi_var.get()) if self.dpi_var.get().isdigit() else 800
            self.gauge_system = FinalPerforationGauge(dpi=dpi)
            
            # Enable fit to window button
            self.fit_window_btn.configure(state='normal')
            
            # Set auto-fit enabled state
            self._auto_fit_enabled = self.auto_fit_var.get()
            
            # Skip auto-fit for testing
            
            self.status_var.set(f"Image loaded - {img_width}x{img_height} pixels (scale: {self.scale_factor:.2f}x)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display image: {str(e)}")
    
    def _update_canvas_display(self):
        """Update the canvas with the current display image."""
        try:
            if hasattr(self, 'display_image'):
                self.photo = ImageTk.PhotoImage(self.display_image)
                self.image_canvas.delete("all")
                self.image_canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
                self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))
        except Exception as e:
            print(f"Failed to update canvas: {e}")
    
    def _show_gauge(self):
        """Show the gauge overlay on the image."""
        if not hasattr(self, 'base_image') or self.gauge_system is None:
            messagebox.showwarning("No Image", "Please load an image first")
            return
        
        try:
            # Create gauge overlay accounting for display scaling
            img_width, img_height = self.base_image.size
            
            # Calculate display-scaled dimensions and DPI
            display_width = int(img_width * self.scale_factor)
            display_height = int(img_height * self.scale_factor)
            display_dpi = int(self.gauge_system.dpi * self.scale_factor)
            
            # Create gauge system at display-scaled DPI
            display_gauge_system = FinalPerforationGauge(dpi=display_dpi)
            overlay = display_gauge_system.create_gauge_overlay(display_width, display_height)
            
            # Rotate if vertical orientation
            if self.orientation_var.get() == 'vertical':
                overlay = display_gauge_system.rotate_90(overlay)
            
            # Convert overlay to PIL Image
            overlay_pil = Image.fromarray(overlay, 'RGBA')
            
            # Create display-sized composite
            composite = Image.new('RGBA', (display_width, display_height))
            
            # Scale base image to display size
            scaled_base = self.base_image.resize((display_width, display_height), Image.LANCZOS)
            composite.paste(scaled_base.convert('RGBA'), (0, 0))
            
            # Position overlay (start centered) - now in display coordinates
            overlay_x = (display_width - overlay_pil.width) // 2
            overlay_y = (display_height - overlay_pil.height) // 2
            self.overlay_position = (overlay_x, overlay_y)  # Store in display coordinates
            
            composite.paste(overlay_pil, self.overlay_position, overlay_pil)
            
            # Use composite directly as display image (already at correct scale)
            self.display_image = composite
            
            self.current_gauge_overlay = overlay_pil
            self._update_canvas_display()
            
            # Update button states
            self.show_gauge_btn.configure(state='disabled')
            self.hide_gauge_btn.configure(state='normal')
            self.center_gauge_btn.configure(state='normal')
            self.record_h_btn.configure(state='normal')
            self.record_v_btn.configure(state='normal')
            
            self.status_var.set("Gauge overlay active - drag to position")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show gauge: {str(e)}")
    
    def _hide_gauge(self):
        """Hide the gauge overlay."""
        if hasattr(self, 'base_image'):
            # Reset to original image scaled for display using CURRENT scale factor
            img_width, img_height = self.base_image.size
            display_size = (int(img_width * self.scale_factor), int(img_height * self.scale_factor))
            self.display_image = self.base_image.resize(display_size, Image.LANCZOS)
            
            self.current_gauge_overlay = None
            self._update_canvas_display()
            
            # Update button states
            self.show_gauge_btn.configure(state='normal')
            self.hide_gauge_btn.configure(state='disabled')
            self.center_gauge_btn.configure(state='disabled')
            
            self.status_var.set("Gauge overlay hidden")
    
    def _change_orientation(self):
        """Change gauge orientation and update display."""
        if self.current_gauge_overlay is not None:
            self._show_gauge()  # Refresh with new orientation
    
    def _update_color_scheme(self, event=None):
        """Update gauge color scheme."""
        if self.current_gauge_overlay is not None:
            self._show_gauge()  # Refresh with new color scheme
    
    def _update_dpi(self):
        """Update DPI from preferences."""
        try:
            from utils.user_preferences import get_preferences_manager
            prefs_manager = get_preferences_manager()
            dpi = prefs_manager.get_default_dpi()
            self.dpi_var.set(str(dpi))
            self.gauge_system = FinalPerforationGauge(dpi=dpi)
            
            if self.current_gauge_overlay is not None:
                self._show_gauge()  # Refresh with new DPI
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update DPI from preferences: {str(e)}")
    
    def _center_gauge(self):
        """Center the gauge overlay on the image."""
        if self.current_gauge_overlay is not None and hasattr(self, 'base_image'):
            self._show_gauge()  # This centers the gauge by default
    
    def _fit_to_window(self):
        """Fit the image to the current window size."""
        if not hasattr(self, 'base_image'):
            return
        
        try:
            # Force canvas to update its size
            self.image_canvas.update_idletasks()
            
            # Get current canvas size
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()
            
            # Ensure we have reasonable canvas dimensions
            if canvas_width < 100:
                canvas_width = 600
            if canvas_height < 100:
                canvas_height = 500
            
            img_width, img_height = self.base_image.size
            
            # Calculate new scale factor to fit the current window
            scale_x = (canvas_width - 20) / img_width  # Leave some margin
            scale_y = (canvas_height - 20) / img_height
            
            # Use the smaller scale to fit entirely within canvas
            new_scale_factor = min(scale_x, scale_y)
            
            # Don't make images too small or too large
            new_scale_factor = max(0.1, min(new_scale_factor, 5.0))
            
            self.scale_factor = new_scale_factor
            
            # Update display based on current state
            if self.current_gauge_overlay is not None:
                # If gauge is active, regenerate it at the new scale
                self._show_gauge()
            else:
                # No gauge active, just scale the base image
                display_size = (int(img_width * self.scale_factor), int(img_height * self.scale_factor))
                self.display_image = self.base_image.resize(display_size, Image.LANCZOS)
                self._update_canvas_display()
            
            self._update_canvas_display()
            
            self.status_var.set(f"Fitted to window - scale: {self.scale_factor:.2f}x")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fit image to window: {str(e)}")
    
    def _toggle_auto_fit(self):
        """Toggle auto-fit on window resize."""
        self._auto_fit_enabled = self.auto_fit_var.get()
        if self._auto_fit_enabled and hasattr(self, 'base_image'):
            # If just enabled, fit to current window size
            self._fit_to_window()
    
    def _on_entry_change(self, *args):
        """Handle changes to direct entry fields."""
        # Parse horizontal entry
        h_text = self.h_entry_var.get().strip()
        if h_text:
            try:
                # Handle fractional notation
                if '¼' in h_text:
                    h_text = h_text.replace('¼', '.25')
                elif '½' in h_text:
                    h_text = h_text.replace('½', '.5')
                elif '¾' in h_text:
                    h_text = h_text.replace('¾', '.75')
                self.horizontal_measurement = float(h_text)
            except ValueError:
                self.horizontal_measurement = None
        else:
            self.horizontal_measurement = None
        
        # Parse vertical entry
        v_text = self.v_entry_var.get().strip()
        if v_text:
            try:
                # Handle fractional notation
                if '¼' in v_text:
                    v_text = v_text.replace('¼', '.25')
                elif '½' in v_text:
                    v_text = v_text.replace('½', '.5')
                elif '¾' in v_text:
                    v_text = v_text.replace('¾', '.75')
                self.vertical_measurement = float(v_text)
            except ValueError:
                self.vertical_measurement = None
        else:
            self.vertical_measurement = None
        
        # Update results display and enable save if we have any measurement
        self._update_results_display()
        if self.horizontal_measurement is not None or self.vertical_measurement is not None:
            self.save_data_btn.configure(state='normal')
        else:
            self.save_data_btn.configure(state='disabled')
    
    def _on_canvas_click(self, event):
        """Handle canvas click for gauge dragging."""
        if self.current_gauge_overlay is not None:
            self.is_dragging = True
            self.drag_start = (event.x, event.y)
    
    def _on_canvas_drag(self, event):
        """Handle gauge dragging."""
        if self.is_dragging and self.current_gauge_overlay is not None:
            if hasattr(self, 'base_image'):
                # Calculate new position (account for scaling)
                dx = (event.x - self.drag_start[0]) / self.scale_factor
                dy = (event.y - self.drag_start[1]) / self.scale_factor
                
                new_x = int(self.overlay_position[0] + dx)
                new_y = int(self.overlay_position[1] + dy)
                
                # Keep overlay within image bounds
                img_width, img_height = self.base_image.size
                overlay_width, overlay_height = self.current_gauge_overlay.size
                
                new_x = max(-overlay_width//2, min(img_width - overlay_width//2, new_x))
                new_y = max(-overlay_height//2, min(img_height - overlay_height//2, new_y))
                
                self.overlay_position = (new_x, new_y)
                
                # Update display
                self._update_overlay_position()
                self.drag_start = (event.x, event.y)
    
    def _on_canvas_release(self, event):
        """Handle end of gauge dragging."""
        self.is_dragging = False
        self.drag_start = None
        if self.current_gauge_overlay is not None:
            self.status_var.set("Gauge positioned - record measurements")
    
    def _update_overlay_position(self):
        """Update the display with the overlay at the current position."""
        if not hasattr(self, 'base_image') or self.current_gauge_overlay is None:
            return
        
        try:
            # Use same display-scaled approach as _show_gauge
            img_width, img_height = self.base_image.size
            display_width = int(img_width * self.scale_factor)
            display_height = int(img_height * self.scale_factor)
            
            # Create display-sized composite
            composite = Image.new('RGBA', (display_width, display_height))
            
            # Scale base image to display size
            scaled_base = self.base_image.resize((display_width, display_height), Image.LANCZOS)
            composite.paste(scaled_base.convert('RGBA'), (0, 0))
            
            # Paste overlay at current position (already in display coordinates)
            composite.paste(self.current_gauge_overlay, self.overlay_position, self.current_gauge_overlay)
            
            # Use composite directly (no additional scaling)
            self.display_image = composite
            
            self._update_canvas_display()
            
        except Exception as e:
            print(f"Failed to update overlay position: {e}")
    
    def _record_horizontal_measurement(self):
        """Record horizontal perforation measurement."""
        if self.current_gauge_overlay is None:
            messagebox.showwarning("No Gauge", "Please show the gauge overlay first")
            return
        
        # Prompt user to visually read the gauge
        result = self._prompt_gauge_reading("Horizontal")
        if result:
            self.horizontal_measurement = result
            self.h_entry_var.set(str(result))  # Update entry field
            self._update_results_display()
            self.status_var.set("Horizontal measurement recorded")
    
    def _record_vertical_measurement(self):
        """Record vertical perforation measurement."""
        if self.current_gauge_overlay is None:
            messagebox.showwarning("No Gauge", "Please show the gauge overlay first")
            return
        
        result = self._prompt_gauge_reading("Vertical")
        if result:
            self.vertical_measurement = result
            self.v_entry_var.set(str(result))  # Update entry field
            self._update_results_display()
            self.status_var.set("Vertical measurement recorded")
    
    def _prompt_gauge_reading(self, orientation):
        """Prompt user to enter gauge reading."""
        dialog = tk.Toplevel(self.dialog)
        dialog.title(f"Record {orientation} Gauge Reading")
        dialog.geometry("350x200")
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (dialog.winfo_screenwidth()//2 - 175, 
                                   dialog.winfo_screenheight()//2 - 100))
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"Enter {orientation.lower()} gauge reading:", 
                 font=("TkDefaultFont", 10, "bold")).pack(pady=5)
        ttk.Label(frame, text="(e.g., 11.5, 12, 13¼, etc.)", 
                 foreground="gray").pack()
        
        entry_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=entry_var, font=("TkDefaultFont", 12))
        entry.pack(pady=10, fill=tk.X)
        entry.focus_set()
        
        result = [None]
        
        def on_ok():
            try:
                value = entry_var.get().strip()
                if value:
                    # Convert fractional notation to decimal
                    if '¼' in value:
                        value = value.replace('¼', '.25')
                    elif '½' in value:
                        value = value.replace('½', '.5')
                    elif '¾' in value:
                        value = value.replace('¾', '.75')
                    
                    result[0] = float(value)
                    dialog.destroy()
                else:
                    messagebox.showwarning("Invalid Input", "Please enter a gauge value")
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number")
        
        def on_cancel():
            result[0] = None
            dialog.destroy()
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        entry.bind('<Return>', lambda e: on_ok())
        
        # Wait for dialog to close
        dialog.wait_window()
        return result[0]
    
    def _update_results_display(self):
        """Update the results text display."""
        self.results_text.delete(1.0, tk.END)
        
        self.results_text.insert(tk.END, "📏 GAUGE MEASUREMENTS\n", "header")
        self.results_text.insert(tk.END, "=" * 25 + "\n\n")
        
        if self.horizontal_measurement is not None:
            self.results_text.insert(tk.END, f"Horizontal: {self.horizontal_measurement}\n", "measurement")
        else:
            self.results_text.insert(tk.END, "Horizontal: Not measured\n", "missing")
        
        if self.vertical_measurement is not None:
            self.results_text.insert(tk.END, f"Vertical: {self.vertical_measurement}\n", "measurement")
        else:
            self.results_text.insert(tk.END, "Vertical: Not measured\n", "missing")
        
        # Determine compound vs uniform
        if self.horizontal_measurement is not None and self.vertical_measurement is not None:
            self.results_text.insert(tk.END, "\n📊 ANALYSIS\n", "header")
            self.results_text.insert(tk.END, "-" * 15 + "\n")
            
            if abs(self.horizontal_measurement - self.vertical_measurement) < 0.1:
                self.results_text.insert(tk.END, "Type: Uniform perforation\n")
                catalog_format = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
            else:
                self.results_text.insert(tk.END, "Type: Compound perforation\n")
                h_str = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
                v_str = f"{self.vertical_measurement:.1f}".rstrip('0').rstrip('.')
                catalog_format = f"{h_str} x {v_str}"
            
            self.results_text.insert(tk.END, f"Catalog Format: {catalog_format}\n", "catalog")
        
        # Configure text tags
        self.results_text.tag_configure("header", font=("TkDefaultFont", 10, "bold"))
        self.results_text.tag_configure("measurement", font=("TkDefaultFont", 10, "bold"), foreground="blue")
        self.results_text.tag_configure("missing", foreground="red")
        self.results_text.tag_configure("catalog", font=("TkDefaultFont", 10, "bold"), foreground="green")
    
    def _load_image(self):
        """Load a new image."""
        filename = filedialog.askopenfilename(
            title="Load Stamp Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            try:
                # Load image with PIL and convert to numpy array
                pil_image = Image.open(filename)
                # Convert to RGB if needed
                if pil_image.mode not in ['RGB', 'RGBA']:
                    pil_image = pil_image.convert('RGB')
                
                # Convert PIL to numpy array (RGB format)
                image_array = np.array(pil_image)
                
                # Convert RGB to BGR for compatibility with OpenCV-expecting code
                if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                    image = image_array[:, :, ::-1]  # RGB->BGR
                else:
                    image = image_array
                
                self.image_array = image
                self.image_filename = filename
                self._display_image(image)
                
                # Reset measurements
                self.horizontal_measurement = None
                self.vertical_measurement = None
                self.h_entry_var.set('')
                self.v_entry_var.set('')
                self.notes_text.delete('1.0', tk.END)
                self._update_results_display()
                self.save_data_btn.configure(state='disabled')
                
                # Hide any existing gauge
                if self.current_gauge_overlay is not None:
                    self._hide_gauge()
                
                self.status_var.set(f"Loaded: {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def _save_measurements(self):
        """Save measurements to unified data logger."""
        if self.horizontal_measurement is None and self.vertical_measurement is None:
            messagebox.showwarning("No Data", "No measurements to save")
            return
        
        if not self.image_filename:
            messagebox.showwarning("No Image File", "Please load an image file first to enable data logging")
            return
        
        try:
            # Use unified data logger
            from utils.unified_data_logger import UnifiedDataLogger
            
            logger = UnifiedDataLogger(self.image_filename)
            
            # Prepare perforation data for logging
            perf_data = self._prepare_perforation_data()
            
            # Log to unified data file
            data_file_path = logger.log_perforation_analysis(perf_data)
            
            if data_file_path:
                # Check for crop-related files and auto-merge
                merge_info = self._auto_merge_crop_files(data_file_path)
                
                success_msg = f"Gauge measurements saved to:\n\n{data_file_path.name}"
                if merge_info:
                    success_msg += f"\n\n{merge_info}"
                
                messagebox.showinfo("Success", success_msg)
                self.status_var.set("Measurements logged to unified data file")
            else:
                raise Exception("Data logger returned no file path")
                
        except ImportError:
            # Fallback to manual file creation if unified logger not available
            messagebox.showwarning(
                "Data Logger Unavailable", 
                "Unified data logger not found. Using manual file save..."
            )
            self._save_measurements_manual()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save measurements to data logger: {str(e)}")
            # Offer manual save as fallback
            if messagebox.askyesno("Fallback", "Would you like to save to a separate file instead?"):
                self._save_measurements_manual()
    
    def _prepare_perforation_data(self):
        """Prepare perforation data for unified data logger."""
        # Determine perforation type and catalog format
        if self.horizontal_measurement is not None and self.vertical_measurement is not None:
            if abs(self.horizontal_measurement - self.vertical_measurement) < 0.1:
                perforation_type = "Uniform"
                catalog_format = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
                gauge_measurement = self.horizontal_measurement
            else:
                perforation_type = "Compound"
                h_str = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
                v_str = f"{self.vertical_measurement:.1f}".rstrip('0').rstrip('.')
                catalog_format = f"{h_str} x {v_str}"
                gauge_measurement = f"H:{self.horizontal_measurement}, V:{self.vertical_measurement}"
        elif self.horizontal_measurement is not None:
            perforation_type = "Horizontal only"
            catalog_format = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
            gauge_measurement = self.horizontal_measurement
        elif self.vertical_measurement is not None:
            perforation_type = "Vertical only" 
            catalog_format = f"{self.vertical_measurement:.1f}".rstrip('0').rstrip('.')
            gauge_measurement = self.vertical_measurement
        else:
            perforation_type = "No measurements"
            catalog_format = "Not measured"
            gauge_measurement = "Not measured"
        
        # Get user notes from text field
        user_notes = self.notes_text.get("1.0", tk.END).strip()
        base_notes = f"Measured using traditional gauge overlay at {self.dpi_var.get()} DPI"
        combined_notes = f"{base_notes}. {user_notes}" if user_notes else base_notes
        
        # Create comprehensive data dictionary
        perf_data = {
            'perf_type': perforation_type,
            'gauge': gauge_measurement,
            'catalog_format': catalog_format,
            'horizontal_gauge': self.horizontal_measurement if self.horizontal_measurement is not None else "Not measured",
            'vertical_gauge': self.vertical_measurement if self.vertical_measurement is not None else "Not measured",
            'dpi_used': self.dpi_var.get(),
            'color_scheme': 'traditional white/black',
            'measurement_method': 'Visual gauge reading with traditional overlay',
            'measurement_tool': 'StampZ Gauge Perforation System',
            'regularity': 'Visual assessment with gauge overlay',
            'notes': combined_notes
        }
        
        return perf_data
    
    def _save_measurements_manual(self):
        """Fallback manual file save (original method)."""
        # Generate default filename
        if self.image_filename:
            base_name = os.path.splitext(os.path.basename(self.image_filename))[0]
            default_name = f"{base_name}_gauge_measurements.txt"
        else:
            default_name = "gauge_measurements.txt"
        
        # Ask user where to save
        filename = filedialog.asksaveasfilename(
            title="Save Gauge Measurements",
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Create measurement data in compatible format
                self._save_to_manual_file(filename)
                messagebox.showinfo("Success", f"Measurements saved to:\n{filename}")
                self.status_var.set("Measurements saved to separate file")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save measurements: {str(e)}")
    
    def _auto_merge_crop_files(self, current_data_file):
        """Auto-merge data from original and cropped image files.
        
        The cropped version (-crp) is always the master file.
        Data from the original (uncropped) file is merged into the -crp file,
        and the original file is then deleted.
        
        Args:
            current_data_file: Path to the current data file
            
        Returns:
            String describing merge action, or None if no merge occurred
        """
        try:
            from pathlib import Path
            import os
            
            current_path = Path(current_data_file)
            current_stem = current_path.stem  # e.g., "stamp-crp_StampZ_Data"
            
            # Remove _StampZ_Data suffix to get image name
            if current_stem.endswith('_StampZ_Data'):
                image_name = current_stem[:-len('_StampZ_Data')]
            else:
                return None
            
            # Check if this is a cropped file (ends with -crp)
            if image_name.endswith('-crp'):
                # This is cropped - look for original and merge it in
                original_image_name = image_name[:-len('-crp')]
                original_data_file = current_path.parent / f"{original_image_name}_StampZ_Data.txt"
                
                if original_data_file.exists():
                    # Merge: append original data to cropped file with a note
                    with open(original_data_file, 'r', encoding='utf-8') as orig:
                        original_content = orig.read()
                    
                    with open(current_path, 'a', encoding='utf-8') as current:
                        current.write("\n" + "=" * 50 + "\n")
                        current.write("DATA MERGED FROM ORIGINAL (UNCROPPED) IMAGE\n")
                        current.write(f"Merged from: {original_data_file.name}\n")
                        current.write(f"Merge timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        current.write("=" * 50 + "\n")
                        current.write(original_content)
                    
                    # Delete the original file after successful merge
                    os.remove(original_data_file)
                    
                    return f"✓ Merged & consolidated data:\n- From: {original_data_file.name} (deleted)\n- Into: {current_path.name}"
            
            else:
                # This is original - check if cropped version exists
                cropped_image_name = f"{image_name}-crp"
                cropped_data_file = current_path.parent / f"{cropped_image_name}_StampZ_Data.txt"
                
                if cropped_data_file.exists():
                    # Merge: append current data to cropped file (master)
                    with open(current_path, 'r', encoding='utf-8') as curr:
                        current_content = curr.read()
                    
                    with open(cropped_data_file, 'a', encoding='utf-8') as cropped:
                        cropped.write("\n" + "=" * 50 + "\n")
                        cropped.write("DATA MERGED FROM ORIGINAL (UNCROPPED) IMAGE\n")
                        cropped.write(f"Merged from: {current_path.name}\n")
                        cropped.write(f"Merge timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        cropped.write("=" * 50 + "\n")
                        cropped.write(current_content)
                    
                    # Delete the original file after successful merge
                    os.remove(current_path)
                    
                    return f"✓ Merged & consolidated data:\n- From: {current_path.name} (deleted)\n- Into: {cropped_data_file.name} (master)"
            
            return None
            
        except Exception as e:
            print(f"Warning: Auto-merge failed: {e}")
            return None
    
    def _save_to_manual_file(self, filename):
        """Save measurements to manual file (fallback method)."""
        # Create measurement summary
        lines = []
        lines.append("# StampZ Gauge-Based Perforation Measurements")
        lines.append(f"# Generated by StampZ Gauge System")
        lines.append(f"# Image: {os.path.basename(self.image_filename) if self.image_filename else 'Unknown'}")
        lines.append("")
        
        lines.append("PERFORATION MEASUREMENTS")
        lines.append("=" * 40)
        
        if self.horizontal_measurement is not None:
            lines.append(f"Horizontal Gauge: {self.horizontal_measurement}")
        
        if self.vertical_measurement is not None:
            lines.append(f"Vertical Gauge: {self.vertical_measurement}")
        
        if self.horizontal_measurement is not None and self.vertical_measurement is not None:
            if abs(self.horizontal_measurement - self.vertical_measurement) < 0.1:
                perforation_type = "Uniform"
                catalog_format = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
            else:
                perforation_type = "Compound"
                h_str = f"{self.horizontal_measurement:.1f}".rstrip('0').rstrip('.')
                v_str = f"{self.vertical_measurement:.1f}".rstrip('0').rstrip('.')
                catalog_format = f"{h_str} x {v_str}"
            
            lines.append("")
            lines.append(f"Perforation Type: {perforation_type}")
            lines.append(f"Catalog Format: {catalog_format}")
        
        lines.append("")
        lines.append("MEASUREMENT DETAILS")
        lines.append("-" * 20)
        lines.append(f"DPI Used: {self.dpi_var.get()}")
        lines.append(f"Color Scheme: traditional white/black")
        lines.append("Measurement Method: Visual gauge reading")
        
        # Add user notes if provided
        user_notes = self.notes_text.get("1.0", tk.END).strip()
        if user_notes:
            lines.append("")
            lines.append("NOTES")
            lines.append("-" * 20)
            lines.append(user_notes)
        
        # Write to file
        with open(filename, 'w') as f:
            f.write("\n".join(lines))
    
    def _show_help(self):
        """Show help dialog."""
        help_text = """
GAUGE PERFORATION MEASUREMENT SYSTEM

This tool provides a traditional perforation gauge overlay system for precise stamp perforation measurement.

WORKFLOW:
1. Load a stamp image
2. Set the correct DPI for your scan
3. Show the gauge overlay
4. Choose horizontal or vertical orientation
5. Drag the gauge to align with stamp perforations
6. Record the gauge reading where perforations align
7. Switch orientation and repeat for other direction
8. Save measurements to log files

GAUGE FEATURES:
• Traditional white lines and dots (like physical gauges)
• Proper fractional gauge markings (8, 8¼, 8½, 8¾, etc.)
• Multiple color schemes for different stamp types
• DPI scaling for accurate measurements
• Draggable positioning for precise alignment

TIPS:
• Use higher DPI scans (800-1200) for best accuracy
• Align the gauge reference line with stamp edge
• Record readings where perforation holes best align with dots
• For compound perforations, measure both orientations

This system integrates with StampZ data logging for consistent record keeping.
"""
        
        messagebox.showinfo("Gauge Measurement Help", help_text)
    
    def _close_dialog(self):
        """Close the dialog."""
        self.dialog.destroy()


def show_gauge_perforation_dialog(parent, image_array=None, image_filename=""):
    """Show the gauge perforation measurement dialog."""
    return GaugePerforationDialog(parent, image_array, image_filename)


if __name__ == "__main__":
    # Test the dialog
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    dialog = GaugePerforationDialog(root)
    root.mainloop()