"""
Sample Results Manager for StampZ

Provides interface for displaying analyzed sample colors and averages.
This is the upper frame functionality extracted from ColorComparisonManager.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Tuple, Dict, Any
import os
from PIL import Image

# Add project root to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.color_library import ColorLibrary


class SampleResultsManager(tk.Frame):
    """Manages sample results display interface and functionality."""
    
    # Minimum dimensions and proportions
    MIN_WIDTH = 1200        # Minimum window width
    MIN_HEIGHT = 400        # Minimum window height for results only
    IDEAL_WIDTH = 2000      # Ideal window width for scaling calculations
    
    # Proportions 
    SWATCH_WIDTH_RATIO = 0.225    # 450/2000
    HEADER_HEIGHT_RATIO = 0.125   # 50/400
    
    # Fixed aspect ratios
    SWATCH_ASPECT_RATIO = 450/60    # Width to height ratio for normal swatches
    AVG_SWATCH_ASPECT_RATIO = 450/375  # Width to height ratio for average swatch
    
    # Minimum padding (will scale up with window size)
    MIN_PADDING = 10
    
    def __init__(self, parent: tk.Widget):
        """Initialize the sample results manager.
        
        Args:
            parent: Parent widget (typically a notebook tab)
        """
        super().__init__(parent)
        
        # Initialize instance variables
        self.parent = parent
        self.library = None
        self.current_image = None
        self.sample_points = []
        
        # Initialize current sizes dictionary
        self.current_sizes = {
            'padding': self.MIN_PADDING  # Start with minimum padding
        }
        
        # Configure for expansion
        self.configure(width=self.IDEAL_WIDTH)
        self.pack(fill=tk.BOTH, expand=True)
        
        # Create the layout
        self._create_layout()
        
        # Bind resize event
        self.bind('<Configure>', self._on_resize)
        
        # Initial size calculation
        self._update_sizes()
    
    def _create_layout(self):
        """Create the main layout with proportional dimensions."""
        # Configure main grid with weights for proper scaling
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, minsize=50)     # Header - fixed height
        self.grid_rowconfigure(1, weight=1)       # Results section - takes remaining space
        
        # Create header frame (filename display)
        self._create_header()
        
        # Create results frame (samples and average)
        self._create_results_section()
    
    def _create_header(self):
        """Create the header section with filename display."""
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky='ew', padx=self.current_sizes['padding'])
        
        self.filename_label = ttk.Label(header_frame, text="No file loaded", 
                                       font=("Arial", 12))
        self.filename_label.pack(side=tk.LEFT, padx=self.current_sizes['padding'])
    
    def _create_results_section(self):
        """Create the results section with samples and average display."""
        results_frame = ttk.Frame(self)
        results_frame.grid(row=1, column=0, sticky='nsew')
        
        # Configure columns for 50/50 split
        results_frame.grid_columnconfigure(0, weight=1)  # Left side
        results_frame.grid_columnconfigure(1, weight=1)  # Right side
        
        # Left frame - Sample data and swatches
        self.samples_frame = ttk.LabelFrame(results_frame, text="Sample Data")
        self.samples_frame.grid(row=0, column=0, sticky='nsew', padx=self.current_sizes['padding'])
        self.samples_frame.grid_propagate(False)
        
        # Right frame - Average display
        self.average_frame = ttk.LabelFrame(results_frame, text="Average Color")
        self.average_frame.grid(row=0, column=1, sticky='nsew', padx=self.current_sizes['padding'])
        self.average_frame.grid_propagate(False)
    
    def _on_resize(self, event=None):
        """Handle window resize events to maintain proportions."""
        if event and event.widget == self:
            self._update_sizes()
    
    def _update_sizes(self):
        """Update all component sizes based on current window dimensions."""
        # Get current window size
        width = self.winfo_width()
        height = self.winfo_height()
        
        # Calculate new dimensions maintaining proportions
        scale_factor = min(width / self.IDEAL_WIDTH, height / (self.MIN_HEIGHT * 1.5))
        
        # Calculate new sizes - increase base swatch width for results view
        base_swatch_width = max(500, int(self.IDEAL_WIDTH * self.SWATCH_WIDTH_RATIO * scale_factor))
        new_swatch_width = base_swatch_width
        new_swatch_height = int(new_swatch_width / self.SWATCH_ASPECT_RATIO)
        new_avg_swatch_height = int(new_swatch_width / self.AVG_SWATCH_ASPECT_RATIO)
        new_padding = int(self.MIN_PADDING * scale_factor)
        
        # Store current sizes for use in other methods
        self.current_sizes = {
            'swatch_width': new_swatch_width,
            'swatch_height': new_swatch_height,
            'avg_swatch_height': new_avg_swatch_height,
            'padding': new_padding
        }
        
        # Update frame sizes
        if hasattr(self, 'samples_frame'):
            self.samples_frame.configure(width=new_swatch_width + 2 * new_padding)
        if hasattr(self, 'average_frame'):
            self.average_frame.configure(width=new_swatch_width + 2 * new_padding)
    
    def set_analyzed_data(self, image_path: str, sample_data: List[Dict]):
        """Set the analyzed image path and sample data.
        
        Args:
            image_path: Path to the image file
            sample_data: List of dictionaries containing sample information
                Each dict should have:
                - position: (x, y) tuple
                - type: 'circle' or 'rectangle'
                - size: (width, height) tuple
                - anchor: anchor position string
        """
        # Store the current file path 
        self.current_file_path = image_path
        try:
            print(f"DEBUG: Setting analyzed data with {len(sample_data)} samples")
            
            # Update filename display
            filename = os.path.basename(image_path)
            self.filename_label.config(text=filename)
            print(f"DEBUG: Updated filename display: {filename}")
            
            # Load the image (needed for color sampling)
            self.current_image = Image.open(image_path)
            
            # Create color analyzer
            from utils.color_analyzer import ColorAnalyzer
            analyzer = ColorAnalyzer()
            
            # Process each sample
            self.sample_points = []
            
            for i, sample in enumerate(sample_data, 1):
                try:
                    print(f"DEBUG: Processing sample {i}")
                    # Create a temporary coordinate point for sampling
                    from utils.coordinate_db import SampleAreaType
                    
                    class TempCoord:
                        def __init__(self, x, y, sample_type, size, anchor):
                            self.x = x
                            self.y = y
                            self.sample_type = SampleAreaType.CIRCLE if sample_type == 'circle' else SampleAreaType.RECTANGLE
                            self.sample_size = size
                            self.anchor_position = anchor
                    
                    # Extract position and parameters
                    x, y = sample['position']
                    temp_coord = TempCoord(
                        x=x,
                        y=y,
                        sample_type=sample['type'],
                        size=sample['size'],
                        anchor=sample['anchor']
                    )
                    
                    # Sample the color
                    rgb_values = analyzer._sample_area_color(self.current_image, temp_coord)
                    if rgb_values:
                        avg_rgb = analyzer._calculate_average_color(rgb_values)
                        
                        # Store the sample point data
                        sample_point = {
                            'rgb': avg_rgb,
                            'position': (x, y),
                            'enabled': tk.BooleanVar(value=True),
                            'index': i,
                            'type': sample['type'],
                            'size': sample['size'],
                            'anchor': sample['anchor']
                        }
                        self.sample_points.append(sample_point)
                        print(f"DEBUG: Added sample {i} with RGB: {avg_rgb}, enabled: {sample_point['enabled'].get()}")
                except Exception as e:
                    print(f"DEBUG: Error processing sample {i}: {str(e)}")
                    continue
            
            print(f"DEBUG: Processed {len(self.sample_points)} sample points")
            
            # Update the display
            self._display_sample_points()
            self._update_average_display()
            
        except Exception as e:
            print(f"DEBUG: Error in set_analyzed_data: {str(e)}")
            messagebox.showerror(
                "Analysis Error",
                f"Failed to analyze sample points:\\n\\n{str(e)}"
            )
    
    def _display_sample_points(self):
        """Display sample points with their color values and swatches."""
        # Clear existing samples
        for widget in self.samples_frame.winfo_children():
            widget.destroy()
        
        # Calculate average color for ΔE comparisons
        enabled_samples = [s for s in self.sample_points if s['enabled'].get()]
        average_lab = None
        
        if enabled_samples and self.library:
            from utils.color_analyzer import ColorAnalyzer
            analyzer = ColorAnalyzer()
            
            lab_values = []
            rgb_values = []
            for sample in enabled_samples:
                rgb = sample['rgb']
                lab = self.library.rgb_to_lab(rgb) if self.library else analyzer.rgb_to_lab(rgb)
                lab_values.append(lab)
                rgb_values.append(rgb)
            
            if lab_values:
                # Calculate quality-controlled average for ΔE comparison
                averaging_result = analyzer._calculate_quality_controlled_average(lab_values, rgb_values)
                average_lab = averaging_result['avg_lab']
        
        # Display each sample point
        for sample in self.sample_points:
            frame = ttk.Frame(self.samples_frame)
            frame.pack(fill=tk.X, pady=5)
            
            # Sample toggle
            ttk.Checkbutton(frame, 
                          text=f"Sample {sample['index']}",
                          variable=sample['enabled'],
                          command=self._on_sample_toggle).pack(side=tk.LEFT)
            
            # Color values with ΔE from average
            rgb = sample['rgb']
            lab = self.library.rgb_to_lab(rgb) if self.library else None
            
            # Use conditional color display based on user preferences
            from utils.color_display_utils import get_conditional_color_values_text
            value_text = get_conditional_color_values_text(rgb, lab, compact=True)
            
            # Add ΔE from average if we have both values
            if lab and average_lab and sample['enabled'].get():
                from utils.color_analyzer import ColorAnalyzer
                analyzer = ColorAnalyzer()
                delta_e = analyzer.calculate_delta_e(lab, average_lab)
                value_text += f"\\nΔE from avg: {delta_e:.2f}"
            
            ttk.Label(frame, text=value_text, font=("Arial", 12)).pack(side=tk.LEFT, padx=20)
            
            # Color swatch using canvas
            canvas = tk.Canvas(
                frame,
                width=450,
                height=60,
                highlightthickness=1,
                highlightbackground='gray'
            )
            canvas.pack(side=tk.RIGHT, padx=5, pady=2)
            
            # Create rectangle for color display
            canvas.create_rectangle(
                0, 0, 450, 60,
                fill=f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}",
                outline=''
            )
    
    def _update_average_display(self):
        """Update the average color display."""
        # Clear existing display
        for widget in self.average_frame.winfo_children():
            widget.destroy()
        
        # Get enabled samples
        enabled_samples = [s for s in self.sample_points if s['enabled'].get()]
        
        if not enabled_samples:
            ttk.Label(self.average_frame, text="No samples enabled").pack(pady=20)
            return
        
        # Use ColorAnalyzer for quality-controlled averaging with ΔE outlier detection
        from utils.color_analyzer import ColorAnalyzer
        analyzer = ColorAnalyzer()
        
        # Convert samples to Lab and RGB lists for quality averaging
        lab_values = []
        rgb_values = []
        for sample in enabled_samples:
            rgb = sample['rgb']
            lab = self.library.rgb_to_lab(rgb) if self.library else analyzer.rgb_to_lab(rgb)
            lab_values.append(lab)
            rgb_values.append(rgb)
        
        # Calculate quality-controlled average with ΔE outlier detection
        averaging_result = analyzer._calculate_quality_controlled_average(lab_values, rgb_values)
        
        avg_rgb = averaging_result['avg_rgb']
        avg_lab = averaging_result['avg_lab']
        max_delta_e = averaging_result['max_delta_e']
        samples_used = averaging_result['samples_used']
        outliers_excluded = averaging_result['outliers_excluded']
        
        # Create display frame
        frame = ttk.Frame(self.average_frame)
        frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)  # Remove left padding
        
        # Average color swatch using canvas
        canvas = tk.Canvas(
            frame,
            width=450,
            height=360,
            highlightthickness=1,
            highlightbackground='gray'
        )
        canvas.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Create rectangle for color display
        canvas.create_rectangle(
            0, 0, 450, 360,
            fill=f"#{int(avg_rgb[0]):02x}{int(avg_rgb[1]):02x}{int(avg_rgb[2]):02x}",
            outline=''
        )
        
        # Color values based on user preferences
        from utils.color_display_utils import get_conditional_color_values_text
        value_text = get_conditional_color_values_text(avg_rgb, avg_lab, compact=True)
        
        # Create a frame for values and button
        values_frame = ttk.Frame(frame)
        values_frame.pack(side=tk.LEFT, padx=20, fill=tk.Y)
        
        # Add color values
        ttk.Label(values_frame, text=value_text, font=("Arial", 14)).pack(pady=10)
        
        # Add averaging information
        if outliers_excluded > 0:
            outlier_text = f"\nAveraging Quality Control:\n{samples_used}/{len(enabled_samples)} samples used\n{outliers_excluded} outlier(s) excluded\nMax ΔE from centroid: {max_delta_e:.2f}"
            ttk.Label(values_frame, text=outlier_text, font=("Arial", 10)).pack(pady=5)
        
        # Add some vertical space
        ttk.Frame(values_frame, height=15).pack()
        
        # Add buttons frame for the two buttons
        buttons_frame = ttk.Frame(values_frame)
        buttons_frame.pack(anchor='se', pady=(0, 5))

        # Add color to library button
        add_button = ttk.Button(buttons_frame, text="Add color to library", 
                              command=lambda: self._add_color_to_library(avg_rgb, avg_lab))
        add_button.pack(side=tk.LEFT, padx=(0, 5))

        # Add Save Results button
        save_button = ttk.Button(buttons_frame, text="Save Results",
                              command=lambda: self._show_save_results_dialog(avg_rgb, avg_lab, enabled_samples))
        save_button.pack(side=tk.LEFT)
    
    def _on_sample_toggle(self):
        """Handle sample toggle events."""
        self._update_average_display()
    
    def _add_color_to_library(self, rgb_values, lab_values):
        """Handle adding the current average color to a library."""
        if not rgb_values or not lab_values:
            messagebox.showerror("Error", "No color data available to add")
            return
            
        # Create a dialog for color name and library selection
        dialog = tk.Toplevel(self)
        dialog.title("Add Color to Library")
        dialog.transient(self)  # Make dialog modal
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("400x200")
        
        # Color name entry
        name_frame = ttk.Frame(dialog, padding="10")
        name_frame.pack(fill=tk.X)
        ttk.Label(name_frame, text="Color name:").pack(side=tk.LEFT)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(name_frame, textvariable=name_var, width=30)
        name_entry.pack(side=tk.LEFT, padx=5)
        
        # Library selection
        lib_frame = ttk.Frame(dialog, padding="10")
        lib_frame.pack(fill=tk.X)
        ttk.Label(lib_frame, text="Select library:").pack(side=tk.LEFT)
        
        # Load available libraries
        library_list = self._get_available_libraries()
        
        lib_var = tk.StringVar()
        lib_combo = ttk.Combobox(lib_frame, textvariable=lib_var, values=library_list, width=27)
        lib_combo.pack(side=tk.LEFT, padx=5)
        
        # Preview frame showing the color
        preview_frame = ttk.Frame(dialog, padding="10")
        preview_frame.pack(fill=tk.X)
        ttk.Label(preview_frame, text="Color preview:").pack(side=tk.LEFT)
        
        # Color preview swatch
        preview_canvas = tk.Canvas(preview_frame, width=100, height=30,
                                highlightthickness=1, highlightbackground='gray')
        preview_canvas.pack(side=tk.LEFT, padx=5)
        preview_canvas.create_rectangle(
            0, 0, 100, 30,
            fill=f"#{int(rgb_values[0]):02x}{int(rgb_values[1]):02x}{int(rgb_values[2]):02x}",
            outline=''
        )
        
        def save_color():
            name = name_var.get().strip()
            library = lib_var.get()
            
            if not name:
                messagebox.showerror("Error", "Please enter a color name")
                return
            if not library:
                messagebox.showerror("Error", "Please select a library")
                return
                
            try:
                # Load the selected library
                from utils.color_library import ColorLibrary
                color_lib = ColorLibrary(library)
                
                # Add the new color
                success = color_lib.add_color(name=name, rgb=rgb_values, lab=lab_values)
                
                if success:
                    messagebox.showinfo("Success", f"Color '{name}' added to library '{library}'")
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", f"Failed to add color '{name}' to library '{library}'")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add color: {str(e)}")
        
        # Buttons frame
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Save", command=save_color).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        
        # Focus the name entry
        name_entry.focus_set()
    
    def _get_available_libraries(self):
        """Get list of available color libraries."""
        try:
            import os
            from utils.path_utils import get_color_libraries_dir
            
            library_dir = get_color_libraries_dir()
            if not os.path.exists(library_dir):
                return ['basic_colors']
                
            library_files = [f for f in os.listdir(library_dir) if f.endswith("_library.db")]
            library_names = [f[:-11] for f in library_files]  # Remove '_library.db' suffix
            
            if not library_names:
                library_names = ['basic_colors']
                
            return sorted(library_names)
        except Exception as e:
            print(f"Error getting libraries: {e}")
            return ['basic_colors']
    
    def _show_save_results_dialog(self, avg_rgb, avg_lab, enabled_samples):
        """Show dialog to save results to database."""
        try:
            # Create dialog
            dialog = tk.Toplevel(self)
            dialog.title("Save Results")
            dialog.geometry("400x300")
            dialog.transient(self)
            dialog.grab_set()
            
            # Main content frame
            content_frame = ttk.Frame(dialog, padding="20")
            content_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            ttk.Label(content_frame, text="Save Analysis Results", 
                     font=("Arial", 14, "bold")).pack(pady=(0, 10))
            
            # Summary information
            summary_text = (
                f"Average Color: RGB({int(avg_rgb[0])}, {int(avg_rgb[1])}, {int(avg_rgb[2])})\n"
                f"L*a*b*: ({avg_lab[0]:.1f}, {avg_lab[1]:.1f}, {avg_lab[2]:.1f})\n"
                f"Based on {len(enabled_samples)} sample{'s' if len(enabled_samples) != 1 else ''}"
            )
            ttk.Label(content_frame, text=summary_text, justify=tk.LEFT).pack(pady=(0, 15))
            
            # Database name entry
            db_frame = ttk.Frame(content_frame)
            db_frame.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Label(db_frame, text="Database name:").pack(anchor='w')
            db_var = tk.StringVar()
            
            # Default database name based on current file
            if hasattr(self, 'current_file_path'):
                import os
                filename = os.path.basename(self.current_file_path)
                default_name = os.path.splitext(filename)[0]
                db_var.set(f"Results_{default_name}")
            else:
                db_var.set("Results_Analysis")
                
            db_entry = ttk.Entry(db_frame, textvariable=db_var, width=40)
            db_entry.pack(fill=tk.X, pady=(5, 0))
            
            def save_results():
                db_name = db_var.get().strip()
                if not db_name:
                    messagebox.showerror("Error", "Please enter a database name")
                    return
                
                try:
                    # Save to database using ColorAnalyzer
                    from utils.color_analyzer import ColorAnalyzer
                    analyzer = ColorAnalyzer()
                    
                    # Convert sample data for saving
                    sample_measurements = []
                    for i, sample in enumerate(enabled_samples, 1):
                        measurement = {
                            'id': f"sample_{i}",
                            'l_value': lab_values[0] if hasattr(self, 'library') and self.library else analyzer.rgb_to_lab(sample['rgb'])[0],
                            'a_value': lab_values[1] if hasattr(self, 'library') and self.library else analyzer.rgb_to_lab(sample['rgb'])[1], 
                            'b_value': lab_values[2] if hasattr(self, 'library') and self.library else analyzer.rgb_to_lab(sample['rgb'])[2],
                            'rgb_r': sample['rgb'][0],
                            'rgb_g': sample['rgb'][1],
                            'rgb_b': sample['rgb'][2],
                            'x_position': sample['position'][0],
                            'y_position': sample['position'][1],
                            'sample_type': sample['type'],
                            'sample_width': sample['size'][0],
                            'sample_height': sample['size'][1],
                            'anchor': sample['anchor']
                        }
                        sample_measurements.append(measurement)
                    
                    # Get image name
                    image_name = "analysis_result"
                    if hasattr(self, 'current_file_path'):
                        import os
                        image_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
                    
                    # Save averaged result
                    success = analyzer.save_averaged_measurement_from_samples(
                        sample_measurements=sample_measurements,
                        sample_set_name=db_name,
                        image_name=image_name,
                        notes=f"Results saved from analysis of {len(enabled_samples)} samples"
                    )
                    
                    if success:
                        messagebox.showinfo(
                            "Success",
                            f"Results saved to database '{db_name}' successfully!"
                        )
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "Failed to save results to database")
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save results: {str(e)}")
            
            # Buttons frame
            button_frame = ttk.Frame(content_frame)
            button_frame.pack(fill=tk.X, pady=(15, 0))
            
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
            ttk.Button(button_frame, text="Save", command=save_results).pack(side=tk.RIGHT, padx=(0, 10))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open save dialog: {str(e)}")
