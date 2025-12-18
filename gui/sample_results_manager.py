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
        
        # Add buttons frame - vertically stacked for better space management
        buttons_frame = ttk.Frame(values_frame)
        buttons_frame.pack(anchor='se', pady=(0, 5))

        # Add color to library button
        add_button = ttk.Button(buttons_frame, text="Add color to library", 
                              command=lambda: self._add_color_to_library(avg_rgb, avg_lab))
        add_button.pack(fill=tk.X, pady=2)

        # Add Save to DB button (renamed from "Save Results")
        save_db_button = ttk.Button(buttons_frame, text="Save to DB",
                              command=lambda: self._save_to_database(avg_rgb, avg_lab, enabled_samples))
        save_db_button.pack(fill=tk.X, pady=2)
        
        # Add Save to File button (new - saves to unified data logger)
        save_file_button = ttk.Button(buttons_frame, text="Save to File",
                              command=lambda: self._save_to_text_file(avg_rgb, avg_lab, enabled_samples))
        save_file_button.pack(fill=tk.X, pady=2)
    
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
        
        # Center the dialog relative to parent window (multi-monitor aware)
        dialog.update_idletasks()
        dialog_width = 450
        dialog_height = 420
        
        # Get parent window position
        try:
            parent_window = self.winfo_toplevel()
            parent_x = parent_window.winfo_x()
            parent_y = parent_window.winfo_y()
            parent_width = parent_window.winfo_width()
            parent_height = parent_window.winfo_height()
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        except:
            # Fallback to simple centering if parent position unavailable
            dialog.geometry(f"{dialog_width}x{dialog_height}")
        
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
        
        # Preselect default library from preferences if available
        try:
            from utils.user_preferences import get_preferences_manager
            prefs = get_preferences_manager()
            default_lib = prefs.get_default_color_library()
            if default_lib in library_list:
                lib_var.set(default_lib)
            else:
                lib_var.set(library_list[0] if library_list else '')
        except Exception:
            lib_var.set(library_list[0] if library_list else '')
        
        lib_combo = ttk.Combobox(lib_frame, textvariable=lib_var, values=library_list, width=27, state="readonly")
        lib_combo.pack(side=tk.LEFT, padx=5)
        
        # Notes entry (multi-line)
        notes_frame = ttk.Frame(dialog, padding="10")
        notes_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(notes_frame, text="Notes (optional):").pack(anchor='w')
        
        notes_text = tk.Text(notes_frame, height=4, width=50, wrap=tk.WORD)
        notes_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add scrollbar for notes
        notes_scrollbar = ttk.Scrollbar(notes_frame, orient=tk.VERTICAL, command=notes_text.yview)
        notes_text.configure(yscrollcommand=notes_scrollbar.set)
        notes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
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
            notes = notes_text.get("1.0", tk.END).strip()
            
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
                
                # Add the new color with notes
                success = color_lib.add_color(name=name, rgb=rgb_values, lab=lab_values, notes=notes if notes else None)
                
                if success:
                    messagebox.showinfo("Success", f"Color '{name}' added to library '{library}'")
                    dialog.destroy()
                    
                    # Notify Compare tab to refresh its library if it exists
                    self._refresh_compare_tab_library(library)
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
    
    def _refresh_compare_tab_library(self, library_name: str):
        """Refresh the library in the Compare tab after adding a color.
        
        Args:
            library_name: Name of the library that was updated
        """
        print(f"DEBUG: _refresh_compare_tab_library called for library '{library_name}'")
        
        # Try direct reference first if available
        if hasattr(self, '_comparison_manager_ref') and self._comparison_manager_ref:
            print(f"DEBUG: Using direct reference to comparison manager")
            try:
                comp_manager = self._comparison_manager_ref
                
                # Reload the library list
                if hasattr(comp_manager, '_load_available_libraries'):
                    comp_manager._load_available_libraries()
                    print(f"DEBUG: Reloaded library list in Compare tab")
                
                # Reload the specific library if it's currently selected
                if hasattr(comp_manager, 'library') and comp_manager.library:
                    if comp_manager.library.library_name == library_name:
                        from utils.color_library import ColorLibrary
                        comp_manager.library = ColorLibrary(library_name)
                        # Also update all_libraries if it exists
                        if hasattr(comp_manager, 'all_libraries') and comp_manager.all_libraries:
                            comp_manager.all_libraries = [ColorLibrary(lib.library_name) if lib.library_name == library_name else lib for lib in comp_manager.all_libraries]
                        print(f"DEBUG: Reloaded library '{library_name}' in Compare tab")
                
                # Also refresh the Library tab if we can find the ColorLibraryManager
                self._refresh_library_tab(library_name)
                
                return
            except Exception as e:
                print(f"DEBUG: Direct reference failed: {e}")
        
        try:
            # Find the ColorLibraryManager window through the widget hierarchy
            current_widget = self.parent
            library_manager = None
            
            print(f"DEBUG: Starting widget tree walk from {type(current_widget).__name__}")
            
            # Walk up the widget tree to find the ColorLibraryManager
            for level in range(10):  # Increased search depth
                if current_widget is None:
                    print(f"DEBUG: Reached None at level {level}")
                    break
                
                print(f"DEBUG: Level {level}: {type(current_widget).__name__}, has comparison_manager: {hasattr(current_widget, 'comparison_manager')}")
                
                # Check if this widget has a comparison_manager attribute
                if hasattr(current_widget, 'comparison_manager'):
                    library_manager = current_widget
                    print(f"DEBUG: Found comparison_manager at level {level}!")
                    break
                
                # Try to go up one level
                if hasattr(current_widget, 'winfo_parent'):
                    try:
                        parent_name = current_widget.winfo_parent()
                        if parent_name:
                            current_widget = current_widget.nametowidget(parent_name)
                        else:
                            print(f"DEBUG: No parent at level {level}")
                            break
                    except Exception as e:
                        print(f"DEBUG: Error getting parent at level {level}: {e}")
                        break
                else:
                    print(f"DEBUG: No winfo_parent at level {level}")
                    break
            
            if library_manager and hasattr(library_manager, 'comparison_manager'):
                comp_manager = library_manager.comparison_manager
                print(f"DEBUG: Found comparison manager, refreshing after adding to '{library_name}'")
                
                # Reload the library list
                if hasattr(comp_manager, '_load_available_libraries'):
                    comp_manager._load_available_libraries()
                
                # Reload the specific library if it's currently selected
                if hasattr(comp_manager, 'library') and comp_manager.library:
                    if comp_manager.library.library_name == library_name:
                        from utils.color_library import ColorLibrary
                        comp_manager.library = ColorLibrary(library_name)
                        # Also update all_libraries if it exists
                        if hasattr(comp_manager, 'all_libraries') and comp_manager.all_libraries:
                            comp_manager.all_libraries = [ColorLibrary(lib.library_name) if lib.library_name == library_name else lib for lib in comp_manager.all_libraries]
                        print(f"DEBUG: Reloaded library '{library_name}' in Compare tab")
            else:
                print(f"DEBUG: Could not find ColorLibraryManager with comparison_manager")
                
        except Exception as e:
            import traceback
            print(f"DEBUG: Could not refresh Compare tab: {e}")
            traceback.print_exc()
    
    def _refresh_library_tab(self, library_name: str):
        """Refresh the Library tab display after adding a color.
        
        Args:
            library_name: Name of the library that was updated
        """
        try:
            # Use the class variable to access the current ColorLibraryManager instance
            from gui.color_library_manager import ColorLibraryManager
            
            if ColorLibraryManager._current_instance:
                manager = ColorLibraryManager._current_instance
                print(f"DEBUG: Found ColorLibraryManager instance via class variable")
                
                if manager.library and manager.library.library_name == library_name:
                    print(f"DEBUG: Refreshing Library tab display for '{library_name}'")
                    # Reload the library to get new colors
                    from utils.color_library import ColorLibrary
                    manager.library = ColorLibrary(library_name)
                    # Refresh the display
                    if hasattr(manager, '_update_colors_display'):
                        manager._update_colors_display()
                        print(f"DEBUG: Library tab display refreshed")
                    else:
                        print(f"DEBUG: Manager missing _update_colors_display method")
                else:
                    print(f"DEBUG: Library names don't match: manager has '{manager.library.library_name if manager.library else 'None'}', looking for '{library_name}'")
            else:
                print(f"DEBUG: No ColorLibraryManager instance available")
                
        except Exception as e:
            import traceback
            print(f"DEBUG: Could not refresh Library tab: {e}")
            traceback.print_exc()
    
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
    
    def _get_existing_databases(self):
        """Get list of existing non-library databases."""
        try:
            from utils.path_utils import get_color_analysis_dir
            analysis_dir = get_color_analysis_dir()
            
            if not os.path.exists(analysis_dir):
                return []
            
            # Get all .db files in the analysis directory
            db_files = [f for f in os.listdir(analysis_dir) if f.endswith('.db')]
            
            # Filter out library databases and system databases
            non_library_dbs = []
            for db_file in db_files:
                db_name = os.path.splitext(db_file)[0]
                # Skip library databases, average databases, and system databases
                if not (db_name.endswith('_library') or 
                       db_name.endswith('_averages') or
                       db_name.endswith('_AVG') or
                       db_name.startswith('system_') or
                       db_name in ['coordinates', 'coordinate_sets']):
                    non_library_dbs.append(db_name)
            
            return sorted(non_library_dbs)
            
        except Exception as e:
            print(f"Error getting existing databases: {e}")
            return []
    
    def _save_to_database(self, avg_rgb, avg_lab, enabled_samples):
        """Save results to database - checks for quick save preference first."""
        # Check if quick save is enabled
        try:
            from utils.user_preferences import get_preferences_manager
            prefs = get_preferences_manager()
            quick_save_enabled = prefs.get_enable_quick_save()
        except:
            quick_save_enabled = False
        
        if quick_save_enabled:
            # Quick save: use preferences directly without showing dialog
            self._perform_quick_save(avg_rgb, avg_lab, enabled_samples)
        else:
            # Normal flow: show the dialog
            self._show_save_results_dialog(avg_rgb, avg_lab, enabled_samples)
    
    def _perform_quick_save(self, avg_rgb, avg_lab, enabled_samples):
        """Perform quick save using preference settings without showing dialog."""
        try:
            from utils.user_preferences import get_preferences_manager
            from utils.color_analyzer import ColorAnalyzer
            from utils.color_analysis_db import ColorAnalysisDB
            from utils.dismissible_message import showsuccess_dismissible
            import os
            
            prefs = get_preferences_manager()
            analyzer = ColorAnalyzer()
            
            # Get preferences
            default_db_name = prefs.get_default_database_name()
            save_individual = prefs.get_save_individual_default()
            save_average = prefs.get_save_average_default()
            use_averages_suffix = prefs.get_use_averages_suffix()
            
            # Use preference default, or base on filename if available
            if hasattr(self, 'current_file_path'):
                filename = os.path.basename(self.current_file_path)
                file_base = os.path.splitext(filename)[0]
                if default_db_name in ["ColorAnalysis", "Results_Analysis"]:
                    final_db_name = f"Results_{file_base}"
                else:
                    final_db_name = default_db_name
            else:
                final_db_name = default_db_name
            
            # Convert sample data
            sample_measurements = []
            for i, sample in enumerate(enabled_samples, 1):
                sample_rgb = sample['rgb']
                sample_lab = self.library.rgb_to_lab(sample_rgb) if hasattr(self, 'library') and self.library else analyzer.rgb_to_lab(sample_rgb)
                
                measurement = {
                    'id': f"sample_{i}",
                    'l_value': sample_lab[0],
                    'a_value': sample_lab[1],
                    'b_value': sample_lab[2],
                    'rgb_r': sample_rgb[0],
                    'rgb_g': sample_rgb[1],
                    'rgb_b': sample_rgb[2],
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
                image_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
            
            success_individual = True
            success_average = True
            saved_files = []
            
            # Save individual samples if enabled
            if save_individual:
                individual_db = ColorAnalysisDB(final_db_name)
                set_id = individual_db.create_measurement_set(image_name, f"Individual samples from {image_name}")
                
                if set_id:
                    success_individual = True
                    for measurement in sample_measurements:
                        sample_size_str = f"{measurement['sample_width']}x{measurement['sample_height']}"
                        saved = individual_db.save_color_measurement(
                            set_id=set_id,
                            coordinate_point=int(measurement['id'].replace('sample_', '')),
                            x_pos=measurement['x_position'],
                            y_pos=measurement['y_position'],
                            l_value=measurement['l_value'],
                            a_value=measurement['a_value'],
                            b_value=measurement['b_value'],
                            rgb_r=measurement['rgb_r'],
                            rgb_g=measurement['rgb_g'],
                            rgb_b=measurement['rgb_b'],
                            sample_type=measurement['sample_type'],
                            sample_size=sample_size_str,
                            sample_anchor=measurement['anchor'],
                            notes=f"Sample from Results Manager"
                        )
                        if not saved:
                            success_individual = False
                            break
                    
                    if success_individual:
                        saved_files.append(f"{final_db_name}.db")
            
            # Save averaged result if enabled
            if save_average:
                if use_averages_suffix:
                    avg_db_name = f"{final_db_name}_AVERAGES"
                else:
                    avg_db_name = final_db_name
                
                success_average = analyzer.save_averaged_measurement_from_samples(
                    sample_measurements=sample_measurements,
                    sample_set_name=avg_db_name,
                    image_name=image_name,
                    notes=f"Average from {len(enabled_samples)} samples via Results Manager (Quick Save)"
                )
                
                if success_average:
                    saved_files.append(f"{avg_db_name}_averages.db")
            
            # Check success
            if (not save_individual or success_individual) and (not save_average or success_average):
                # Save database name to preferences
                prefs.set('last_used_database', final_db_name)
                
                # Build success message
                success_msg = "Results saved successfully!\n\n"
                if save_individual and success_individual:
                    success_msg += f"✓ {len(enabled_samples)} individual samples saved\n"
                if save_average and success_average:
                    success_msg += f"✓ 1 averaged result saved\n"
                success_msg += "\nSaved to:\n"
                for file in saved_files:
                    success_msg += f"• {file}\n"
                
                # Use dismissible success message
                showsuccess_dismissible(
                    title="Quick Save Complete",
                    message=success_msg,
                    message_id="quick_save_success"
                )
            else:
                # Show error
                from tkinter import messagebox
                error_msg = "Some save operations failed:\n\n"
                if save_individual and not success_individual:
                    error_msg += "✗ Individual samples failed to save\n"
                if save_average and not success_average:
                    error_msg += "✗ Average calculation failed to save\n"
                messagebox.showerror("Quick Save Error", error_msg)
                
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Quick save failed: {str(e)}")
    
    def _show_save_results_dialog(self, avg_rgb, avg_lab, enabled_samples):
        """Show dialog to save results to database."""
        try:
            # Create dialog
            dialog = tk.Toplevel(self)
            dialog.title("Save Results")
            dialog.transient(self)
            dialog.grab_set()
            
            # Center dialog relative to parent window (multi-monitor aware)
            dialog.update_idletasks()
            dialog_width = 500
            dialog_height = 550
            
            # Get parent window position
            try:
                parent_window = self.winfo_toplevel()
                parent_x = parent_window.winfo_x()
                parent_y = parent_window.winfo_y()
                parent_width = parent_window.winfo_width()
                parent_height = parent_window.winfo_height()
                x = parent_x + (parent_width - dialog_width) // 2
                y = parent_y + (parent_height - dialog_height) // 2
                dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            except:
                # Fallback to simple centering if parent position unavailable
                dialog.geometry(f"{dialog_width}x{dialog_height}")
            
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
                f"Individual Samples: {len(enabled_samples)}\n"
                f"Data to save: Both individual samples and calculated average"
            )
            ttk.Label(content_frame, text=summary_text, justify=tk.LEFT).pack(pady=(0, 15))
            
            # Database selection frame
            db_frame = ttk.LabelFrame(content_frame, text="Database Selection", padding="10")
            db_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Get existing non-library databases
            existing_databases = self._get_existing_databases()
            
            # Get default database name from preferences to determine initial choice
            try:
                from utils.user_preferences import get_preferences_manager
                prefs = get_preferences_manager()
                default_db_name = prefs.get_default_database_name()
            except:
                default_db_name = "ColorAnalysis"
            
            # Determine which radio button should be selected by default
            # If the preference database exists, select it; otherwise create new
            if existing_databases and default_db_name in existing_databases:
                initial_choice = "existing"
            else:
                initial_choice = "new"
            
            # Radio button for database selection
            db_choice = tk.StringVar(value=initial_choice)
            
            # Existing database option
            existing_frame = ttk.Frame(db_frame)
            existing_frame.pack(fill=tk.X, pady=(0, 10))
            
            existing_radio = ttk.Radiobutton(existing_frame, text="Use existing database:", 
                                           variable=db_choice, value="existing")
            existing_radio.pack(anchor='w')
            
            db_var = tk.StringVar()
            if existing_databases:
                # Use preference database name if it exists, otherwise last used
                if default_db_name in existing_databases:
                    db_var.set(default_db_name)
                else:
                    # Try to load last used database from preferences
                    try:
                        last_db = prefs.get('last_used_database', '')
                        if last_db and last_db in existing_databases:
                            db_var.set(last_db)
                        else:
                            db_var.set(existing_databases[0])
                    except:
                        db_var.set(existing_databases[0])
            
            existing_combo = ttk.Combobox(existing_frame, textvariable=db_var, 
                                        values=existing_databases, state="readonly", width=50)
            existing_combo.pack(fill=tk.X, padx=(20, 0), pady=(5, 0))
            
            if not existing_databases:
                existing_radio.config(state='disabled')
                existing_combo.config(state='disabled')
                ttk.Label(existing_frame, text="(No existing databases found)", 
                         foreground='gray').pack(anchor='w', padx=(20, 0))
            
            # New database option
            new_frame = ttk.Frame(db_frame)
            new_frame.pack(fill=tk.X, pady=(10, 0))
            
            new_radio = ttk.Radiobutton(new_frame, text="Create new database:", 
                                       variable=db_choice, value="new")
            new_radio.pack(anchor='w')
            
            new_db_var = tk.StringVar()
            # default_db_name already retrieved above
            
            # Use preference default, or base on filename if available
            if hasattr(self, 'current_file_path'):
                import os
                filename = os.path.basename(self.current_file_path)
                file_base = os.path.splitext(filename)[0]
                # If default is generic, use filename; otherwise use preference
                if default_db_name in ["ColorAnalysis", "Results_Analysis"]:
                    new_db_var.set(f"Results_{file_base}")
                else:
                    new_db_var.set(default_db_name)
            else:
                new_db_var.set(default_db_name)
                
            new_db_entry = ttk.Entry(new_frame, textvariable=new_db_var, width=50)
            new_db_entry.pack(fill=tk.X, padx=(20, 0), pady=(5, 0))
            
            # Save options frame
            options_frame = ttk.LabelFrame(content_frame, text="Save Options", padding="10")
            options_frame.pack(fill=tk.X, pady=(15, 0))
            
            # Load default values from preferences
            try:
                from utils.user_preferences import get_preferences_manager
                prefs = get_preferences_manager()
                save_individual_default = prefs.get_save_individual_default()
                save_average_default = prefs.get_save_average_default()
            except:
                # Fallback to defaults if preferences unavailable
                save_individual_default = True
                save_average_default = True
            
            # Checkboxes for what to save (using preferences as defaults)
            save_individual = tk.BooleanVar(value=save_individual_default)
            save_average = tk.BooleanVar(value=save_average_default)
            
            save_individual_cb = ttk.Checkbutton(options_frame, text="Save individual sample measurements", 
                                               variable=save_individual)
            save_individual_cb.pack(anchor='w', pady=(0, 5))
            
            save_average_cb = ttk.Checkbutton(options_frame, text="Save calculated average", 
                                            variable=save_average)
            save_average_cb.pack(anchor='w', pady=(0, 10))
            
            # Info about database naming
            info_text = (
                "• Individual samples: {database_name}.db\n"
                "• Average result: {database_name}_AVG.db"
            )
            ttk.Label(options_frame, text=info_text, font=("Arial", 9), 
                     foreground="gray", justify=tk.LEFT).pack(anchor='w')
            
            def save_results():
                # Check that at least one save option is selected
                if not save_individual.get() and not save_average.get():
                    messagebox.showerror("Error", "Please select at least one save option")
                    return
                
                # Determine which database to use
                final_db_name = ""
                if db_choice.get() == "existing" and existing_databases:
                    final_db_name = db_var.get().strip()
                else:
                    final_db_name = new_db_var.get().strip()
                
                if not final_db_name:
                    messagebox.showerror("Error", "Please select or enter a database name")
                    return
                
                try:
                    # Save to database using ColorAnalyzer
                    from utils.color_analyzer import ColorAnalyzer
                    analyzer = ColorAnalyzer()
                    
                    # Convert sample data for saving
                    sample_measurements = []
                    for i, sample in enumerate(enabled_samples, 1):
                        # Calculate Lab values properly for each sample
                        sample_rgb = sample['rgb']
                        sample_lab = self.library.rgb_to_lab(sample_rgb) if hasattr(self, 'library') and self.library else analyzer.rgb_to_lab(sample_rgb)
                        
                        measurement = {
                            'id': f"sample_{i}",
                            'l_value': sample_lab[0],
                            'a_value': sample_lab[1], 
                            'b_value': sample_lab[2],
                            'rgb_r': sample_rgb[0],
                            'rgb_g': sample_rgb[1],
                            'rgb_b': sample_rgb[2],
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
                    
                    # Initialize success flags
                    success_individual = True
                    success_average = True
                    saved_files = []
                    
                    # Save individual samples if requested
                    if save_individual.get():
                        from utils.color_analysis_db import ColorAnalysisDB
                        individual_db = ColorAnalysisDB(final_db_name)
                        
                        # Create measurement set
                        set_id = individual_db.create_measurement_set(image_name, f"Individual samples from {image_name}")
                        success_individual = False
                        
                        if set_id:
                            # Save each individual measurement
                            success_individual = True
                            for measurement in sample_measurements:
                                # Format sample size as string
                                sample_size_str = f"{measurement['sample_width']}x{measurement['sample_height']}"
                                
                                saved = individual_db.save_color_measurement(
                                    set_id=set_id,
                                    coordinate_point=int(measurement['id'].replace('sample_', '')),
                                    x_pos=measurement['x_position'],
                                    y_pos=measurement['y_position'],
                                    l_value=measurement['l_value'],
                                    a_value=measurement['a_value'],
                                    b_value=measurement['b_value'],
                                    rgb_r=measurement['rgb_r'],
                                    rgb_g=measurement['rgb_g'],
                                    rgb_b=measurement['rgb_b'],
                                    sample_type=measurement['sample_type'],
                                    sample_size=sample_size_str,
                                    sample_anchor=measurement['anchor'],
                                    notes=f"Sample from Results Manager"
                                )
                                if not saved:
                                    success_individual = False
                                    break
                            
                            if success_individual:
                                saved_files.append(f"{final_db_name}.db")
                    
                    # Save averaged result if requested
                    if save_average.get():
                        # Get suffix preference
                        try:
                            from utils.user_preferences import get_preferences_manager
                            prefs = get_preferences_manager()
                            use_averages_suffix = prefs.get_use_averages_suffix()
                        except:
                            use_averages_suffix = True
                        
                        # Apply _AVERAGES suffix if preference is enabled
                        if use_averages_suffix:
                            avg_db_name = f"{final_db_name}_AVERAGES"
                        else:
                            avg_db_name = final_db_name
                        
                        success_average = analyzer.save_averaged_measurement_from_samples(
                            sample_measurements=sample_measurements,
                            sample_set_name=avg_db_name,
                            image_name=image_name,
                            notes=f"Average from {len(enabled_samples)} samples via Results Manager"
                        )
                        
                        if success_average:
                            saved_files.append(f"{avg_db_name}_averages.db")
                    
                    # Check if all requested operations succeeded
                    all_requested_succeeded = True
                    if save_individual.get() and not success_individual:
                        all_requested_succeeded = False
                    if save_average.get() and not success_average:
                        all_requested_succeeded = False
                    
                    if all_requested_succeeded and saved_files:
                        # Save database name to preferences for next time
                        try:
                            from utils.user_preferences import get_preferences_manager
                            prefs = get_preferences_manager()
                            prefs.set('last_used_database', final_db_name)
                        except Exception as e:
                            print(f"Warning: Could not save last_used_database preference: {e}")
                        
                        # Build success message
                        success_msg = "Results saved successfully!\n\n"
                        
                        if save_individual.get() and success_individual:
                            success_msg += f"✓ {len(enabled_samples)} individual samples saved\n"
                        if save_average.get() and success_average:
                            success_msg += f"✓ 1 averaged result saved\n"
                        
                        success_msg += "\nSaved to:\n"
                        for file in saved_files:
                            success_msg += f"• {file}\n"
                        
                        messagebox.showinfo("Success", success_msg)
                        dialog.destroy()
                    else:
                        # Build error message for failures
                        error_msg = "Some save operations failed:\n\n"
                        
                        if save_individual.get() and not success_individual:
                            error_msg += "✗ Individual samples failed to save\n"
                        if save_average.get() and not success_average:
                            error_msg += "✗ Average calculation failed to save\n"
                        
                        if saved_files:
                            error_msg += "\nPartially saved to:\n"
                            for file in saved_files:
                                error_msg += f"• {file}\n"
                        
                        messagebox.showerror("Save Error", error_msg)
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save results: {str(e)}")
            
            # Buttons frame
            button_frame = ttk.Frame(content_frame)
            button_frame.pack(fill=tk.X, pady=(15, 0))
            
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
            ttk.Button(button_frame, text="Save", command=save_results).pack(side=tk.RIGHT, padx=(0, 10))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open save dialog: {str(e)}")
    
    def _save_to_text_file(self, avg_rgb, avg_lab, enabled_samples):
        """Save analysis results to unified data logger text file.
        
        Args:
            avg_rgb: Average RGB tuple
            avg_lab: Average Lab tuple
            enabled_samples: List of enabled sample dictionaries
        """
        try:
            # Check if we have a current file path
            if not hasattr(self, 'current_file_path') or not self.current_file_path:
                messagebox.showerror(
                    "No Image File",
                    "Cannot save to text file without an associated image file.\n\n"
                    "Please load an image before saving analysis results."
                )
                return
            
            # Import unified data logger
            from utils.unified_data_logger import UnifiedDataLogger
            from utils.color_analyzer import ColorAnalyzer
            
            # Create logger instance for current image
            logger = UnifiedDataLogger(self.current_file_path)
            analyzer = ColorAnalyzer()
            
            # Prepare individual measurements data
            sample_measurements = []
            for i, sample in enumerate(enabled_samples, 1):
                sample_rgb = sample['rgb']
                sample_lab = self.library.rgb_to_lab(sample_rgb) if hasattr(self, 'library') and self.library else analyzer.rgb_to_lab(sample_rgb)
                
                measurement = {
                    'coordinate_point': i,
                    'x_position': sample['position'][0],
                    'y_position': sample['position'][1],
                    'l_value': sample_lab[0],
                    'a_value': sample_lab[1],
                    'b_value': sample_lab[2],
                    'rgb_r': sample_rgb[0],
                    'rgb_g': sample_rgb[1],
                    'rgb_b': sample_rgb[2],
                    'sample_type': sample['type'],
                    'sample_width': sample['size'][0],
                    'sample_height': sample['size'][1],
                    'anchor': sample['anchor']
                }
                sample_measurements.append(measurement)
            
            # Get image name for the logger
            import os
            image_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
            
            # Log individual measurements
            individual_result = logger.log_individual_color_measurements(
                measurements=sample_measurements,
                sample_set_name="Color_Analysis_Results",
                image_name=image_name
            )
            
            # Prepare averaged measurement data
            averaged_data = {
                'l_value': avg_lab[0],
                'a_value': avg_lab[1],
                'b_value': avg_lab[2],
                'rgb_r': avg_rgb[0],
                'rgb_g': avg_rgb[1],
                'rgb_b': avg_rgb[2],
                'notes': f"Averaged from {len(enabled_samples)} samples via Results Manager"
            }
            
            # Log averaged measurement
            averaged_result = logger.log_averaged_color_measurement(
                averaged_data=averaged_data,
                sample_set_name="Color_Analysis_Results",
                image_name=image_name,
                source_count=len(enabled_samples)
            )
            
            # Check for crop-related files and auto-merge
            data_file_path = logger.get_data_file_path()
            merge_info = self._auto_merge_crop_files(data_file_path)
            
            # Show success message
            if individual_result and averaged_result:
                success_msg = (
                    f"Color analysis results saved successfully!\n\n"
                    f"File: {data_file_path.name}\n"
                    f"Location: {data_file_path.parent}\n\n"
                    f"Saved:\n"
                    f"• {len(enabled_samples)} individual samples\n"
                    f"• 1 averaged result\n\n"
                )
                if merge_info:
                    success_msg += f"\n{merge_info}\n\n"
                success_msg += "Data has been appended to your unified analysis log."
                
                messagebox.showinfo("Saved to File", success_msg)
            else:
                messagebox.showerror(
                    "Save Error",
                    "Failed to save some or all data to text file."
                )
            
        except Exception as e:
            messagebox.showerror(
                "Save Error",
                f"Failed to save to text file:\n\n{str(e)}"
            )
    
    def _auto_merge_crop_files(self, current_data_file):
        """Auto-merge data from original and cropped image files.
        
        The cropped version (-crp) is always the master file.
        
        Args:
            current_data_file: Path to the current data file
            
        Returns:
            String describing merge action, or None if no merge occurred
        """
        try:
            from pathlib import Path
            import os
            from datetime import datetime
            
            current_path = Path(current_data_file)
            current_stem = current_path.stem
            
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
                    # Merge: append original data to cropped file
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
