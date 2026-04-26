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
        
        # Reset the canvas live model's role flags so they start in lockstep
        # with the freshly-built ``sample_points`` (which always start as
        # ink). The back-ref — if wired — was set up by the caller
        # before this method runs (see analysis_manager.compare_sample_to_library).
        live_model = getattr(self, '_live_model_ref', None)
        if live_model is not None:
            try:
                for sidx in list(live_model.samples.keys()):
                    live_model.set_paper(sidx, False)
            except Exception as e:
                print(f"DEBUG: could not reset live model is_paper: {e}")
        
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
                    rgb_values, rgb_stddev, lab_stddev = analyzer._sample_area_color(self.current_image, temp_coord)
                    if rgb_values:
                        avg_rgb = analyzer._calculate_average_color(rgb_values)
                        
                        # Store the sample point data
                        # is_paper marks this sample as a margin/paper reading;
                        # paper samples participate in their own group average
                        # and on save are routed to a separate '-p' measurement
                        # set inside the same DB (see _save_to_database).
                        sample_point = {
                            'rgb': avg_rgb,
                            'rgb_stddev': rgb_stddev,
                            'lab_stddev': lab_stddev,
                            'position': (x, y),
                            'enabled': tk.BooleanVar(value=True),
                            'is_paper': tk.BooleanVar(value=False),
                            'index': i,
                            'type': sample['type'],
                            'size': sample['size'],
                            'anchor': sample['anchor']
                        }
                        self.sample_points.append(sample_point)
                        print(f"DEBUG: Added sample {i} with RGB: {avg_rgb}, RGB StdDev: {rgb_stddev}, L*a*b* StdDev: {lab_stddev}, enabled: {sample_point['enabled'].get()}")
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
        """Display sample points with their color values and swatches.
        
        Each sample row carries two checkboxes:
          * the existing 'Sample N' (enable/disable in averaging)
          * 'P' (mark this sample as a paper-margin reading instead of ink)
        
        ΔE labels show distance from the *group* average (ink or paper)
        the sample belongs to, so paper samples don't get penalised for
        being far from the ink mean.
        """
        # Clear existing samples
        for widget in self.samples_frame.winfo_children():
            widget.destroy()
        
        from utils.color_analyzer import ColorAnalyzer
        from utils.color_display_utils import (
            get_conditional_color_values_text, get_conditional_stddev_text,
        )
        analyzer = ColorAnalyzer()
        
        def _group_avg_lab(group_samples):
            """Quality-controlled Lab mean for a group, or None if empty."""
            if not group_samples:
                return None
            lab_values = []
            rgb_values = []
            for s in group_samples:
                rgb = s['rgb']
                lab = (self.library.rgb_to_lab(rgb)
                       if self.library else analyzer.rgb_to_lab(rgb))
                lab_values.append(lab)
                rgb_values.append(rgb)
            if not lab_values:
                return None
            return analyzer._calculate_quality_controlled_average(
                lab_values, rgb_values,
            )['avg_lab']
        
        enabled_ink = [s for s in self.sample_points
                       if s['enabled'].get() and not s['is_paper'].get()]
        enabled_paper = [s for s in self.sample_points
                         if s['enabled'].get() and s['is_paper'].get()]
        ink_avg_lab = _group_avg_lab(enabled_ink)
        paper_avg_lab = _group_avg_lab(enabled_paper)
        
        # Display each sample point
        for sample in self.sample_points:
            frame = ttk.Frame(self.samples_frame)
            frame.pack(fill=tk.X, pady=5)
            
            # Sample toggle
            ttk.Checkbutton(frame,
                          text=f"Sample {sample['index']}",
                          variable=sample['enabled'],
                          command=self._on_sample_toggle).pack(side=tk.LEFT)
            
            # Paper toggle — marks this sample as paper-margin (vs ink).
            # Wrapped so we can enforce the "min 2 ink samples" rule:
            # turning P on is rejected if it would drop the ink-tagged
            # count below 2 (which would leave the ink section empty
            # and hide the Save / Compute coverage buttons).
            ttk.Checkbutton(frame,
                          text="P",
                          variable=sample['is_paper'],
                          command=lambda s=sample: self._on_paper_toggle(s)).pack(
                              side=tk.LEFT, padx=(2, 8))
            
            # Color values with ΔE from this sample's group average
            rgb = sample['rgb']
            rgb_stddev = sample.get('rgb_stddev', None)
            lab_stddev = sample.get('lab_stddev', None)
            lab = self.library.rgb_to_lab(rgb) if self.library else None
            
            value_text = get_conditional_color_values_text(rgb, lab, compact=True)
            
            # Add blank line for separation
            value_text += "\n"
            
            if lab and sample['enabled'].get():
                is_paper = sample['is_paper'].get()
                group_avg = paper_avg_lab if is_paper else ink_avg_lab
                if group_avg:
                    delta_e = analyzer.calculate_delta_e(lab, group_avg)
                    role_label = "paper" if is_paper else "ink"
                    value_text += f"\nΔE from {role_label} avg: {delta_e:.2f}"
                    # ΔL/ΔC/ΔH breakdown directly under the ΔE line.
                    # In low-chroma blues a single ΔE often disagrees
                    # with what the eye sees; the breakdown shows which
                    # axis the disagreement is on (lighter/darker,
                    # more/less saturated, hue rotated which way).
                    try:
                        from utils.lab_difference import (
                            lab_difference_components,
                            format_lab_components_compact,
                        )
                        components = lab_difference_components(lab, group_avg)
                        breakdown = format_lab_components_compact(components)
                        value_text += f"\n  {breakdown}"
                    except Exception as e:
                        print(f"DEBUG: Δ breakdown failed: {e}")
            
            # Add StdDev if available (conditionally based on user preferences)
            stddev_text = get_conditional_stddev_text(rgb_stddev, lab_stddev)
            if stddev_text:
                value_text += f"\n{stddev_text}"
            
            ttk.Label(frame, text=value_text, font=("Arial", 12)).pack(
                side=tk.LEFT, padx=20)
            
            # Color swatch using canvas - increased height to accommodate multi-line text
            canvas = tk.Canvas(
                frame,
                width=450,
                height=100,
                highlightthickness=1,
                highlightbackground='gray'
            )
            canvas.pack(side=tk.RIGHT, padx=5, pady=2)
            
            # Create rectangle for color display
            canvas.create_rectangle(
                0, 0, 450, 100,
                fill=f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}",
                outline=''
            )
    
    def _update_average_display(self):
        """Render ink and (optionally) paper average sections.
        
        Ink samples produce the primary, full-size swatch with the existing
        action buttons (Add to library, Save to DB, Save to File, Save
        comparison image). Paper samples, if any are enabled, get their
        own smaller readout below — no action buttons, since the existing
        Save buttons will handle paper persistence in slice 2 by routing
        them to a '-p' measurement set inside the same DB.
        """
        # Clear existing display
        for widget in self.average_frame.winfo_children():
            widget.destroy()
        
        enabled_ink = [s for s in self.sample_points
                       if s['enabled'].get() and not s['is_paper'].get()]
        enabled_paper = [s for s in self.sample_points
                         if s['enabled'].get() and s['is_paper'].get()]
        
        if not enabled_ink and not enabled_paper:
            ttk.Label(self.average_frame, text="No samples enabled").pack(pady=20)
            return
        
        if enabled_ink:
            self._render_average_section(
                samples=enabled_ink,
                label="Average Color (ink)",
                big=True,
                with_buttons=True,
            )
        else:
            ttk.Label(
                self.average_frame,
                text=("No ink samples enabled.\n"
                      "Uncheck 'P' on at least one sample to compute an ink average."),
                font=("Arial", 10), justify=tk.LEFT,
            ).pack(anchor='w', padx=10, pady=10)
        
        if enabled_paper:
            self._render_average_section(
                samples=enabled_paper,
                label="Paper Color",
                big=False,
                with_buttons=False,
            )
    
    def _render_average_section(self, samples, label, big=True, with_buttons=False):
        """Render one labelled average swatch + readout into ``self.average_frame``.
        
        Args:
            samples: list of enabled sample dicts in this group (ink or paper).
            label: section heading shown above the swatch.
            big: True for the primary ink swatch (450×360); False for the
                smaller paper swatch (450×120).
            with_buttons: True attaches the existing 'Add to library' /
                'Save to DB' / 'Save to File' / 'Save comparison image…'
                actions, which currently operate on the ink group.
        """
        from utils.color_analyzer import ColorAnalyzer
        from utils.color_display_utils import get_conditional_color_values_text
        
        analyzer = ColorAnalyzer()
        
        lab_values = []
        rgb_values = []
        for sample in samples:
            rgb = sample['rgb']
            lab = (self.library.rgb_to_lab(rgb)
                   if self.library else analyzer.rgb_to_lab(rgb))
            lab_values.append(lab)
            rgb_values.append(rgb)
        
        averaging_result = analyzer._calculate_quality_controlled_average(
            lab_values, rgb_values,
        )
        avg_rgb = averaging_result['avg_rgb']
        avg_lab = averaging_result['avg_lab']
        max_delta_e = averaging_result['max_delta_e']
        samples_used = averaging_result['samples_used']
        outliers_excluded = averaging_result['outliers_excluded']
        
        # Section header
        ttk.Label(
            self.average_frame, text=label,
            font=("Arial", 12, "bold"),
        ).pack(anchor='w', padx=10, pady=(8, 2))
        
        # Display row
        frame = ttk.Frame(self.average_frame)
        frame.pack(fill=tk.BOTH, expand=big, padx=0, pady=5)
        
        sw_w = 450
        sw_h = 360 if big else 120
        
        canvas = tk.Canvas(
            frame, width=sw_w, height=sw_h,
            highlightthickness=1, highlightbackground='gray',
        )
        canvas.pack(side=tk.LEFT, padx=5, pady=5)
        canvas.create_rectangle(
            0, 0, sw_w, sw_h,
            fill=f"#{int(avg_rgb[0]):02x}{int(avg_rgb[1]):02x}{int(avg_rgb[2]):02x}",
            outline='',
        )
        
        value_text = get_conditional_color_values_text(
            avg_rgb, avg_lab, compact=True,
        )
        
        values_frame = ttk.Frame(frame)
        values_frame.pack(side=tk.LEFT, padx=20, fill=tk.Y)
        
        ttk.Label(
            values_frame, text=value_text,
            font=("Arial", 14 if big else 12),
        ).pack(pady=(10 if big else 4))
        
        if outliers_excluded > 0:
            outlier_text = (
                f"\nAveraging Quality Control:\n"
                f"{samples_used}/{len(samples)} samples used\n"
                f"{outliers_excluded} outlier(s) excluded\n"
                f"Max ΔE from centroid: {max_delta_e:.2f}"
            )
            ttk.Label(values_frame, text=outlier_text, font=("Arial", 10)).pack(pady=5)
        
        if not with_buttons:
            return
        
        # --- ink-only action buttons -------------------------------------- #
        ttk.Frame(values_frame, height=15).pack()
        buttons_frame = ttk.Frame(values_frame)
        buttons_frame.pack(anchor='se', pady=(0, 5))
        
        add_button = ttk.Button(
            buttons_frame, text="Add color to library",
            command=lambda: self._add_color_to_library(avg_rgb, avg_lab),
        )
        add_button.pack(fill=tk.X, pady=2)
        
        save_db_button = ttk.Button(
            buttons_frame, text="Save to DB",
            command=lambda: self._save_to_database(avg_rgb, avg_lab, samples),
        )
        save_db_button.pack(fill=tk.X, pady=2)
        
        save_file_button = ttk.Button(
            buttons_frame, text="Save to File",
            command=lambda: self._save_to_text_file(avg_rgb, avg_lab, samples),
        )
        save_file_button.pack(fill=tk.X, pady=2)
        
        compare_button = ttk.Button(
            buttons_frame, text="Save comparison image…",
            command=lambda: self._save_comparison_image(avg_rgb, avg_lab),
        )
        compare_button.pack(fill=tk.X, pady=2)
        
        # Coverage analysis (effective-tone) requires the user to have
        # cropped the image and tagged at least one sample as paper.
        # The button itself is always visible; the handler validates and
        # complains if either pre-condition isn't met.
        coverage_button = ttk.Button(
            buttons_frame, text="Compute coverage…",
            command=lambda mr=avg_rgb, ml=avg_lab: self._show_coverage_analysis(
                marker_avg_rgb=mr, marker_avg_lab=ml,
            ),
        )
        coverage_button.pack(fill=tk.X, pady=2)
    
    def _show_coverage_analysis(self, marker_avg_rgb=None, marker_avg_lab=None):
        """Run the coverage / effective-tone analyzer and show the result.
        
        Resolves the paper-Lab reference through a 3-step chain (see
        ``_resolve_paper_lab_for_coverage``), then delegates to
        ``_run_coverage_with_tolerance`` for the actual analyze + show.
        Splitting it this way lets the dialog's 'Recompute' button
        re-run with a different paper-tolerance without re-walking the
        paper-Lab resolution chain.
        """
        if not getattr(self, 'current_image', None):
            messagebox.showerror(
                "No Image",
                "Load and crop an image, then run an analysis before "
                "computing coverage.",
            )
            return
        
        paper_lab, paper_rgb, paper_source_desc, n_paper_samples = (
            self._resolve_paper_lab_for_coverage()
        )
        if paper_lab is None:
            return  # user cancelled the picker, or there was an error
        
        # First pass uses the analyzer's default tolerance (5.0 ΔE).
        self._run_coverage_with_tolerance(
            paper_lab=paper_lab,
            paper_rgb=paper_rgb,
            paper_source_desc=paper_source_desc,
            n_paper_samples=n_paper_samples,
            marker_avg_rgb=marker_avg_rgb,
            marker_avg_lab=marker_avg_lab,
            paper_tolerance=None,  # use default
        )
    
    def _run_coverage_with_tolerance(
        self, paper_lab, paper_rgb, paper_source_desc, n_paper_samples,
        marker_avg_rgb, marker_avg_lab, paper_tolerance,
    ):
        """Run the coverage analyzer once and present its result dialog.
        
        Used both by the initial click on 'Compute coverage…' and by the
        dialog's 'Recompute' button. The paper-Lab metadata is passed
        through unchanged so we don't re-prompt the user.
        
        Args:
            paper_tolerance: ΔE radius for the paper class. Pass ``None``
                to use ``coverage_analyzer.DEFAULT_PAPER_TOLERANCE``.
        """
        try:
            from utils.coverage_analyzer import (
                analyze_coverage, DEFAULT_PAPER_TOLERANCE,
            )
        except ImportError as e:
            messagebox.showerror(
                "Missing Module",
                f"Could not load coverage analyzer:\n\n{e}",
            )
            return
        
        if paper_tolerance is None:
            paper_tolerance = DEFAULT_PAPER_TOLERANCE
        
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            result = analyze_coverage(
                self.current_image,
                paper_lab=paper_lab,
                paper_tolerance=float(paper_tolerance),
            )
        except Exception as e:
            self.config(cursor="")
            messagebox.showerror(
                "Coverage Analysis Failed",
                f"Could not analyse coverage:\n\n{e}",
            )
            return
        finally:
            self.config(cursor="")
        
        # Stash the inputs so the dialog's Recompute button can call us
        # again without re-resolving the paper Lab. We also stash the
        # tolerance so the 'Save comparison image…' striped swatch can
        # inherit it — otherwise that flow would silently revert to the
        # default ΔE 5.0 and produce a mismatched coverage figure.
        self._coverage_session = {
            'paper_lab': paper_lab,
            'paper_rgb': paper_rgb,
            'paper_source_desc': paper_source_desc,
            'n_paper_samples': n_paper_samples,
            'marker_avg_rgb': marker_avg_rgb,
            'marker_avg_lab': marker_avg_lab,
            'paper_tolerance': float(paper_tolerance),
        }
        
        self._show_coverage_results_dialog(
            result=result,
            paper_rgb=paper_rgb,
            marker_avg_rgb=marker_avg_rgb,
            marker_avg_lab=marker_avg_lab,
            n_paper_samples=n_paper_samples,
            paper_source_desc=paper_source_desc,
        )
    
    def _resolve_paper_lab_for_coverage(self):
        """Return ``(paper_lab, paper_rgb, source_desc, n_samples)``.
        
        Walks the 3-step chain described in ``_show_coverage_analysis``
        and returns ``(None, None, None, 0)`` if the user cancels the
        manual picker (so the caller bails out cleanly).
        """
        from utils.color_analyzer import ColorAnalyzer
        analyzer = ColorAnalyzer()
        
        # --- 1) in-image P samples ---------------------------------- #
        paper_samples = self._enabled_paper_samples()
        if paper_samples:
            paper_lab_values = []
            paper_rgb_values = []
            for s in paper_samples:
                rgb = s['rgb']
                lab = (self.library.rgb_to_lab(rgb)
                       if self.library else analyzer.rgb_to_lab(rgb))
                paper_lab_values.append(lab)
                paper_rgb_values.append(rgb)
            avg = analyzer._calculate_quality_controlled_average(
                paper_lab_values, paper_rgb_values,
            )
            return (
                avg['avg_lab'],
                avg['avg_rgb'],
                f"in-image samples ({len(paper_samples)})",
                len(paper_samples),
            )
        
        # --- 2) auto-detect from saved DB --------------------------- #
        try:
            from utils.paper_lab_lookup import find_saved_paper_lab
        except Exception:
            find_saved_paper_lab = None  # type: ignore[assignment]
        
        auto_source = None
        if find_saved_paper_lab and getattr(self, 'current_file_path', None):
            try:
                auto_source = find_saved_paper_lab(self.current_file_path)
            except Exception:
                auto_source = None
        
        if auto_source is not None:
            paper_rgb = self._lab_to_display_rgb(auto_source.lab)
            return (
                auto_source.lab,
                paper_rgb,
                f"auto-detected: {auto_source.describe()}",
                auto_source.sample_count,
            )
        
        # --- 3) manual picker (with explicit confirmation) --------- #
        picked = self._prompt_for_saved_paper_set(
            note=(
                "This image has no paper-tagged samples and no saved "
                "'-p' measurement set was found by filename.\n\n"
                "Pick a saved paper measurement set to use as the "
                "reference, or cancel and add a 'P' sample first.\n\n"
                "Tip: For tightly-printed designs you can shrink the "
                "sample size in Preferences → Sampling (e.g. 5×5 or "
                "3×3 px) and place 'P' samples in small unprinted "
                "areas inside the design."
            ),
        )
        if picked is None:
            return (None, None, None, 0)
        
        paper_rgb = self._lab_to_display_rgb(picked.lab)
        return (
            picked.lab,
            paper_rgb,
            f"manually selected: {picked.describe()}",
            picked.sample_count,
        )
    
    def _prompt_for_saved_paper_set(self, note=""):
        """Modal picker that lists every saved ``-p`` set, newest-first.
        
        Returns the chosen ``PaperLabSource`` or ``None`` if cancelled.
        """
        try:
            from utils.paper_lab_lookup import list_all_paper_sets
        except Exception as e:
            messagebox.showerror(
                "Missing Module",
                f"Could not load paper-lab lookup helper:\n\n{e}",
            )
            return None
        
        sources = list_all_paper_sets()
        if not sources:
            messagebox.showerror(
                "No Saved Paper Data",
                "No paper-tagged measurement sets were found in any "
                "analysis database.\n\n"
                "Place at least one 'P' sample on a stamp's margin and "
                "click 'Save to DB' to create one.",
            )
            return None
        
        dialog = tk.Toplevel(self)
        dialog.title("Select Saved Paper Measurement Set")
        dialog.grab_set()
        
        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            outer,
            text="Select a saved '-p' measurement set to use as the "
                 "paper reference:",
            font=("Arial", 11, "bold"),
        ).pack(anchor='w', pady=(0, 4))
        
        if note:
            ttk.Label(
                outer, text=note, font=("Arial", 9),
                foreground='gray', justify=tk.LEFT, wraplength=540,
            ).pack(anchor='w', pady=(0, 8))
        
        # Listbox of sources, newest-first
        list_frame = ttk.Frame(outer)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        listbox = tk.Listbox(
            list_frame, height=12, width=72,
            font=("Menlo", 11), exportselection=False,
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=listbox.yview,
        )
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for src in sources:
            L, a, b = src.lab
            entry = (
                f"{src.set_name:<24}  "
                f"L*{L:6.1f} a*{a:6.1f} b*{b:6.1f}   "
                f"n={src.sample_count}   "
                f"{src.measurement_date or '(date n/a)'}   "
                f"in {src.db_name}"
            )
            listbox.insert(tk.END, entry)
        listbox.selection_set(0)
        listbox.activate(0)
        
        # Centre on parent monitor
        dialog.update_idletasks()
        try:
            parent = self.winfo_toplevel()
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            dw = max(620, dialog.winfo_reqwidth())
            dh = max(380, dialog.winfo_reqheight())
            x = px + max(0, (pw - dw) // 2)
            y = py + max(0, (ph - dh) // 2)
            dialog.geometry(f"{dw}x{dh}+{x}+{y}")
        except Exception:
            pass
        
        chosen = {'src': None}
        
        def on_use():
            sel = listbox.curselection()
            if not sel:
                return
            chosen['src'] = sources[sel[0]]
            dialog.destroy()
        
        def on_cancel():
            chosen['src'] = None
            dialog.destroy()
        
        listbox.bind('<Double-Button-1>', lambda _e: on_use())
        
        btn_bar = ttk.Frame(outer, padding=(0, 8, 0, 0))
        btn_bar.pack(fill=tk.X)
        ttk.Button(btn_bar, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)
        ttk.Button(
            btn_bar, text="Use this paper set",
            command=on_use,
        ).pack(side=tk.RIGHT, padx=(0, 6))
        
        dialog.wait_window()
        return chosen['src']
    
    def _show_coverage_results_dialog(
        self, result, paper_rgb, marker_avg_rgb, marker_avg_lab, n_paper_samples,
        paper_source_desc=None,
    ):
        """Render the coverage analysis report in a Toplevel.
        
        Layout (top-down):
          * Header with filename and tuning notes (including which
            paper-Lab source was used — in-image, auto-detected, or
            manually selected).
          * Numeric panel: paper / ink (whole-region) / ink (markers) /
            effective tone, each with a swatch and Lab triple.
          * Coverage ratio + pixel-count breakdown.
          * Classification preview image (scaled to fit the screen).
          * Save preview / Close buttons.
        """
        from PIL import ImageTk
        
        viewer = tk.Toplevel(self)
        viewer.title("Coverage Analysis")
        
        outer = ttk.Frame(viewer, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        
        # --- header --------------------------------------------------- #
        title_text = "Coverage Analysis"
        if getattr(self, 'current_file_path', None):
            title_text += f" — {os.path.basename(self.current_file_path)}"
        ttk.Label(
            outer, text=title_text, font=("Arial", 14, "bold"),
        ).pack(anchor='w', pady=(0, 2))
        
        tuning_text = (
            f"paper tolerance ΔE {result.paper_tolerance:.1f}    "
            f"edge band ×{result.edge_band_factor:.1f}    "
            f"neutral-dark L*<{result.dark_l_threshold:.0f} ∧ "
            f"C*<{result.dark_c_threshold:.0f}    "
            f"paper samples: {n_paper_samples}"
        )
        ttk.Label(outer, text=tuning_text, font=("Arial", 9),
                  foreground='gray').pack(anchor='w', pady=(0, 2))
        
        if paper_source_desc:
            ttk.Label(
                outer, text=f"paper Lab source: {paper_source_desc}",
                font=("Arial", 9, "italic"), foreground='#444',
            ).pack(anchor='w', pady=(0, 8))
        else:
            # Keep the spacing consistent with the no-source-line case.
            ttk.Frame(outer, height=6).pack()
        
        # --- swatches + numbers --------------------------------------- #
        swatch_frame = ttk.Frame(outer)
        swatch_frame.pack(fill=tk.X, pady=(0, 8))
        
        def _add_swatch_row(parent, label, rgb, lab, *, big=False, note=""):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=2)
            sw_w, sw_h = (160, 56) if big else (100, 36)
            canvas = tk.Canvas(
                row, width=sw_w, height=sw_h,
                highlightthickness=1, highlightbackground='gray',
            )
            canvas.pack(side=tk.LEFT, padx=(0, 10))
            r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
            canvas.create_rectangle(
                0, 0, sw_w, sw_h, fill=f"#{r:02x}{g:02x}{b:02x}", outline='',
            )
            text = (
                f"{label}\n"
                f"  L* {lab[0]:6.2f}    a* {lab[1]:6.2f}    b* {lab[2]:6.2f}"
            )
            if note:
                text += f"\n  {note}"
            ttk.Label(
                row, text=text, font=("Menlo", 11) if big else ("Menlo", 10),
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, anchor='w')
        
        # Paper reference
        _add_swatch_row(
            swatch_frame, "Paper (reference)",
            paper_rgb, result.paper_lab,
        )
        
        # Ink (whole-region) — the primary readout
        # Convert ink Lab to a display sRGB swatch via colorspacious if available;
        # otherwise approximate. We only need this for the swatch fill.
        ink_rgb = self._lab_to_display_rgb(result.ink_lab)
        _add_swatch_row(
            swatch_frame, "Ink (whole-region, primary)",
            ink_rgb, result.ink_lab, big=True,
            note="Mean Lab of every pixel classified as ink.",
        )
        
        # Ink (markers, secondary) — only if markers exist
        if marker_avg_rgb and marker_avg_lab:
            _add_swatch_row(
                swatch_frame, "Ink (markers, secondary)",
                marker_avg_rgb, marker_avg_lab,
                note="Average of the ink samples you placed on the canvas.",
            )
        
        # Effective tone — what the eye fuses to at viewing distance
        _add_swatch_row(
            swatch_frame, "Effective tone (perceived)",
            result.effective_tone_rgb, result.effective_tone_lab, big=True,
            note="coverage·ink + (1−coverage)·paper, blended in linear RGB.",
        )
        
        # --- coverage + counts ---------------------------------------- #
        ratio_pct = result.coverage_ratio * 100.0
        counts_text = (
            f"Coverage ratio: {ratio_pct:.1f}%   "
            f"(ink {result.n_ink:,}   cancel {result.n_cancel:,}   "
            f"edge {result.n_edge:,}   paper {result.n_paper:,}   "
            f"of {result.n_visible:,} visible px)"
        )
        ttk.Label(
            outer, text=counts_text, font=("Arial", 11, "bold"),
        ).pack(anchor='w', pady=(4, 8))
        
        # --- classification preview ----------------------------------- #
        preview_frame = ttk.LabelFrame(
            outer,
            text=(
                "Classification preview "
                "(ink = original colour; paper = lightened; "
                "edge = mid grey; cancel = darkened)"
            ),
            padding=6,
        )
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scale the preview down if it's larger than ~700 px in either axis
        # so the dialog stays usable on a laptop.
        max_w, max_h = 800, 500
        prev_img = result.classification_image
        pw, ph = prev_img.size
        scale = min(1.0, max_w / pw, max_h / ph)
        if scale < 1.0:
            prev_img_disp = prev_img.resize(
                (max(1, int(pw * scale)), max(1, int(ph * scale))),
                Image.LANCZOS,
            )
        else:
            prev_img_disp = prev_img
        
        photo = ImageTk.PhotoImage(prev_img_disp)
        prev_label = ttk.Label(preview_frame, image=photo, anchor='center')
        prev_label.image = photo  # keep a reference
        prev_label.pack(fill=tk.BOTH, expand=True)
        
        # --- buttons + tolerance control ------------------------------ #
        btn_bar = ttk.Frame(outer, padding=(0, 8, 0, 0))
        btn_bar.pack(fill=tk.X)
        
        # Tolerance spinbox — lets the user re-run with a different ΔE
        # threshold without re-walking the paper-Lab chain. The session
        # state was stashed on ``self._coverage_session`` by
        # ``_run_coverage_with_tolerance``.
        tol_frame = ttk.Frame(btn_bar)
        tol_frame.pack(side=tk.LEFT)
        
        ttk.Label(tol_frame, text="Paper tolerance ΔE:").pack(side=tk.LEFT)
        
        tol_var = tk.DoubleVar(value=float(result.paper_tolerance))
        tol_spin = ttk.Spinbox(
            tol_frame, from_=1.0, to=30.0, increment=0.5,
            textvariable=tol_var, width=6, justify='center',
        )
        tol_spin.pack(side=tk.LEFT, padx=(4, 6))
        
        def on_recompute():
            try:
                new_tol = float(tol_var.get())
            except (tk.TclError, ValueError):
                messagebox.showerror(
                    "Invalid Tolerance",
                    "Paper tolerance must be a positive number.",
                )
                return
            if new_tol <= 0:
                messagebox.showerror(
                    "Invalid Tolerance",
                    "Paper tolerance must be greater than zero.",
                )
                return
            session = getattr(self, '_coverage_session', None)
            if not session:
                messagebox.showerror(
                    "Recompute Failed",
                    "Lost the paper Lab from the previous run. "
                    "Close this window and click 'Compute coverage…' again.",
                )
                return
            viewer.destroy()
            self._run_coverage_with_tolerance(
                paper_lab=session['paper_lab'],
                paper_rgb=session['paper_rgb'],
                paper_source_desc=session['paper_source_desc'],
                n_paper_samples=session['n_paper_samples'],
                marker_avg_rgb=session['marker_avg_rgb'],
                marker_avg_lab=session['marker_avg_lab'],
                paper_tolerance=new_tol,
            )
        
        ttk.Button(
            tol_frame, text="Recompute",
            command=on_recompute,
        ).pack(side=tk.LEFT)
        
        # Right-aligned actions
        def on_save_preview():
            self._save_classification_preview(result.classification_image)
        
        ttk.Button(btn_bar, text="Close", command=viewer.destroy).pack(side=tk.RIGHT)
        ttk.Button(
            btn_bar, text="Save preview image…",
            command=on_save_preview,
        ).pack(side=tk.RIGHT, padx=(0, 6))
        
        # --- centre on the parent's monitor (multi-display friendly) -- #
        viewer.update_idletasks()
        try:
            parent_window = self.winfo_toplevel()
            px = parent_window.winfo_x()
            py = parent_window.winfo_y()
            pw_ = parent_window.winfo_width()
            ph_ = parent_window.winfo_height()
            vw = viewer.winfo_width()
            vh = viewer.winfo_height()
            x = px + max(0, (pw_ - vw) // 2)
            y = py + max(0, (ph_ - vh) // 2)
            viewer.geometry(f"+{x}+{y}")
        except Exception:
            pass
    
    def _lab_to_display_rgb(self, lab):
        """Convert a Lab tuple to a display-ready sRGB ``(r, g, b)`` triple.
        
        Used purely to fill the on-screen Tk swatches. Falls back to mid
        grey if colorspacious is unavailable.
        """
        try:
            from colorspacious import cspace_convert
            import numpy as np
            srgb = np.asarray(cspace_convert(np.asarray(lab), "CIELab", "sRGB1"))
            srgb = np.clip(srgb, 0.0, 1.0)
            return tuple(int(round(c * 255.0)) for c in srgb)
        except Exception:
            return (128, 128, 128)
    
    def _save_classification_preview(self, image):
        """Save the classification preview image with an embedded sRGB ICC."""
        from tkinter import filedialog
        
        default_dir = None
        suggested_name = "coverage_classification"
        if getattr(self, 'current_file_path', None):
            default_dir = os.path.dirname(self.current_file_path)
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            suggested_name = f"{base}_coverage_classification"
        
        filepath = filedialog.asksaveasfilename(
            title="Save Classification Preview",
            defaultextension=".png",
            initialfile=f"{suggested_name}.png",
            initialdir=default_dir,
            filetypes=[
                ("PNG (lossless, recommended)", "*.png"),
                ("TIFF", "*.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not filepath:
            return
        
        try:
            from utils.icc_profiles import get_save_icc_profile
            kwargs = {}
            icc = get_save_icc_profile(image)
            if icc:
                kwargs["icc_profile"] = icc
            image.save(filepath, **kwargs)
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save image:\n\n{e}")
            return
        
        messagebox.showinfo(
            "Saved",
            f"Classification preview saved:\n\n{os.path.basename(filepath)}",
        )
    
    def _on_sample_toggle(self):
        """Handle sample toggle events (enable/disable, ink/paper).
        
        Refreshes both panes because toggling 'P' changes which group a
        sample belongs to, which changes the per-sample ΔE label and the
        composition of both the ink and paper averages.
        """
        self._display_sample_points()
        self._update_average_display()
    
    # Minimum number of samples that must remain tagged as ink (not 'P')
    # in any session. Keeping this >= 2 ensures the ink section always
    # has content, so the Save / Compute coverage buttons stay visible.
    MIN_INK_SAMPLES = 2
    
    def _on_paper_toggle(self, sample):
        """Validate a 'P' tag toggle, then refresh the panes.
        
        Enforces ``MIN_INK_SAMPLES`` ink-tagged samples per session: if
        the toggle that just fired would push the ink-tagged count below
        the minimum, we revert the BooleanVar and show a brief notice.
        Going the other way (paper → ink) is always allowed because it
        can only increase the ink count.
        
        On a successful toggle we also push the new role into the canvas
        live model (when one is wired) so the on-image ΔE HUD recomputes
        each marker's distance against its own group's QC mean. Without
        this, the HUD would still average ink + paper into one bucket
        and never agree with the Results panel ΔE numbers.
        """
        becoming_paper = sample['is_paper'].get()
        if becoming_paper:
            ink_tagged_count = sum(
                1 for s in self.sample_points if not s['is_paper'].get()
            )
            if ink_tagged_count < self.MIN_INK_SAMPLES:
                # Snap the toggle back; refresh would be wasted work.
                sample['is_paper'].set(False)
                messagebox.showinfo(
                    "Minimum Ink Samples",
                    f"Each session must keep at least {self.MIN_INK_SAMPLES} "
                    f"ink-tagged samples.\n\n"
                    f"With the default six-sample maximum, you can tag up "
                    f"to four samples as paper, leaving the ink set big "
                    f"enough to compute a meaningful average.",
                )
                return
        
        # Mirror the new role into the canvas live model so the on-image
        # HUD agrees with what the Results panel will show. Quietly skip
        # if Results was populated outside the standard analyse flow
        # (no back-ref wired) — the panel still works, just without
        # live-canvas synchronisation.
        live_model = getattr(self, '_live_model_ref', None)
        if live_model is not None:
            try:
                live_model.set_paper(
                    sample['index'], bool(sample['is_paper'].get()),
                )
            except Exception as e:
                print(f"DEBUG: could not push P toggle to live model: {e}")
        
        self._on_sample_toggle()
    
    def _save_comparison_image(self, avg_rgb, avg_lab):
        """Export the current stamp image composed with the average swatch.
        
        Two layouts are offered:
          * "Swatch behind stamp" — solid swatch as the bottom layer, stamp
            on top. If the stamp was loaded from a shape-cropped PNG/TIFF
            (alpha channel present), the swatch shows through the
            transparent corners.
          * "Side by side" — stamp on the left, swatch panel on the right
            with the RGB / Lab values printed on it.
        """
        if not getattr(self, 'current_image', None):
            messagebox.showerror(
                "No Image",
                "Load an image and run an analysis before saving a comparison image.",
            )
            return
        if not avg_rgb:
            messagebox.showerror("No Average", "No average colour is available.")
            return
        
        # --- layout chooser dialog ---------------------------------------- #
        dialog = tk.Toplevel(self)
        dialog.title("Save Comparison Image")
        dialog.grab_set()
        
        # Center relative to parent window so it appears on the correct
        # monitor in multi-display setups.
        dialog.update_idletasks()
        dlg_w, dlg_h = 480, 430  # taller to fit the new Swatch colour section
        try:
            parent_window = self.winfo_toplevel()
            px = parent_window.winfo_x()
            py = parent_window.winfo_y()
            pw = parent_window.winfo_width()
            ph = parent_window.winfo_height()
            x = px + (pw - dlg_w) // 2
            y = py + (ph - dlg_h) // 2
            dialog.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")
        except Exception:
            dialog.geometry(f"{dlg_w}x{dlg_h}")
        
        ttk.Label(
            dialog, text="Save Comparison Image",
            font=("Arial", 14, "bold"),
        ).pack(pady=(12, 6))
        
        layout_var = tk.StringVar(value="swatch_behind")
        swatch_source_var = tk.StringVar(value="marker")
        include_values_var = tk.BooleanVar(value=True)
        padding_var = tk.IntVar(value=60)
        
        layout_frame = ttk.LabelFrame(dialog, text="Layout", padding=8)
        layout_frame.pack(fill=tk.X, padx=16, pady=6)
        ttk.Radiobutton(
            layout_frame,
            text="Swatch behind stamp (best for cropped shapes)",
            variable=layout_var, value="swatch_behind",
        ).pack(anchor="w")
        ttk.Radiobutton(
            layout_frame,
            text="Side-by-side panel (stamp | swatch)",
            variable=layout_var, value="side_by_side",
        ).pack(anchor="w")
        
        # --- Swatch colour source ---------------------------------------- #
        # Marker average is the existing behaviour (the ink-sample mean
        # the user already sees in the Results panel).
        #
        # Striped renders alternating paper / ink stripes at the actual
        # coverage ratio measured by the coverage analyzer, so the
        # swatch *behaves* the same way the stamp does as viewing
        # distance changes: visible structure up close, fused tone at
        # distance. That parallel behaviour is a more honest
        # perceptual comparison than any flat coverage-weighted blend.
        # Picking it triggers the same paper-Lab resolution chain as
        # 'Compute coverage…' (in-image P samples → saved -p set → picker).
        swatch_src_frame = ttk.LabelFrame(dialog, text="Swatch colour", padding=8)
        swatch_src_frame.pack(fill=tk.X, padx=16, pady=6)
        ttk.Radiobutton(
            swatch_src_frame,
            text="Marker average (ink samples on the canvas)",
            variable=swatch_source_var, value="marker",
        ).pack(anchor="w")
        ttk.Radiobutton(
            swatch_src_frame,
            text="Striped pattern (paper + ink at coverage ratio) — runs coverage analysis",
            variable=swatch_source_var, value="striped",
        ).pack(anchor="w")
        
        opts_frame = ttk.LabelFrame(dialog, text="Options", padding=8)
        opts_frame.pack(fill=tk.X, padx=16, pady=6)
        ttk.Checkbutton(
            opts_frame,
            text="Print RGB / L*a*b* values on the side-by-side swatch",
            variable=include_values_var,
        ).pack(anchor="w")
        
        pad_row = ttk.Frame(opts_frame)
        pad_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(pad_row, text="Swatch frame padding (px):").pack(side=tk.LEFT)
        ttk.Spinbox(
            pad_row, from_=0, to=400, increment=10,
            textvariable=padding_var, width=6,
        ).pack(side=tk.LEFT, padx=(6, 0))
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=16, pady=(10, 14))
        
        def _build():
            """Build the composite image from the current dialog values.
            
            When the user selects 'Striped pattern' as the swatch source,
            we walk the coverage paper-Lab resolution chain (in-image
            'P' samples → auto-detect saved '-p' set → manual picker),
            run ``analyze_coverage`` once at the analyzer's default
            tolerance, and render a small (period × period) tile of
            ink-and-paper stripes at the measured coverage ratio. The
            composer tiles that across the swatch panel / backdrop so
            the swatch behaves perceptually like the stamp itself.
            
            For the side-by-side layout we also build a custom text
            block listing both ink and paper Lab values plus the
            coverage %, since a single 'Average' line wouldn't reflect
            what the swatch actually shows.
            
            The output filename is suffixed ``_striped`` so it's
            distinguishable from the flat marker-average composite.
            """
            swatch_source = swatch_source_var.get()
            rgb_to_use = avg_rgb
            lab_to_use = avg_lab
            text_block = None
            text_bg_rgb = None
            suffix_extra = ""
            
            if swatch_source == "striped":
                # 1) resolve paper Lab + tolerance.
                # If the user has just run 'Compute coverage…' on this
                # image, inherit the paper Lab AND the tolerance they
                # settled on — otherwise this flow would silently fall
                # back to the default ΔE 5.0 and the coverage figure on
                # the saved swatch wouldn't match what they saw in the
                # Coverage Analysis dialog. If there's no session, walk
                # the existing 3-step chain and use the analyzer default.
                session = getattr(self, '_coverage_session', None)
                inherited_tol = None
                if session and session.get('paper_lab') is not None:
                    paper_lab = session['paper_lab']
                    source_desc = (
                        session.get('paper_source_desc')
                        or 'last computed coverage'
                    )
                    inherited_tol = session.get('paper_tolerance')
                else:
                    paper_lab, _paper_rgb, source_desc, _n = (
                        self._resolve_paper_lab_for_coverage()
                    )
                    if paper_lab is None:
                        return None, None  # user cancelled the picker
                
                # 2) run the coverage analyzer to get ink Lab + coverage
                try:
                    from utils.coverage_analyzer import analyze_coverage
                    from utils.comparison_image import make_striped_swatch
                except ImportError as e:
                    messagebox.showerror(
                        "Missing Module",
                        f"Could not load coverage helpers:\n\n{e}",
                    )
                    return None, None
                
                try:
                    self.config(cursor="watch")
                    self.update_idletasks()
                    analyze_kwargs = {'paper_lab': paper_lab}
                    if inherited_tol is not None:
                        analyze_kwargs['paper_tolerance'] = float(inherited_tol)
                    result = analyze_coverage(
                        self.current_image, **analyze_kwargs,
                    )
                except Exception as e:
                    self.config(cursor="")
                    messagebox.showerror(
                        "Coverage Analysis Failed",
                        f"Could not analyse coverage:\n\n{e}",
                    )
                    return None, None
                finally:
                    self.config(cursor="")
                
                # 3) render the tile from the analyzer outputs
                ink_rgb_disp = self._lab_to_display_rgb(result.ink_lab)
                paper_rgb_disp = self._lab_to_display_rgb(paper_lab)
                cov = max(0.0, min(1.0, float(result.coverage_ratio)))
                tile = make_striped_swatch(
                    ink_rgb=ink_rgb_disp,
                    paper_rgb=paper_rgb_disp,
                    coverage_ratio=cov,
                    period=10,           # vertical 10-px stripe pair
                )
                
                # 4) text-contrast colour: simple sRGB linear blend
                # (good enough for picking black vs. white text;
                # doesn't need to be perceptually exact).
                text_bg_rgb = tuple(
                    int(round(cov * ink_rgb_disp[i]
                              + (1.0 - cov) * paper_rgb_disp[i]))
                    for i in range(3)
                )
                
                # 5) text block for the side-by-side panel
                pct = cov * 100.0
                text_block = [
                    "Perceived (striped)",
                    (f"Ink    L*{result.ink_lab[0]:5.1f}  "
                     f"a*{result.ink_lab[1]:5.1f}  "
                     f"b*{result.ink_lab[2]:5.1f}"),
                    (f"Paper  L*{paper_lab[0]:5.1f}  "
                     f"a*{paper_lab[1]:5.1f}  "
                     f"b*{paper_lab[2]:5.1f}"),
                    f"Coverage  {pct:.1f}%",
                ]
                
                rgb_to_use = tile          # composer treats Image as tile
                lab_to_use = None
                suffix_extra = "_striped"
                
                # 6) one-line confirmation in the debug log
                print(
                    f"DEBUG comparison-image: striped swatch "
                    f"(coverage {pct:.1f}%, paper from {source_desc}, "
                    f"ΔE tol {result.paper_tolerance:.1f})"
                )
            
            composite, suffix = self._build_comparison_image(
                layout=layout_var.get(),
                avg_rgb=rgb_to_use,
                avg_lab=lab_to_use,
                include_values=include_values_var.get(),
                frame_padding=max(0, int(padding_var.get())),
                text_block=text_block,
                text_bg_rgb=text_bg_rgb,
            )
            if composite is None:
                return None, None
            return composite, suffix + suffix_extra
        
        def do_preview():
            composite, suffix = _build()
            if composite is None:
                return
            dialog.destroy()
            self._show_comparison_preview(
                composite=composite,
                avg_rgb=avg_rgb,
                avg_lab=avg_lab,
                suggested_suffix=suffix,
                layout=layout_var.get(),
            )
        
        def do_save():
            composite, suffix = _build()
            if composite is None:
                return
            dialog.destroy()
            self._save_composite_to_disk(composite, suffix)
        
        ttk.Button(button_frame, text="Preview", command=do_preview).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Save…", command=do_save).pack(
            side=tk.RIGHT, padx=(0, 6),
        )
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=(0, 6),
        )
    
    def _build_comparison_image(
        self, layout, avg_rgb, avg_lab, include_values, frame_padding,
        text_block=None, text_bg_rgb=None,
    ):
        """Return ``(composite_image, filename_suffix)`` or ``(None, None)``.
        
        Centralises the composer dispatch so Preview and Save go through
        the same code path with identical parameters.
        
        ``avg_rgb`` may be either a solid RGB triple (the marker
        average) or a small PIL tile image which the composers tile
        across the swatch backdrop / panel (the striped paper/ink
        pattern). ``text_block`` and ``text_bg_rgb`` are forwarded to
        ``compose_side_by_side`` and let the caller print custom text
        (e.g. ink + paper Lab + coverage %) on a tiled panel.
        """
        try:
            from utils.comparison_image import (
                compose_swatch_layer, compose_side_by_side,
            )
        except ImportError as e:
            messagebox.showerror(
                "Missing Module",
                f"Could not load comparison composer:\n\n{e}",
            )
            return None, None
        
        try:
            if layout == "swatch_behind":
                composite = compose_swatch_layer(
                    self.current_image, avg_rgb, frame_padding=frame_padding,
                )
                suffix = "_swatch_behind"
            else:
                composite = compose_side_by_side(
                    self.current_image,
                    avg_rgb,
                    avg_lab=avg_lab,
                    include_values=include_values,
                    text_block=text_block,
                    text_bg_rgb=text_bg_rgb,
                )
                suffix = "_side_by_side"
        except Exception as e:
            messagebox.showerror(
                "Composition Failed",
                f"Could not build the comparison image:\n\n{e}",
            )
            return None, None
        
        return composite, suffix
    
    def _save_composite_to_disk(self, composite, suffix):
        """Prompt for a save location and write ``composite`` there."""
        default_dir = None
        suggested_name = "comparison"
        if getattr(self, 'current_file_path', None):
            default_dir = os.path.dirname(self.current_file_path)
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            suggested_name = f"{base}{suffix}"
        
        from tkinter import filedialog
        filetypes = [
            ("PNG (lossless, recommended)", "*.png"),
            ("TIFF", "*.tif *.tiff"),
            ("All files", "*.*"),
        ]
        filepath = filedialog.asksaveasfilename(
            title="Save Comparison Image",
            defaultextension=".png",
            initialfile=f"{suggested_name}.png",
            initialdir=default_dir,
            filetypes=filetypes,
        )
        if not filepath:
            return False
        
        try:
            # PIL picks format from extension; composite is RGB so PNG/TIFF
            # both save without further conversion.
            #
            # Embed an sRGB ICC profile so colour-managed viewers (macOS
            # Preview, browsers, Photoshop) interpret the bytes the same
            # way Windows users do — without this tag, macOS will assume
            # the display's profile and shift the colours.
            from utils.icc_profiles import get_save_icc_profile
            save_kwargs = {}
            icc_bytes = get_save_icc_profile(composite)
            if icc_bytes:
                save_kwargs["icc_profile"] = icc_bytes
            composite.save(filepath, **save_kwargs)
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save image:\n\n{e}")
            return False
        
        messagebox.showinfo(
            "Saved",
            f"Comparison image saved:\n\n{os.path.basename(filepath)}",
        )
        return True
    
    def _show_comparison_preview(
        self, composite, avg_rgb, avg_lab, suggested_suffix, layout,
    ):
        """Open a Toplevel window showing ``composite`` with Save / Close buttons.
        
        The image is down-scaled to fit the current screen when larger;
        the original full-resolution copy is preserved so Save always
        writes the un-shrunk version.
        """
        from PIL import ImageTk
        
        viewer = tk.Toplevel(self)
        layout_label = (
            "Swatch behind stamp" if layout == "swatch_behind"
            else "Side-by-side panel"
        )
        viewer.title(f"Comparison Preview — {layout_label}")
        
        # Size the viewer to roughly fit the screen, leaving room for the
        # Dock / menu bar and the button strip below the image.
        try:
            screen_w = viewer.winfo_screenwidth()
            screen_h = viewer.winfo_screenheight()
        except Exception:
            screen_w, screen_h = 1600, 1000
        max_img_w = int(screen_w * 0.8)
        max_img_h = int(screen_h * 0.75)
        
        img_w, img_h = composite.size
        scale = min(1.0, max_img_w / img_w, max_img_h / img_h)
        if scale < 1.0:
            preview_img = composite.resize(
                (max(1, int(img_w * scale)), max(1, int(img_h * scale))),
                Image.LANCZOS,
            )
        else:
            preview_img = composite
        
        # Layout: image on top, info strip + buttons on the bottom.
        image_frame = ttk.Frame(viewer, padding=8)
        image_frame.pack(fill=tk.BOTH, expand=True)
        
        photo = ImageTk.PhotoImage(preview_img)
        label = ttk.Label(image_frame, image=photo, anchor="center")
        # Keep a reference; Tk will garbage-collect the image otherwise.
        label.image = photo
        label.pack(fill=tk.BOTH, expand=True)
        
        info_bar = ttk.Frame(viewer, padding=(12, 0, 12, 6))
        info_bar.pack(fill=tk.X)
        info_text = (
            f"Avg RGB  ({int(round(avg_rgb[0]))}, "
            f"{int(round(avg_rgb[1]))}, {int(round(avg_rgb[2]))})"
        )
        if avg_lab:
            info_text += (
                f"     L*a*b*  ({avg_lab[0]:.1f}, "
                f"{avg_lab[1]:.1f}, {avg_lab[2]:.1f})"
            )
        if scale < 1.0:
            info_text += f"     (displayed at {int(scale * 100)}% of full size)"
        ttk.Label(info_bar, text=info_text, font=("Arial", 10)).pack(
            side=tk.LEFT
        )
        
        button_bar = ttk.Frame(viewer, padding=(12, 0, 12, 10))
        button_bar.pack(fill=tk.X)
        
        def on_save():
            # Save the full-resolution composite, not the shrunk preview.
            if self._save_composite_to_disk(composite, suggested_suffix):
                viewer.destroy()
        
        ttk.Button(button_bar, text="Close", command=viewer.destroy).pack(
            side=tk.RIGHT
        )
        ttk.Button(button_bar, text="Save…", command=on_save).pack(
            side=tk.RIGHT, padx=(0, 6)
        )
        
        # Center the viewer on the parent's current monitor.
        viewer.update_idletasks()
        try:
            parent_window = self.winfo_toplevel()
            px = parent_window.winfo_x()
            py = parent_window.winfo_y()
            pw = parent_window.winfo_width()
            ph = parent_window.winfo_height()
            vw = viewer.winfo_width()
            vh = viewer.winfo_height()
            x = px + max(0, (pw - vw) // 2)
            y = py + max(0, (ph - vh) // 2)
            viewer.geometry(f"+{x}+{y}")
        except Exception:
            pass
    
    def _add_color_to_library(self, rgb_values, lab_values):
        """Handle adding the current average color to a library."""
        if not rgb_values or not lab_values:
            messagebox.showerror("Error", "No color data available to add")
            return
            
        # Create a dialog for color name and library selection
        dialog = tk.Toplevel(self)
        dialog.title("Add Color to Library")
        # Note: Not using transient() to allow free movement across monitors on macOS
        
        # On macOS, set window attributes to prevent disappearing when moved
        import sys
        if sys.platform == 'darwin':
            try:
                dialog.attributes('-topmost', False)
                dialog.lift()
                dialog.attributes('-topmost', False)
            except:
                pass
        
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
        
        # Auto-populate notes with current image filename if available
        if hasattr(self, 'current_file_path') and self.current_file_path:
            filename = os.path.basename(self.current_file_path)
            notes_text.insert("1.0", filename)
        
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
                return []
                
            library_files = [f for f in os.listdir(library_dir) if f.endswith("_library.db")]
            library_names = [f[:-11] for f in library_files]  # Remove '_library.db' suffix
                
            return sorted(library_names)
        except Exception as e:
            print(f"Error getting libraries: {e}")
            return []
    
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
    
    def _save_one_group_to_db(
        self, samples, db_name, image_name,
        save_individual, save_average, use_averages_suffix,
        notes_label="Results Manager",
    ):
        """Save one sample group (ink or paper) into ``db_name`` as ``image_name``.
        
        Mirrors the per-set save logic that previously lived inline in
        ``_perform_quick_save`` and the Save Results dialog. Both ink
        and paper groups go through this helper; paper just uses an
        ``image_name`` suffixed with ``-p`` so the two sets stay tied
        to the same stamp inside one DB but never mix in plots.
        
        Returns:
            dict with keys 'success_individual', 'success_average',
            'saved_files', 'measurements_count'.
        """
        from utils.color_analyzer import ColorAnalyzer
        from utils.color_analysis_db import ColorAnalysisDB
        
        analyzer = ColorAnalyzer()
        
        sample_measurements = []
        for i, sample in enumerate(samples, 1):
            sample_rgb = sample['rgb']
            sample_lab = (
                self.library.rgb_to_lab(sample_rgb)
                if hasattr(self, 'library') and self.library
                else analyzer.rgb_to_lab(sample_rgb)
            )
            rgb_stddev = sample.get('rgb_stddev', None)
            lab_stddev = sample.get('lab_stddev', None)
            sample_measurements.append({
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
                'anchor': sample['anchor'],
                'rgb_r_stddev': rgb_stddev[0] if rgb_stddev else None,
                'rgb_g_stddev': rgb_stddev[1] if rgb_stddev else None,
                'rgb_b_stddev': rgb_stddev[2] if rgb_stddev else None,
                'lab_l_stddev': lab_stddev[0] if lab_stddev else None,
                'lab_a_stddev': lab_stddev[1] if lab_stddev else None,
                'lab_b_stddev': lab_stddev[2] if lab_stddev else None,
            })
        
        success_individual = True
        success_average = True
        saved_files = []
        
        if save_individual:
            individual_db = ColorAnalysisDB(db_name)
            set_id = individual_db.create_measurement_set(
                image_name, f"Individual samples from {image_name}",
            )
            success_individual = False
            if set_id:
                success_individual = True
                for m in sample_measurements:
                    size_str = f"{m['sample_width']}x{m['sample_height']}"
                    saved = individual_db.save_color_measurement(
                        set_id=set_id,
                        coordinate_point=int(m['id'].replace('sample_', '')),
                        x_pos=m['x_position'], y_pos=m['y_position'],
                        l_value=m['l_value'], a_value=m['a_value'], b_value=m['b_value'],
                        rgb_r=m['rgb_r'], rgb_g=m['rgb_g'], rgb_b=m['rgb_b'],
                        sample_type=m['sample_type'], sample_size=size_str,
                        sample_anchor=m['anchor'],
                        notes=f"Sample from {notes_label}",
                        rgb_r_stddev=m.get('rgb_r_stddev'),
                        rgb_g_stddev=m.get('rgb_g_stddev'),
                        rgb_b_stddev=m.get('rgb_b_stddev'),
                        lab_l_stddev=m.get('lab_l_stddev'),
                        lab_a_stddev=m.get('lab_a_stddev'),
                        lab_b_stddev=m.get('lab_b_stddev'),
                    )
                    if not saved:
                        success_individual = False
                        break
                if success_individual:
                    saved_files.append(f"{db_name}.db")
        
        if save_average and sample_measurements:
            avg_db_name = f"{db_name}_AVG" if use_averages_suffix else db_name
            ok = analyzer.save_averaged_measurement_from_samples(
                sample_measurements=sample_measurements,
                sample_set_name=avg_db_name,
                image_name=image_name,
                notes=f"Average from {len(samples)} samples via {notes_label}",
            )
            success_average = bool(ok)
            if success_average and use_averages_suffix:
                saved_files.append(f"{avg_db_name}.db")
        
        return {
            'success_individual': success_individual,
            'success_average': success_average,
            'saved_files': saved_files,
            'measurements_count': len(sample_measurements),
        }
    
    def _enabled_paper_samples(self):
        """Return the list of enabled paper-tagged samples (may be empty)."""
        return [s for s in self.sample_points
                if s['enabled'].get() and s['is_paper'].get()]
    
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
        """Quick save using preference settings without showing a dialog.
        
        Saves the ink samples to ``<final_db_name>``/``<image_name>``, and
        if any paper samples are enabled, saves them to the same DB under
        ``<image_name>-p`` so they stay associated with the stamp but
        never mix into ink plots.
        """
        try:
            from utils.user_preferences import get_preferences_manager
            from utils.dismissible_message import showsuccess_dismissible
            
            prefs = get_preferences_manager()
            
            # Get preferences
            default_db_name = prefs.get_default_database_name()
            save_individual = prefs.get_save_individual_default()
            save_average = prefs.get_save_average_default()
            use_averages_suffix = prefs.get_use_averages_suffix()
            
            # Resolve DB name + image name from current file
            if hasattr(self, 'current_file_path'):
                filename = os.path.basename(self.current_file_path)
                file_base = os.path.splitext(filename)[0]
                if default_db_name in ["ColorAnalysis", "Results_Analysis"]:
                    final_db_name = f"Results_{file_base}"
                else:
                    final_db_name = default_db_name
                image_name = file_base
            else:
                final_db_name = default_db_name
                image_name = "analysis_result"
            
            # --- ink (primary) save ----------------------------------------- #
            ink_result = self._save_one_group_to_db(
                samples=enabled_samples,
                db_name=final_db_name,
                image_name=image_name,
                save_individual=save_individual,
                save_average=save_average,
                use_averages_suffix=use_averages_suffix,
                notes_label="Results Manager (Quick Save)",
            )
            
            # --- paper (optional) save -------------------------------------- #
            paper_samples = self._enabled_paper_samples()
            paper_result = None
            if paper_samples:
                paper_result = self._save_one_group_to_db(
                    samples=paper_samples,
                    db_name=final_db_name,
                    image_name=f"{image_name}-p",
                    save_individual=save_individual,
                    save_average=save_average,
                    use_averages_suffix=use_averages_suffix,
                    notes_label="Results Manager (Quick Save) [paper]",
                )
            
            # --- evaluate combined success/error and report ----------------- #
            ok_ink = ((not save_individual or ink_result['success_individual'])
                      and (not save_average or ink_result['success_average']))
            ok_paper = (
                paper_result is None or (
                    (not save_individual or paper_result['success_individual'])
                    and (not save_average or paper_result['success_average'])
                )
            )
            
            if ok_ink and ok_paper:
                prefs.set('last_used_database', final_db_name)
                
                success_msg = "Results saved successfully!\n\n"
                if save_individual:
                    success_msg += (
                        f"✓ {ink_result['measurements_count']} ink samples saved\n"
                    )
                    if paper_result:
                        success_msg += (
                            f"✓ {paper_result['measurements_count']} "
                            f"paper samples saved (set '{image_name}-p')\n"
                        )
                if save_average:
                    success_msg += "✓ 1 averaged ink result saved\n"
                    if paper_result:
                        success_msg += "✓ 1 averaged paper result saved\n"
                # De-dup file list (preserve order)
                saved_files = list(dict.fromkeys(
                    ink_result['saved_files']
                    + (paper_result['saved_files'] if paper_result else [])
                ))
                success_msg += "\nSaved to:\n"
                for f in saved_files:
                    success_msg += f"• {f}\n"
                
                showsuccess_dismissible(
                    title="Quick Save Complete",
                    message=success_msg,
                    message_id="quick_save_success",
                    parent=self.winfo_toplevel(),
                )
            else:
                error_msg = "Some save operations failed:\n\n"
                if save_individual and not ink_result['success_individual']:
                    error_msg += "✗ Ink individual samples failed to save\n"
                if save_average and not ink_result['success_average']:
                    error_msg += "✗ Ink average failed to save\n"
                if paper_result and save_individual and not paper_result['success_individual']:
                    error_msg += "✗ Paper individual samples failed to save\n"
                if paper_result and save_average and not paper_result['success_average']:
                    error_msg += "✗ Paper average failed to save\n"
                messagebox.showerror("Quick Save Error", error_msg)
        
        except Exception as e:
            messagebox.showerror("Error", f"Quick save failed: {str(e)}")
    
    def _show_save_results_dialog(self, avg_rgb, avg_lab, enabled_samples):
        """Show dialog to save results to database."""
        try:
            # Create dialog
            dialog = tk.Toplevel(self)
            dialog.title("Save Results")
            # Note: Not using transient() to allow free movement across monitors on macOS
            
            # On macOS, set window attributes to prevent disappearing when moved
            import sys
            if sys.platform == 'darwin':
                try:
                    dialog.attributes('-topmost', False)
                    dialog.lift()
                    dialog.attributes('-topmost', False)
                except:
                    pass
            
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
                if db_choice.get() == "existing" and existing_databases:
                    final_db_name = db_var.get().strip()
                else:
                    final_db_name = new_db_var.get().strip()
                
                if not final_db_name:
                    messagebox.showerror(
                        "Error", "Please select or enter a database name")
                    return
                
                # Image (= measurement-set) name from the current file
                image_name = "analysis_result"
                if hasattr(self, 'current_file_path'):
                    image_name = os.path.splitext(
                        os.path.basename(self.current_file_path))[0]
                
                try:
                    try:
                        from utils.user_preferences import get_preferences_manager
                        use_averages_suffix = (
                            get_preferences_manager().get_use_averages_suffix()
                        )
                    except Exception:
                        use_averages_suffix = True
                    
                    # --- ink save (existing behaviour) ---------------------- #
                    ink_result = self._save_one_group_to_db(
                        samples=enabled_samples,
                        db_name=final_db_name,
                        image_name=image_name,
                        save_individual=save_individual.get(),
                        save_average=save_average.get(),
                        use_averages_suffix=use_averages_suffix,
                    )
                    
                    # --- paper save (if any paper samples are enabled) ------ #
                    paper_samples = self._enabled_paper_samples()
                    paper_result = None
                    if paper_samples:
                        paper_result = self._save_one_group_to_db(
                            samples=paper_samples,
                            db_name=final_db_name,
                            image_name=f"{image_name}-p",
                            save_individual=save_individual.get(),
                            save_average=save_average.get(),
                            use_averages_suffix=use_averages_suffix,
                            notes_label="Results Manager [paper]",
                        )
                    
                    ok_ink = (
                        (not save_individual.get() or ink_result['success_individual'])
                        and (not save_average.get() or ink_result['success_average'])
                    )
                    ok_paper = (
                        paper_result is None or (
                            (not save_individual.get() or paper_result['success_individual'])
                            and (not save_average.get() or paper_result['success_average'])
                        )
                    )
                    
                    saved_files = list(dict.fromkeys(
                        ink_result['saved_files']
                        + (paper_result['saved_files'] if paper_result else [])
                    ))
                    
                    if ok_ink and ok_paper and saved_files:
                        try:
                            from utils.user_preferences import get_preferences_manager
                            get_preferences_manager().set(
                                'last_used_database', final_db_name)
                        except Exception as e:
                            print(f"Warning: Could not save last_used_database preference: {e}")
                        
                        success_msg = "Results saved successfully!\n\n"
                        if save_individual.get():
                            success_msg += (
                                f"✓ {ink_result['measurements_count']} ink samples saved\n"
                            )
                            if paper_result:
                                success_msg += (
                                    f"✓ {paper_result['measurements_count']} "
                                    f"paper samples saved (set '{image_name}-p')\n"
                                )
                        if save_average.get():
                            success_msg += "✓ 1 averaged ink result saved\n"
                            if paper_result:
                                success_msg += "✓ 1 averaged paper result saved\n"
                        success_msg += "\nSaved to:\n"
                        for f in saved_files:
                            success_msg += f"• {f}\n"
                        
                        messagebox.showinfo("Success", success_msg)
                        dialog.destroy()
                    else:
                        error_msg = "Some save operations failed:\n\n"
                        if save_individual.get() and not ink_result['success_individual']:
                            error_msg += "✗ Ink individual samples failed to save\n"
                        if save_average.get() and not ink_result['success_average']:
                            error_msg += "✗ Ink average failed to save\n"
                        if paper_result and save_individual.get() and not paper_result['success_individual']:
                            error_msg += "✗ Paper individual samples failed to save\n"
                        if paper_result and save_average.get() and not paper_result['success_average']:
                            error_msg += "✗ Paper average failed to save\n"
                        if saved_files:
                            error_msg += "\nPartially saved to:\n"
                            for f in saved_files:
                                error_msg += f"• {f}\n"
                        messagebox.showerror("Save Error", error_msg)
                        
                except Exception as e:
                    messagebox.showerror(
                        "Error", f"Failed to save results: {str(e)}")
            
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
                
                # Get stddev values if available
                rgb_stddev = sample.get('rgb_stddev', None)
                lab_stddev = sample.get('lab_stddev', None)
                
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
                    'anchor': sample['anchor'],
                    'rgb_r_stddev': rgb_stddev[0] if rgb_stddev else None,
                    'rgb_g_stddev': rgb_stddev[1] if rgb_stddev else None,
                    'rgb_b_stddev': rgb_stddev[2] if rgb_stddev else None,
                    'lab_l_stddev': lab_stddev[0] if lab_stddev else None,
                    'lab_a_stddev': lab_stddev[1] if lab_stddev else None,
                    'lab_b_stddev': lab_stddev[2] if lab_stddev else None
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
