#!/usr/bin/env python3
"""
Color Comparison Manager for StampZ
Provides interface for comparing sample colors with library colors.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Tuple, Dict, Any
import os
from PIL import Image, ImageTk

# Add project root to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.color_library import ColorLibrary, LibraryColor
from .color_display import ColorDisplay

class ColorComparisonManager(tk.Frame):
    """Manages color comparison interface and functionality."""
    
    # Minimum dimensions and proportions
    MIN_WIDTH = 1200        # Minimum window width
    MIN_HEIGHT = 600        # Minimum window height
    IDEAL_WIDTH = 2000      # Ideal window width for scaling calculations
    
    # Proportions (as percentages of window size)
    TOP_HEIGHT_RATIO = 0.35       # Reduced top section height
    BOTTOM_HEIGHT_RATIO = 0.65    # Increased bottom section height
    SWATCH_WIDTH_RATIO = 0.225    # 450/2000
    HEADER_HEIGHT_RATIO = 0.0625   # 50/800
    
    # Fixed aspect ratios
    SWATCH_ASPECT_RATIO = 450/60    # Width to height ratio for normal swatches (adjusted to 60px height)
    AVG_SWATCH_ASPECT_RATIO = 500/600  # Width to height ratio for average swatch
    
    # Minimum padding (will scale up with window size)
    MIN_PADDING = 10
    
    def __init__(self, parent: tk.Widget):
        """Initialize the color comparison manager.
        
        Args:
            parent: Parent widget (typically a notebook tab)
        """
        super().__init__(parent)
        
        # Initialize instance variables
        self.parent = parent
        self.library = None
        self.current_image = None
        self.sample_points = []
        self.delta_e_threshold = 15.0  # Increased threshold for testing
        
        # Initialize current sizes dictionary
        self.current_sizes = {
            'padding': self.MIN_PADDING  # Start with minimum padding
        }
        
        # Set minimum window size
        if isinstance(parent.winfo_toplevel(), tk.Tk):
            parent.winfo_toplevel().minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        
        # Configure for expansion
        self.configure(width=self.IDEAL_WIDTH)
        self.pack(fill=tk.BOTH, expand=True)
        
        # Create the layout
        self._create_layout()
        
        # Bind resize event
        self.bind('<Configure>', self._on_resize)
        
        # Initial size calculation
        self._update_sizes()
        
        # Load available libraries after UI is created
        self._load_available_libraries()
    
    def _create_layout(self):
        """Create the main layout with proportional dimensions - comparison only."""
        # Configure main grid with weights for proper scaling
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, minsize=50)     # Header - fixed height
        self.grid_rowconfigure(1, weight=1)       # Comparison section - takes remaining space
        
        # Create header frame (filename display)
        self._create_header()
        
        # Create comparison frame (library selection and matches only)
        self._create_comparison_section()
    
    def _create_header(self):
        """Create the header section with filename display."""
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky='ew', padx=self.current_sizes['padding'])
        
        self.filename_label = ttk.Label(header_frame, text="No file loaded", 
                                       font=("Arial", 12))
        self.filename_label.pack(side=tk.LEFT, padx=self.current_sizes['padding'])
    
    def _create_header(self):
        """Create the header section with filename display."""
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky='ew', padx=self.current_sizes['padding'])
        
        self.filename_label = ttk.Label(header_frame, text="No file loaded", 
                                       font=("Arial", 12))
        self.filename_label.pack(side=tk.LEFT, padx=self.current_sizes['padding'])
    
    def _create_top_section(self):
        """Create the top section with samples and average display."""
        top_frame = ttk.Frame(self)
        top_frame.grid(row=1, column=0, sticky='nsew')
        
        # Configure columns for 50/50 split
        top_frame.grid_columnconfigure(0, weight=1)  # Left side
        top_frame.grid_columnconfigure(1, weight=1)  # Right side
        
        # Left frame - Sample data and swatches
        self.samples_frame = ttk.LabelFrame(top_frame, text="Sample Data")
        self.samples_frame.grid(row=0, column=0, sticky='nsew', padx=self.current_sizes['padding'])
        self.samples_frame.grid_propagate(False)
        
        # Right frame - Average display
        self.average_frame = ttk.LabelFrame(top_frame, text="Average Color")
        self.average_frame.grid(row=0, column=1, sticky='nsew', padx=self.current_sizes['padding'])
        self.average_frame.grid_propagate(False)
    
    def _create_comparison_section(self):
        """Create the comparison section with library selection and matches."""
        comparison_frame = ttk.Frame(self)
        comparison_frame.grid(row=1, column=0, sticky='nsew')
        
        # Use grid for precise positioning in comparison frame
        comparison_frame.grid_columnconfigure(0, weight=1)  # Center horizontally
        comparison_frame.grid_columnconfigure(1, weight=1)  # Center horizontally
        comparison_frame.grid_columnconfigure(2, weight=1)  # Center horizontally
        comparison_frame.grid_rowconfigure(1, weight=1)  # Give weight to matches frame
        
        # Library selection bar - at top with minimal padding
        selection_frame = ttk.Frame(comparison_frame)
        selection_frame.grid(row=0, column=1, sticky='ew', padx=self.current_sizes['padding'], pady=5)
        
        # Library selection UI (multi-select)
        ttk.Label(selection_frame, text="Compare with:").pack(side=tk.LEFT)

        # Frame for listbox + scrollbar
        listbox_frame = ttk.Frame(selection_frame)
        listbox_frame.pack(side=tk.LEFT, padx=self.current_sizes['padding'])

        # Multi-select list of libraries (first item will be 'All Libraries')
        self.library_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, height=5, width=30, exportselection=False)
        self.library_listbox.pack(side=tk.LEFT)

        # Scrollbar for the listbox
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.library_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.library_listbox.config(yscrollcommand=scrollbar.set)

        # Bind selection event
        self.library_listbox.bind('<<ListboxSelect>>', self._on_library_selected)

        # Compare button
        self.compare_button = ttk.Button(selection_frame, text="Compare", command=self._compare_color)
        self.compare_button.pack(side=tk.LEFT, padx=self.current_sizes['padding'])
        
        # Delta E threshold display
        ttk.Label(selection_frame, 
                 text=f"ΔE ≤ {self.delta_e_threshold}",
                 font=("Arial", 12)).pack(side=tk.RIGHT)
        
        # Add export button in the comparison section
        export_frame = ttk.Frame(comparison_frame)
        export_frame.grid(row=0, column=0, sticky='ew', padx=self.current_sizes['padding'], pady=5)
        
        # Export to unified data logger button
        self.export_button = ttk.Button(
            export_frame,
            text="📊 Export to Unified Data Logger",
            command=self._open_export_dialog
        )
        self.export_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Matches frame
        self.matches_frame = ttk.LabelFrame(comparison_frame, text="Closest Matches")
        self.matches_frame.grid(row=1, column=0, columnspan=3, sticky='nsew', padx=self.current_sizes['padding'], pady=5)
        self.matches_frame.grid_propagate(False)  # Maintain fixed size
    
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
        
        # Calculate new sizes - increase base swatch width for comparison view
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
        if hasattr(self, 'matches_frame'):
            # Make matches frame use more of the available width
            self.matches_frame.configure(width=max(width - 2 * new_padding, 1200))
    
    def set_analyzed_data(self, image_path: str, sample_data: List[Dict]):
        """Set the analyzed image path and sample data for comparison.
        
        Args:
            image_path: Path to the image file
            sample_data: List of dictionaries containing sample information
                Each dict should have:
                - position: (x, y) tuple
                - type: 'circle' or 'rectangle'
                - size: (width, height) tuple
                - anchor: anchor position string
        """
        # Store the current file path for export functionality
        self.current_file_path = image_path
        try:
            print(f"DEBUG: Setting analyzed data with {len(sample_data)} samples for comparison")
            
            # Update filename display
            filename = os.path.basename(image_path)
            self.filename_label.config(text=filename)
            print(f"DEBUG: Updated filename display: {filename}")
            
            # Load the image (needed for color sampling)
            self.current_image = Image.open(image_path)
            
            # Create color analyzer
            from utils.color_analyzer import ColorAnalyzer
            analyzer = ColorAnalyzer()
            
            # Process each sample for comparison purposes only
            self.sample_points = []
            
            for i, sample in enumerate(sample_data, 1):
                try:
                    print(f"DEBUG: Processing sample {i} for comparison")
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
                        
                        # Store the sample point data for comparison
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
                        print(f"DEBUG: Added sample {i} with RGB: {avg_rgb} for comparison")
                except Exception as e:
                    print(f"DEBUG: Error processing sample {i}: {str(e)}")
                    continue
            
            print(f"DEBUG: Processed {len(self.sample_points)} sample points for comparison")
            
            # Initialize comparison UI (no display of samples/averages)
            self._initialize_comparison_ui()
            
        except Exception as e:
            print(f"DEBUG: Error in set_analyzed_data: {str(e)}")
            messagebox.showerror(
                "Comparison Error",
                f"Failed to prepare samples for comparison:\n\n{str(e)}"
            )
    
    def _initialize_comparison_ui(self):
        """Initialize the comparison UI after samples are loaded."""
        print(f"DEBUG: Initializing comparison UI with {len(self.sample_points)} samples")
        
        # Clear any existing matches display
        for widget in self.matches_frame.winfo_children():
            widget.destroy()
        
        # Show initial message in matches frame
        initial_label = ttk.Label(
            self.matches_frame, 
            text=f"Ready to compare {len(self.sample_points)} samples. Select libraries and click Compare.",
            font=("Arial", 12)
        )
        initial_label.pack(pady=20)
    
    
    def _on_sample_toggle(self):
        """Handle sample toggle events (no-op in comparison mode)."""
        # Samples are not displayed in comparison mode, so this is a no-op
        pass
    
    def _load_available_libraries(self):
        """Load available color libraries and populate dropdown."""
        try:
            # Use the same logic as main.py to find libraries
            library_files = set()  # Use set to avoid duplicates
            
            # Get directories to check
            library_dirs = self._get_library_directories()
            
            for library_dir in library_dirs:
                print(f"DEBUG: Looking for libraries in: {library_dir}")
                
                if not os.path.exists(library_dir):
                    print(f"DEBUG: Library directory does not exist: {library_dir}")
                    continue
                
                # Get list of all files in directory for debugging
                all_files = os.listdir(library_dir)
                print(f"DEBUG: All files in library directory: {all_files}")
                
                # Get list of library files
                for f in all_files:
                    if f.endswith("_library.db") and not f.lower().startswith("all_libraries"):
                        library_name = f[:-11]  # Remove '_library.db' suffix
                        library_files.add(library_name)
                        print(f"DEBUG: Found library: {library_name} in {library_dir}")
            
            # Convert to sorted list
            library_list = sorted(list(library_files))
            print(f"DEBUG: Found {len(library_list)} total libraries: {library_list}")
            
            # Store available libraries and populate listbox (first item is 'All Libraries')
            self.available_libraries = library_list
            
            # Clear and insert items
            if hasattr(self, 'library_listbox'):
                self.library_listbox.delete(0, tk.END)
                self.library_listbox.insert(tk.END, 'All Libraries')
                for name in library_list:
                    self.library_listbox.insert(tk.END, name)
                print(f"DEBUG: Populated library listbox with: ['All Libraries'] + {library_list}")
            
            # Set default selection from preferences
            try:
                from utils.user_preferences import get_preferences_manager
                prefs_manager = get_preferences_manager()
                default_library = prefs_manager.get_default_color_library()
                
                if default_library in library_list and hasattr(self, 'library_listbox'):
                    # Select the default library (offset by 1 due to 'All Libraries' at index 0)
                    index = library_list.index(default_library) + 1
                    self.library_listbox.selection_clear(0, tk.END)
                    self.library_listbox.selection_set(index)
                    self._on_library_selected()
                    print(f"DEBUG: Set default library to: {default_library}")
                elif library_list and hasattr(self, 'library_listbox'):
                    # Default to selecting All Libraries when multiple exist
                    self.library_listbox.selection_clear(0, tk.END)
                    if len(library_list) > 1:
                        self.library_listbox.selection_set(0)  # All Libraries
                    else:
                        self.library_listbox.selection_set(1)  # First/only library
                    self._on_library_selected()
                    print(f"DEBUG: Default selection applied")
                else:
                    print("DEBUG: No libraries available")
            except Exception as e:
                print(f"DEBUG: Error setting default library: {e}")
                # Fallback behavior
                if library_list and hasattr(self, 'library_listbox'):
                    self.library_listbox.selection_clear(0, tk.END)
                    self.library_listbox.selection_set(1)
                    self._on_library_selected()
            
        except Exception as e:
            print(f"Error loading libraries: {str(e)}")
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Library Error",
                f"Failed to load color libraries:\n\n{str(e)}"
            )
    
    def _get_library_directories(self):
        """Get list of directories to check for color libraries.
        
        Returns:
            List of directory paths to search for libraries
        """
        directories = []
        
        # Use the unified path utility for consistency
        from utils.path_utils import get_color_libraries_dir
        
        directories = []
        
        # Primary location using unified path utility
        directories.append(get_color_libraries_dir())
        
        # If running from PyInstaller bundle, also check bundled libraries
        if hasattr(sys, '_MEIPASS'):
            bundled_dir = os.path.join(sys._MEIPASS, "data", "color_libraries")
            directories.append(bundled_dir)
        
        return directories
    
    def _on_library_selected(self, event=None):
        """Handle library selection change (supports multi-select)."""
        try:
            # Get selected names from listbox
            if not hasattr(self, 'library_listbox'):
                return
            selected_indices = self.library_listbox.curselection()
            if not selected_indices:
                return

            # If 'All Libraries' (index 0) is selected, or nothing else selected, use all available
            use_all = 0 in selected_indices
            if use_all:
                selected_names = list(getattr(self, 'available_libraries', []))
            else:
                # Map indices to names (offset by 1 due to 'All Libraries' at index 0)
                selected_names = [self.library_listbox.get(i) for i in selected_indices]

            print(f"Loading libraries: {selected_names if selected_names else 'None'}")

            if selected_names:
                # Primary library for conversions (first selection)
                self.library = ColorLibrary(selected_names[0])
                # All selected libraries for comparison (if more than one)
                self.all_libraries = [ColorLibrary(n) for n in selected_names]
            else:
                self.library = None
                self.all_libraries = []

        except Exception as e:
            print(f"Error selecting library: {str(e)}")
            messagebox.showerror(
                "Library Error",
                f"Failed to load selected library/libraries:\n\n{str(e)}"
            )
    
    def _compare_color(self):
        """Compare sample colors to the selected library."""
        print(f"DEBUG: _compare_color called")
        print(f"DEBUG: self.library = {self.library}")
        print(f"DEBUG: self.sample_points count = {len(self.sample_points) if hasattr(self, 'sample_points') and self.sample_points else 0}")
        
        if not self.library:
            print("DEBUG: No library selected")
            messagebox.showerror("Error", "Please select a library first")
            return
        
        # Get enabled samples
        if not hasattr(self, 'sample_points') or not self.sample_points:
            print("DEBUG: No sample_points available")
            messagebox.showinfo("No Data", "No samples available for comparison. Please go to Results tab first to load sample data.")
            return
            
        enabled_samples = [s for s in self.sample_points if s['enabled'].get()]
        print(f"DEBUG: enabled_samples count = {len(enabled_samples)}")
        
        if not enabled_samples:
            print("DEBUG: No enabled samples")
            messagebox.showinfo("No Data", "No samples available for comparison.")
            return
        
        # Calculate average RGB for comparison
        total_r = sum(s['rgb'][0] for s in enabled_samples)
        total_g = sum(s['rgb'][1] for s in enabled_samples)
        total_b = sum(s['rgb'][2] for s in enabled_samples)
        count = len(enabled_samples)
        
        avg_rgb = (total_r/count, total_g/count, total_b/count)
        avg_lab = self.library.rgb_to_lab(avg_rgb)
        
        # Clear previous matches
        for widget in self.matches_frame.winfo_children():
            widget.destroy()
        
        try:
            # Compare with selected libraries
            if hasattr(self, 'all_libraries') and self.all_libraries and len(self.all_libraries) > 1:
                # Multiple libraries selected
                all_matches = []
                for lib in self.all_libraries:
                    lib_matches = lib.find_closest_matches(
                        sample_lab=avg_lab,
                        max_delta_e=self.delta_e_threshold,
                        max_results=6,
                        include_library_name=True
                    )
                    for match in lib_matches:
                        match.library_name = lib.library_name
                    all_matches.extend(lib_matches)
                
                # Sort by Delta E
                all_matches.sort(key=lambda x: x.delta_e_2000)
                matches = all_matches[:10]  # Top 10 matches
            else:
                # Single library comparison
                result = self.library.compare_sample_to_library(
                    sample_lab=avg_lab,
                    threshold=self.delta_e_threshold
                )
                matches = result.get('matches', []) if result else []
                # Set library name on each match for consistent display
                for match in matches:
                    match.library_name = self.library.library_name
            
            # Display matches
            if matches:
                self._display_matches(matches, avg_rgb, avg_lab)
            else:
                no_matches_label = ttk.Label(
                    self.matches_frame,
                    text=f"No matches found within ΔE ≤ {self.delta_e_threshold}",
                    font=("Arial", 12)
                )
                no_matches_label.pack(pady=20)
        
        except Exception as e:
            print(f"Error comparing colors: {str(e)}")
            messagebox.showerror(
                "Comparison Error",
                f"Failed to compare colors:\n\n{str(e)}"
            )
    
    def _display_matches(self, matches, sample_rgb, sample_lab):
        """Display color matches in the matches frame with sample swatch."""
        # Clear existing content
        for widget in self.matches_frame.winfo_children():
            widget.destroy()
        
        # Create main layout frame
        main_layout = ttk.Frame(self.matches_frame)
        main_layout.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns: matches on left (75%), sample swatch on right (25%)
        main_layout.grid_columnconfigure(0, weight=3)  # Matches column
        main_layout.grid_columnconfigure(1, weight=1)  # Sample swatch column
        main_layout.grid_rowconfigure(0, weight=1)
        
        # Left side: Scrollable matches
        from .scroll_manager import ScrollManager
        matches_scroll_frame = ttk.Frame(main_layout)
        matches_scroll_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        
        scroll_manager = ScrollManager(matches_scroll_frame)
        matches_content = scroll_manager.content_frame
        
        # Header with sample information in matches area
        header_frame = ttk.Frame(matches_content)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        sample_label = ttk.Label(
            header_frame,
            text=f"Comparing: RGB({int(sample_rgb[0])}, {int(sample_rgb[1])}, {int(sample_rgb[2])}) | "
                 f"L*a*b*({sample_lab[0]:.1f}, {sample_lab[1]:.1f}, {sample_lab[2]:.1f})",
            font=("Arial", 12, "bold")
        )
        sample_label.pack()
        
        # Right side: Sample color swatch
        sample_frame = ttk.LabelFrame(main_layout, text="Sample Color")
        sample_frame.grid(row=0, column=1, sticky='nsew', padx=(0, 0))
        
        # Create sample swatch - much larger to fill available space, aligned left
        sample_canvas = tk.Canvas(
            sample_frame,
            width=450,
            height=600,  # Much larger for better visualization
            highlightthickness=1,
            highlightbackground='gray'
        )
        sample_canvas.pack(pady=10, padx=(0, 10), anchor='w')
        
        # Draw sample color
        sample_canvas.create_rectangle(
            0, 0, 450, 600,
            fill=f"#{int(sample_rgb[0]):02x}{int(sample_rgb[1]):02x}{int(sample_rgb[2]):02x}",
            outline=''
        )
        
        # Add sample color info below swatch
        sample_info_frame = ttk.Frame(sample_frame)
        sample_info_frame.pack(fill=tk.X, padx=(0, 10), pady=(0, 10), anchor='w')
        
        sample_info_text = (
            f"RGB: ({int(sample_rgb[0])}, {int(sample_rgb[1])}, {int(sample_rgb[2])})\n"
            f"L*a*b*: ({sample_lab[0]:.1f}, {sample_lab[1]:.1f}, {sample_lab[2]:.1f})"
        )
        
        sample_info_label = ttk.Label(
            sample_info_frame,
            text=sample_info_text,
            font=("Arial", 12),
            justify=tk.CENTER
        )
        sample_info_label.pack()
        
        # Display matches in left column
        for i, match in enumerate(matches, 1):
            self._create_match_display(matches_content, match, i, sample_rgb)
    
    def _create_match_display(self, parent, match, index, sample_rgb=None):
        """Create display for a single color match."""
        match_frame = ttk.Frame(parent)
        match_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Match information on the left
        info_frame = ttk.Frame(match_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Color name and library
        color_rgb = match.library_color.rgb
        name_text = match.library_color.name
        if hasattr(match, 'library_name'):
            name_text += f" ({match.library_name})"
        
        name_label = ttk.Label(
            info_frame,
            text=f"{index}. {name_text}",
            font=("Arial", 12, "bold")
        )
        name_label.pack(anchor='w')
        
        # Color values and Delta E
        # Display very small ΔE values (< 0.1) as 0.0 to account for floating-point rounding
        display_delta_e = 0.0 if match.delta_e_2000 < 0.1 else match.delta_e_2000
        values_text = (
            f"RGB: ({int(color_rgb[0])}, {int(color_rgb[1])}, {int(color_rgb[2])}) | "
            f"L*a*b*: ({match.library_color.lab[0]:.1f}, {match.library_color.lab[1]:.1f}, {match.library_color.lab[2]:.1f}) | "
            f"ΔE: {display_delta_e:.2f}"
        )
        
        values_label = ttk.Label(
            info_frame,
            text=values_text,
            font=("Arial", 12)
        )
        values_label.pack(anchor='w')
        
        # Color swatch on the right - closer to sample swatch
        swatch_canvas = tk.Canvas(
            match_frame,
            width=550,
            height=100,
            highlightthickness=1,
            highlightbackground='gray'
        )
        swatch_canvas.pack(side=tk.RIGHT, padx=(10, 0))
        
        swatch_canvas.create_rectangle(
            0, 0, 600, 100,
            fill=f"#{int(color_rgb[0]):02x}{int(color_rgb[1]):02x}{int(color_rgb[2]):02x}",
            outline=''
        )
    
    def _open_export_dialog(self):
        """Open export dialog (placeholder - functionality moved to Results tab)."""
        messagebox.showinfo(
            "Export",
            "Export functionality has been moved to the Results tab.\n\n"
            "Please use the 'Send to Compare Tab' button in Results to send data here for comparison."
        )
