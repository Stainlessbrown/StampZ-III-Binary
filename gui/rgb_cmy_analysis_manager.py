#!/usr/bin/env python3
"""
RGB-CMY Channel Analysis Manager

GUI integration for RGB-CMY channel mask analysis functionality.
Integrates with existing StampZ workflow and mask generation systems.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.rgb_cmy_analyzer import RGBCMYAnalyzer
from utils.mask_generator import create_shape_mask, create_polygon_mask, MaskColor
from utils.geometry import Point
from utils.rounded_shapes import Circle, Oval
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


class MaskCreationDialog:
    """Dialog for creating masks interactively."""
    
    def __init__(self, parent, image, shape_type):
        self.parent = parent
        self.image = image
        self.shape_type = shape_type
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Create {shape_type.title()} Mask")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (300 // 2)
        self.dialog.geometry(f"400x300+{x}+{y}")
        
        self.create_dialog_content()
    
    def create_dialog_content(self):
        """Create dialog content."""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.grid(row=0, column=0, sticky='nsew')
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)
        
        # Instructions
        ttk.Label(main_frame, text=f"Create {self.shape_type} mask for RGB-CMY analysis", 
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        ttk.Label(main_frame, text=f"Image size: {self.image.size[0]} x {self.image.size[1]} pixels").grid(
            row=1, column=0, columnspan=2, pady=5)
        
        # Mask name
        ttk.Label(main_frame, text="Mask Name:").grid(row=2, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar(value=f"{self.shape_type}_mask")
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=2, column=1, sticky='ew', pady=5)
        
        # Shape parameters
        if self.shape_type == "rectangle":
            self.create_rectangle_controls(main_frame, 3)
        elif self.shape_type == "circle":
            self.create_circle_controls(main_frame, 3)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=10, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Create Mask", command=self.create_mask).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).grid(row=0, column=1, padx=5)
        
        # Configure grid weights
        main_frame.grid_columnconfigure(1, weight=1)
    
    def create_rectangle_controls(self, parent, start_row):
        """Create controls for rectangle mask."""
        ttk.Label(parent, text="Rectangle Parameters:", font=('Arial', 10, 'bold')).grid(
            row=start_row, column=0, columnspan=2, sticky='w', pady=(10, 5))
        
        # Position
        ttk.Label(parent, text="X (left):").grid(row=start_row+1, column=0, sticky='w', pady=2)
        self.x_var = tk.IntVar(value=100)
        ttk.Spinbox(parent, from_=0, to=self.image.size[0]-1, textvariable=self.x_var, width=10).grid(
            row=start_row+1, column=1, sticky='w', pady=2)
        
        ttk.Label(parent, text="Y (top):").grid(row=start_row+2, column=0, sticky='w', pady=2)
        self.y_var = tk.IntVar(value=100)
        ttk.Spinbox(parent, from_=0, to=self.image.size[1]-1, textvariable=self.y_var, width=10).grid(
            row=start_row+2, column=1, sticky='w', pady=2)
        
        # Size
        ttk.Label(parent, text="Width:").grid(row=start_row+3, column=0, sticky='w', pady=2)
        self.width_var = tk.IntVar(value=200)
        ttk.Spinbox(parent, from_=10, to=self.image.size[0], textvariable=self.width_var, width=10).grid(
            row=start_row+3, column=1, sticky='w', pady=2)
        
        ttk.Label(parent, text="Height:").grid(row=start_row+4, column=0, sticky='w', pady=2)
        self.height_var = tk.IntVar(value=200)
        ttk.Spinbox(parent, from_=10, to=self.image.size[1], textvariable=self.height_var, width=10).grid(
            row=start_row+4, column=1, sticky='w', pady=2)
    
    def create_circle_controls(self, parent, start_row):
        """Create controls for circle mask."""
        ttk.Label(parent, text="Circle Parameters:", font=('Arial', 10, 'bold')).grid(
            row=start_row, column=0, columnspan=2, sticky='w', pady=(10, 5))
        
        # Center
        ttk.Label(parent, text="Center X:").grid(row=start_row+1, column=0, sticky='w', pady=2)
        self.cx_var = tk.IntVar(value=self.image.size[0]//2)
        ttk.Spinbox(parent, from_=0, to=self.image.size[0]-1, textvariable=self.cx_var, width=10).grid(
            row=start_row+1, column=1, sticky='w', pady=2)
        
        ttk.Label(parent, text="Center Y:").grid(row=start_row+2, column=0, sticky='w', pady=2)
        self.cy_var = tk.IntVar(value=self.image.size[1]//2)
        ttk.Spinbox(parent, from_=0, to=self.image.size[1]-1, textvariable=self.cy_var, width=10).grid(
            row=start_row+2, column=1, sticky='w', pady=2)
        
        # Radius
        ttk.Label(parent, text="Radius:").grid(row=start_row+3, column=0, sticky='w', pady=2)
        self.radius_var = tk.IntVar(value=100)
        max_radius = min(self.image.size[0], self.image.size[1]) // 2
        ttk.Spinbox(parent, from_=10, to=max_radius, textvariable=self.radius_var, width=10).grid(
            row=start_row+3, column=1, sticky='w', pady=2)
    
    def create_mask(self):
        """Create the mask based on current parameters."""
        try:
            mask_name = self.name_var.get().strip()
            if not mask_name:
                messagebox.showerror("Error", "Please enter a mask name.")
                return
            
            # Create mask based on shape type
            if self.shape_type == "rectangle":
                mask = self.create_rectangle_mask_image()
            elif self.shape_type == "circle":
                mask = self.create_circle_mask_image()
            else:
                raise ValueError(f"Unknown shape type: {self.shape_type}")
            
            self.result = (mask_name, mask)
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create mask: {str(e)}")
    
    def create_rectangle_mask_image(self):
        """Create rectangular mask image."""
        from PIL import ImageDraw
        
        # Get parameters
        x = self.x_var.get()
        y = self.y_var.get()
        width = self.width_var.get()
        height = self.height_var.get()
        
        # Validate bounds
        if x + width > self.image.size[0]:
            width = self.image.size[0] - x
        if y + height > self.image.size[1]:
            height = self.image.size[1] - y
        
        # Create mask
        mask = Image.new('L', self.image.size, 0)  # Black background
        draw = ImageDraw.Draw(mask)
        draw.rectangle([x, y, x + width, y + height], fill=255)  # White rectangle
        
        return mask
    
    def create_circle_mask_image(self):
        """Create circular mask image."""
        from PIL import ImageDraw
        
        # Get parameters
        cx = self.cx_var.get()
        cy = self.cy_var.get()
        radius = self.radius_var.get()
        
        # Create mask
        mask = Image.new('L', self.image.size, 0)  # Black background
        draw = ImageDraw.Draw(mask)
        
        # Draw circle
        left = cx - radius
        top = cy - radius
        right = cx + radius
        bottom = cy + radius
        
        draw.ellipse([left, top, right, bottom], fill=255)  # White circle
        
        return mask
    
    def cancel(self):
        """Cancel dialog."""
        self.result = None
        self.dialog.destroy()


class RGBCMYAnalysisManager:
    """Manages RGB-CMY channel analysis with GUI interface."""
    
    def __init__(self, parent_frame, image_manager=None):
        self.parent_frame = parent_frame
        self.image_manager = image_manager
        self.analyzer = RGBCMYAnalyzer()
        self.current_image_path = None
        self.masks = {}
        self.results = []
        
        # Template paths
        self.template_paths = {
            'xlsx': "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.xlsx",
            'ods': "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.ods"
        }
        
        self.create_interface()
    
    def create_interface(self):
        """Create the RGB-CMY analysis interface."""
        # Main frame
        self.main_frame = ttk.LabelFrame(self.parent_frame, text="RGB-CMY Channel Analysis", padding=10)
        self.main_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        # Configure grid weights
        self.parent_frame.grid_rowconfigure(0, weight=1)
        self.parent_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        
        # Image selection
        ttk.Label(self.main_frame, text="Source Image:").grid(row=0, column=0, sticky='w', pady=2)
        self.image_path_var = tk.StringVar(value="No image selected")
        ttk.Label(self.main_frame, textvariable=self.image_path_var, width=50).grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Button(self.main_frame, text="Browse", command=self.browse_image).grid(row=0, column=2, padx=(5, 0), pady=2)
        
        # Metadata section
        metadata_frame = ttk.LabelFrame(self.main_frame, text="Analysis Metadata", padding=5)
        metadata_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=10)
        metadata_frame.grid_columnconfigure(1, weight=1)
        
        # Metadata fields
        self.metadata_vars = {}
        fields = [
            ('Date Measured:', 'date_measured', datetime.now().strftime('%m/%d/%Y')),
            ('Plate:', 'plate', ''),
            ('Die:', 'die', ''),
            ('Date Registered:', 'date_registered', datetime.now().strftime('%m/%d/%Y')),
            ('Described Colour:', 'described_colour', '')
        ]
        
        for i, (label, key, default) in enumerate(fields):
            ttk.Label(metadata_frame, text=label).grid(row=i, column=0, sticky='w', pady=2)
            var = tk.StringVar(value=default)
            self.metadata_vars[key] = var
            ttk.Entry(metadata_frame, textvariable=var, width=40).grid(row=i, column=1, sticky='ew', padx=(5, 0), pady=2)
        
        # Mask management section
        mask_frame = ttk.LabelFrame(self.main_frame, text="Sample Masks", padding=5)
        mask_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)
        mask_frame.grid_columnconfigure(0, weight=1)
        
        # Mask list
        self.mask_listbox = tk.Listbox(mask_frame, height=6)
        self.mask_listbox.grid(row=0, column=0, columnspan=3, sticky='ew', pady=2)
        
        # Mask buttons
        mask_buttons_frame = ttk.Frame(mask_frame)
        mask_buttons_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=5)
        
        ttk.Button(mask_buttons_frame, text="📁 Load Mask", command=self.add_mask).grid(row=0, column=0, padx=2)
        ttk.Button(mask_buttons_frame, text="🔲 Create Rectangle", command=self.create_rectangle_mask).grid(row=0, column=1, padx=2)
        ttk.Button(mask_buttons_frame, text="⭕ Create Circle", command=self.create_circle_mask).grid(row=0, column=2, padx=2)
        ttk.Button(mask_buttons_frame, text="🗑️ Remove", command=self.remove_mask).grid(row=0, column=3, padx=2)
        ttk.Button(mask_buttons_frame, text="🔄 Clear All", command=self.clear_masks).grid(row=0, column=4, padx=2)
        
        # Analysis section
        analysis_frame = ttk.LabelFrame(self.main_frame, text="Analysis", padding=5)
        analysis_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=10)
        
        ttk.Button(analysis_frame, text="🔬 Run RGB-CMY Analysis", command=self.run_analysis).grid(row=0, column=0, pady=5)
        ttk.Button(analysis_frame, text="💾 Save Masks", command=self.save_masks).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(analysis_frame, text="📤 Export Results", command=self.export_results).grid(row=0, column=2, pady=5)
        
        # Results display
        results_frame = ttk.LabelFrame(self.main_frame, text="Results", padding=5)
        results_frame.grid(row=4, column=0, columnspan=3, sticky='ew', pady=10)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Results text area with scrollbar
        text_frame = ttk.Frame(results_frame)
        text_frame.grid(row=0, column=0, sticky='ew')
        text_frame.grid_columnconfigure(0, weight=1)
        
        self.results_text = tk.Text(text_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.grid(row=0, column=0, sticky='ew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready for RGB-CMY analysis")
        status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=5, column=0, columnspan=3, sticky='ew', pady=5)
    
    def browse_image(self):
        """Browse for source image."""
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select Source Image",
            filetypes=filetypes
        )
        
        if filename:
            self.current_image_path = filename
            self.image_path_var.set(os.path.basename(filename))
            self.analyzer.load_image(filename)
            self.status_var.set(f"Loaded image: {os.path.basename(filename)}")
            logger.info(f"Loaded source image: {filename}")
    
    def add_mask(self):
        """Add a mask file for analysis."""
        if not self.current_image_path:
            messagebox.showwarning("No Image", "Please select a source image first.")
            return
        
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select Mask Image",
            filetypes=filetypes
        )
        
        if filename:
            try:
                # Load and validate mask
                mask_image = Image.open(filename)
                mask_name = os.path.splitext(os.path.basename(filename))[0]
                
                # Check if we already have this mask
                if mask_name in self.masks:
                    response = messagebox.askyesno(
                        "Duplicate Mask",
                        f"Mask '{mask_name}' already exists. Replace it?"
                    )
                    if not response:
                        return
                
                self.masks[mask_name] = mask_image
                self.update_mask_list()
                self.status_var.set(f"Added mask: {mask_name}")
                logger.info(f"Added mask: {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load mask: {str(e)}")
                logger.error(f"Error loading mask {filename}: {e}")
    
    def remove_mask(self):
        """Remove selected mask."""
        selection = self.mask_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a mask to remove.")
            return
        
        mask_name = self.mask_listbox.get(selection[0])
        if mask_name in self.masks:
            del self.masks[mask_name]
            self.update_mask_list()
            self.status_var.set(f"Removed mask: {mask_name}")
    
    def clear_masks(self):
        """Clear all masks."""
        if self.masks:
            response = messagebox.askyesno(
                "Clear Masks",
                f"Remove all {len(self.masks)} masks?"
            )
            if response:
                self.masks.clear()
                self.update_mask_list()
                self.status_var.set("Cleared all masks")
    
    def create_rectangle_mask(self):
        """Create a rectangular mask interactively."""
        if not self.current_image_path:
            messagebox.showwarning("No Image", "Please select a source image first.")
            return
            
        self._create_interactive_mask("rectangle")
    
    def create_circle_mask(self):
        """Create a circular mask interactively."""
        if not self.current_image_path:
            messagebox.showwarning("No Image", "Please select a source image first.")
            return
            
        self._create_interactive_mask("circle")
    
    def _create_interactive_mask(self, shape_type):
        """Create mask using interactive dialog."""
        try:
            # Load image for preview
            source_image = Image.open(self.current_image_path)
            
            # Create mask creation dialog
            dialog = MaskCreationDialog(self.main_frame, source_image, shape_type)
            self.main_frame.wait_window(dialog.dialog)
            
            if dialog.result:
                mask_name, mask_image = dialog.result
                
                # Check for duplicate name
                counter = 1
                original_name = mask_name
                while mask_name in self.masks:
                    mask_name = f"{original_name}_{counter:02d}"
                    counter += 1
                
                self.masks[mask_name] = mask_image
                self.update_mask_list()
                self.status_var.set(f"Created mask: {mask_name}")
                logger.info(f"Created {shape_type} mask: {mask_name}")
                
        except Exception as e:
            messagebox.showerror("Mask Creation Error", f"Failed to create mask: {str(e)}")
            logger.error(f"Error creating {shape_type} mask: {e}")
    
    def update_mask_list(self):
        """Update the mask listbox."""
        self.mask_listbox.delete(0, tk.END)
        for mask_name in sorted(self.masks.keys()):
            self.mask_listbox.insert(tk.END, mask_name)
    
    def run_analysis(self):
        """Run RGB-CMY channel analysis."""
        if not self.current_image_path:
            messagebox.showerror("No Image", "Please select a source image first.")
            return
        
        if not self.masks:
            messagebox.showerror("No Masks", "Please add at least one mask for analysis.")
            return
        
        try:
            self.status_var.set("Running RGB-CMY analysis...")
            
            # Set metadata
            metadata = {key: var.get() for key, var in self.metadata_vars.items()}
            if self.current_image_path:
                img = Image.open(self.current_image_path)
                metadata['total_pixels'] = str(img.size[0] * img.size[1])
            self.analyzer.set_metadata(metadata)
            
            # Run analysis
            self.results = self.analyzer.analyze_multiple_masks(self.masks)
            
            # Display results
            self.display_results()
            
            self.status_var.set(f"Analysis complete: {len(self.results)} samples analyzed")
            
        except Exception as e:
            messagebox.showerror("Analysis Error", f"Failed to run analysis: {str(e)}")
            logger.error(f"Analysis error: {e}")
            self.status_var.set("Analysis failed")
    
    def display_results(self):
        """Display analysis results in the text widget."""
        self.results_text.delete(1.0, tk.END)
        
        if not self.results:
            self.results_text.insert(tk.END, "No results available. Run analysis first.")
            return
        
        # Header
        self.results_text.insert(tk.END, "RGB-CMY Channel Analysis Results\\n")
        self.results_text.insert(tk.END, "=" * 60 + "\\n\\n")
        
        # Table header
        header = f"{'Sample':<15} {'Pixels':<8} {'R':<6} {'G':<6} {'B':<6} {'C':<6} {'Y':<6} {'M':<6}\\n"
        self.results_text.insert(tk.END, header)
        self.results_text.insert(tk.END, "-" * len(header) + "\\n")
        
        # Results
        for result in self.results:
            line = (f"{result['sample_name']:<15} "
                   f"{result['pixel_count']:<8} "
                   f"{result['R_mean']:<6.1f} "
                   f"{result['G_mean']:<6.1f} "
                   f"{result['B_mean']:<6.1f} "
                   f"{result['C_mean']:<6.1f} "
                   f"{result['Y_mean']:<6.1f} "
                   f"{result['M_mean']:<6.1f}\\n")
            self.results_text.insert(tk.END, line)
        
        # Statistics
        if len(self.results) > 1:
            self.results_text.insert(tk.END, "\\n" + "=" * 60 + "\\n")
            self.results_text.insert(tk.END, "Summary Statistics:\\n\\n")
            
            import numpy as np
            
            avg_r = np.mean([r['R_mean'] for r in self.results])
            avg_g = np.mean([r['G_mean'] for r in self.results])
            avg_b = np.mean([r['B_mean'] for r in self.results])
            avg_c = np.mean([r['C_mean'] for r in self.results])
            avg_y = np.mean([r['Y_mean'] for r in self.results])
            avg_m = np.mean([r['M_mean'] for r in self.results])
            
            self.results_text.insert(tk.END, f"RGB Averages: R={avg_r:.1f}, G={avg_g:.1f}, B={avg_b:.1f}\\n")
            self.results_text.insert(tk.END, f"CMY Averages: C={avg_c:.1f}, Y={avg_y:.1f}, M={avg_m:.1f}\\n")
    
    def save_masks(self):
        """Save individual mask files."""
        if not self.masks:
            messagebox.showwarning("No Masks", "No masks to save.")
            return
        
        directory = filedialog.askdirectory(title="Select Directory to Save Masks")
        if not directory:
            return
        
        try:
            saved_files = self.analyzer.save_masks(directory, "rgbcmy_mask")
            messagebox.showinfo(
                "Masks Saved",
                f"Saved {len(saved_files)} mask files to:\\n{directory}"
            )
            self.status_var.set(f"Saved {len(saved_files)} masks")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save masks: {str(e)}")
            logger.error(f"Error saving masks: {e}")
    
    def export_results(self):
        """Export analysis results to template."""
        if not self.results:
            messagebox.showwarning("No Results", "Run analysis first.")
            return
        
        # Choose output file
        filetypes = [
            ("Excel files", "*.xlsx"),
            ("OpenDocument Spreadsheet", "*.ods"),
            ("CSV files", "*.csv"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.asksaveasfilename(
            title="Export Analysis Results",
            defaultextension=".xlsx",
            filetypes=filetypes
        )
        
        if not filename:
            return
        
        try:
            # Determine template to use
            ext = os.path.splitext(filename)[1].lower()
            template_path = None
            
            if ext == '.xlsx' and os.path.exists(self.template_paths['xlsx']):
                template_path = self.template_paths['xlsx']
            elif ext == '.ods' and os.path.exists(self.template_paths['ods']):
                template_path = self.template_paths['ods']
            
            if template_path:
                success = self.analyzer.export_to_template(template_path, filename)
            else:
                # Fallback to CSV export
                csv_path = filename.replace('.xlsx', '.csv').replace('.ods', '.csv')
                self.analyzer._export_to_csv(csv_path)
                success = True
                filename = csv_path
            
            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Results exported to:\\n{filename}"
                )
                self.status_var.set("Results exported successfully")
            else:
                messagebox.showerror("Export Error", "Failed to export results.")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
            logger.error(f"Export error: {e}")


def create_rgb_cmy_analysis_window():
    """Create standalone RGB-CMY analysis window for testing."""
    root = tk.Tk()
    root.title("RGB-CMY Channel Analysis")
    root.geometry("800x700")
    
    # Create main frame
    main_frame = ttk.Frame(root, padding=10)
    main_frame.grid(row=0, column=0, sticky='nsew')
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    
    # Create manager
    manager = RGBCMYAnalysisManager(main_frame)
    
    return root, manager


if __name__ == "__main__":
    # Standalone testing
    root, manager = create_rgb_cmy_analysis_window()
    root.mainloop()