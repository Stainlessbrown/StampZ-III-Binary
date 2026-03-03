#!/usr/bin/env python3
"""
Scanner Calibration Dialog for StampZ

Provides a GUI for calibrating scanners using the StampZ color target.
Allows users to load a scanned target, detect patches, compute correction,
and save/activate calibration profiles.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ScannerCalibrationDialog:
    """Dialog for scanner calibration setup."""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.calibration = None
        self.quality = None
        
        # Create window
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Scanner Calibration")
        self.root.geometry("800x700")
        self.root.minsize(700, 600)
        
        # Don't use transient on macOS to allow free movement
        if sys.platform != 'darwin' and parent:
            self.root.transient(parent)
        
        self._create_ui()
        self._update_status()
    
    def _create_ui(self):
        """Create the dialog UI."""
        # Main container
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(
            main,
            text="Scanner Calibration",
            font=("Arial", 16, "bold")
        ).pack(anchor='w', pady=(0, 5))
        
        ttk.Label(
            main,
            text="Calibrate your scanner using the StampZ color target to enable "
                 "accurate color measurements and shared color libraries.",
            font=("Arial", 10),
            foreground='gray',
            wraplength=750
        ).pack(anchor='w', pady=(0, 15))
        
        # Status frame
        self.status_frame = ttk.LabelFrame(main, text="Calibration Status", padding=10)
        self.status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(
            self.status_frame,
            text="Not calibrated",
            font=("Arial", 11, "bold"),
            foreground='#CC0000'
        )
        self.status_label.pack(anchor='w')
        
        self.profile_info_label = ttk.Label(
            self.status_frame,
            text="",
            font=("Arial", 9),
            foreground='gray'
        )
        self.profile_info_label.pack(anchor='w')
        
        # Action buttons frame
        action_frame = ttk.LabelFrame(main, text="Calibration Steps", padding=10)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Step 1: Load target scan
        step1_frame = ttk.Frame(action_frame)
        step1_frame.pack(fill=tk.X, pady=3)
        ttk.Label(step1_frame, text="1.", font=("Arial", 11, "bold"), width=3).pack(side=tk.LEFT)
        ttk.Button(
            step1_frame,
            text="Load Target Scan...",
            command=self._load_target_scan
        ).pack(side=tk.LEFT, padx=(0, 10))
        self.file_label = ttk.Label(step1_frame, text="No file loaded", foreground='gray')
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Step 2: Detect & Calibrate
        step2_frame = ttk.Frame(action_frame)
        step2_frame.pack(fill=tk.X, pady=3)
        ttk.Label(step2_frame, text="2.", font=("Arial", 11, "bold"), width=3).pack(side=tk.LEFT)
        self.calibrate_button = ttk.Button(
            step2_frame,
            text="Detect Patches & Calibrate",
            command=self._calibrate,
            state='disabled'
        )
        self.calibrate_button.pack(side=tk.LEFT, padx=(0, 10))
        self.quality_label = ttk.Label(step2_frame, text="", foreground='gray')
        self.quality_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Step 3: Save & Activate
        step3_frame = ttk.Frame(action_frame)
        step3_frame.pack(fill=tk.X, pady=3)
        ttk.Label(step3_frame, text="3.", font=("Arial", 11, "bold"), width=3).pack(side=tk.LEFT)
        self.save_button = ttk.Button(
            step3_frame,
            text="Save & Activate Profile",
            command=self._save_and_activate,
            state='disabled'
        )
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Deactivate button
        self.deactivate_button = ttk.Button(
            step3_frame,
            text="Deactivate Calibration",
            command=self._deactivate_calibration
        )
        self.deactivate_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Load existing profile
        ttk.Button(
            step3_frame,
            text="Load Existing Profile...",
            command=self._load_existing_profile
        ).pack(side=tk.LEFT)
        
        # Results frame (patch comparison grid)
        results_frame = ttk.LabelFrame(main, text="Patch Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Scrollable results area
        canvas = tk.Canvas(results_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=canvas.yview)
        self.results_inner = ttk.Frame(canvas)
        
        self.results_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.results_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Column headers
        self._create_results_header()
        
        # Bottom buttons
        bottom_frame = ttk.Frame(main)
        bottom_frame.pack(fill=tk.X)
        
        ttk.Button(
            bottom_frame,
            text="Close",
            command=self.root.destroy
        ).pack(side=tk.RIGHT, padx=5)
        
        # Instructions
        ttk.Label(
            main,
            text="Instructions: Scan the StampZ color target with auto-corrections OFF, "
                 "save as TIFF, crop to just inside the outer frame. "
                 "Black patch should be at top-left.",
            font=("Arial", 9),
            foreground='gray',
            wraplength=750
        ).pack(anchor='w', pady=(5, 0))
    
    def _create_results_header(self):
        """Create column headers for the patch results grid."""
        for widget in self.results_inner.winfo_children():
            widget.destroy()
        
        headers = ["Patch", "Reference", "Scanned", "Corrected", "ΔE Before", "ΔE After"]
        for col, header in enumerate(headers):
            ttk.Label(
                self.results_inner,
                text=header,
                font=("Arial", 9, "bold"),
                anchor='center'
            ).grid(row=0, column=col, padx=5, pady=2, sticky='ew')
    
    def _update_status(self):
        """Update the calibration status display."""
        from utils.scanner_calibration import get_active_calibration
        
        active = get_active_calibration()
        if active and active.is_valid:
            self.status_label.config(
                text="Scanner calibrated ✓",
                foreground='#006600'
            )
            quality = active.get_calibration_quality()
            if quality:
                self.profile_info_label.config(
                    text=f"Profile: {quality.get('profile_name', 'Unknown')}  |  "
                         f"Created: {quality.get('created_date', 'Unknown')[:10]}  |  "
                         f"Avg ΔE after: {quality.get('avg_delta_e_after', 0):.1f}"
                )
        else:
            self.status_label.config(
                text="Not calibrated",
                foreground='#CC0000'
            )
            self.profile_info_label.config(text="")
    
    def _load_target_scan(self):
        """Open file picker to load a scanned target image."""
        filetypes = [
            ("TIFF files", "*.tif *.tiff"),
            ("All image files", "*.tif *.tiff *.png *.jpg *.jpeg *.bmp"),
            ("All files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            parent=self.root,
            title="Select Scanned Target Image",
            filetypes=filetypes
        )
        
        if filepath:
            self.target_path = filepath
            self.file_label.config(
                text=os.path.basename(filepath),
                foreground='black'
            )
            self.calibrate_button.config(state='normal')
    
    def _calibrate(self):
        """Detect patches and compute calibration."""
        from utils.scanner_calibration import ScannerCalibration
        
        try:
            self.calibration = ScannerCalibration()
            
            # Detect patches
            self.root.config(cursor="watch")
            self.root.update()
            
            patches = self.calibration.detect_patches(self.target_path)
            
            # Compute correction
            self.quality = self.calibration.compute_correction()
            
            self.root.config(cursor="")
            
            # Update quality display
            used = self.quality.get('patches_used', len(self.calibration.patch_results))
            excluded = self.quality.get('patches_excluded', 0)
            self.quality_label.config(
                text=f"Avg ΔE: {self.quality['avg_delta_e_before']:.1f} → "
                     f"{self.quality['avg_delta_e_after']:.1f}  "
                     f"({self.quality['improvement_percent']:.0f}% improvement, "
                     f"{used} patches used, {excluded} out-of-gamut)",
                foreground='#006600'
            )
            
            # Enable save button
            self.save_button.config(state='normal')
            
            # Populate results grid
            self._populate_results()
            
        except Exception as e:
            self.root.config(cursor="")
            messagebox.showerror(
                "Calibration Error",
                f"Failed to calibrate:\n\n{str(e)}\n\n"
                "Make sure the target is properly cropped with the "
                "Black patch at top-left.",
                parent=self.root
            )
    
    def _populate_results(self):
        """Populate the patch results grid with color swatches and values."""
        # Clear existing results
        self._create_results_header()
        
        if not self.calibration or not self.calibration.patch_results:
            return
        
        from utils.scanner_calibration import ScannerCalibration
        threshold = ScannerCalibration.GAMUT_THRESHOLD
        
        for row_idx, patch in enumerate(self.calibration.patch_results, start=1):
            # Determine if patch was used in fit or excluded
            is_excluded = patch.delta_e_before > threshold
            name_text = f"{patch.name}  (out of gamut)" if is_excluded else patch.name
            name_color = '#999999' if is_excluded else 'black'
            
            # Patch name
            ttk.Label(
                self.results_inner,
                text=name_text,
                font=("Arial", 9),
                foreground=name_color,
                anchor='w'
            ).grid(row=row_idx, column=0, padx=5, pady=1, sticky='w')
            
            # Reference color swatch
            ref_hex = '#{:02x}{:02x}{:02x}'.format(*patch.digital_rgb)
            ref_frame = tk.Frame(self.results_inner, bg=ref_hex, width=50, height=18,
                                highlightthickness=1, highlightbackground='gray')
            ref_frame.grid(row=row_idx, column=1, padx=5, pady=1)
            ref_frame.grid_propagate(False)
            
            # Scanned color swatch
            sr, sg, sb = [int(max(0, min(255, v))) for v in patch.scanned_rgb]
            scan_hex = '#{:02x}{:02x}{:02x}'.format(sr, sg, sb)
            scan_frame = tk.Frame(self.results_inner, bg=scan_hex, width=50, height=18,
                                 highlightthickness=1, highlightbackground='gray')
            scan_frame.grid(row=row_idx, column=2, padx=5, pady=1)
            scan_frame.grid_propagate(False)
            
            # Corrected color swatch
            if patch.corrected_rgb:
                cr, cg, cb = [int(max(0, min(255, v))) for v in patch.corrected_rgb]
                corr_hex = '#{:02x}{:02x}{:02x}'.format(cr, cg, cb)
                corr_frame = tk.Frame(self.results_inner, bg=corr_hex, width=50, height=18,
                                     highlightthickness=1, highlightbackground='gray')
                corr_frame.grid(row=row_idx, column=3, padx=5, pady=1)
                corr_frame.grid_propagate(False)
            
            # ΔE before
            de_before_color = '#CC0000' if patch.delta_e_before > 50 else '#996600' if patch.delta_e_before > 20 else '#006600'
            ttk.Label(
                self.results_inner,
                text=f"{patch.delta_e_before:.1f}",
                font=("Arial", 9),
                foreground=de_before_color,
                anchor='center'
            ).grid(row=row_idx, column=4, padx=5, pady=1)
            
            # ΔE after
            de_after_color = '#CC0000' if patch.delta_e_after > 30 else '#996600' if patch.delta_e_after > 15 else '#006600'
            ttk.Label(
                self.results_inner,
                text=f"{patch.delta_e_after:.1f}",
                font=("Arial", 9),
                foreground=de_after_color,
                anchor='center'
            ).grid(row=row_idx, column=5, padx=5, pady=1)
    
    def _save_and_activate(self):
        """Save the calibration profile and activate it."""
        if not self.calibration or not self.calibration.is_valid:
            messagebox.showwarning(
                "No Calibration",
                "Please run calibration first.",
                parent=self.root
            )
            return
        
        # Ask for profile name
        name = simpledialog.askstring(
            "Profile Name",
            "Enter a name for this calibration profile\n"
            "(e.g., your scanner model):",
            parent=self.root,
            initialvalue="My Scanner"
        )
        
        if not name:
            return
        
        # Save profile
        from utils.path_utils import get_calibration_profiles_dir
        
        safe_name = "".join(c for c in name if c.isalnum() or c in ' _-').strip()
        profile_path = os.path.join(
            get_calibration_profiles_dir(),
            f"{safe_name}.json"
        )
        
        if not self.calibration.save_profile(profile_path, name=name):
            messagebox.showerror(
                "Save Error",
                "Failed to save calibration profile.",
                parent=self.root
            )
            return
        
        # Activate the calibration
        from utils.scanner_calibration import set_active_calibration
        set_active_calibration(self.calibration)
        
        # Save to preferences
        try:
            from utils.user_preferences import get_preferences_manager
            prefs = get_preferences_manager()
            prefs.preferences.calibration_prefs.active_profile_path = profile_path
            prefs.preferences.calibration_prefs.calibration_enabled = True
            prefs.save_preferences()
        except Exception as e:
            logger.warning(f"Could not save calibration preference: {e}")
        
        self._update_status()
        
        messagebox.showinfo(
            "Calibration Saved",
            f"Scanner calibration profile '{name}' has been saved and activated.\n\n"
            f"All future color measurements will be corrected using this profile.",
            parent=self.root
        )
    
    def _deactivate_calibration(self):
        """Deactivate the current calibration."""
        from utils.scanner_calibration import set_active_calibration
        set_active_calibration(None)
        
        # Update preferences
        try:
            from utils.user_preferences import get_preferences_manager
            prefs = get_preferences_manager()
            prefs.preferences.calibration_prefs.calibration_enabled = False
            prefs.save_preferences()
        except Exception as e:
            logger.warning(f"Could not save calibration preference: {e}")
        
        self._update_status()
        
        messagebox.showinfo(
            "Calibration Deactivated",
            "Scanner calibration has been deactivated.\n"
            "Color measurements will use raw scanner values.",
            parent=self.root
        )
    
    def _load_existing_profile(self):
        """Load an existing calibration profile from file."""
        from utils.path_utils import get_calibration_profiles_dir
        from utils.scanner_calibration import ScannerCalibration, set_active_calibration
        
        profiles_dir = get_calibration_profiles_dir()
        
        filepath = filedialog.askopenfilename(
            parent=self.root,
            title="Select Calibration Profile",
            initialdir=profiles_dir,
            filetypes=[
                ("JSON profiles", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        cal = ScannerCalibration()
        if cal.load_profile(filepath):
            self.calibration = cal
            set_active_calibration(cal)
            
            # Update preferences
            try:
                from utils.user_preferences import get_preferences_manager
                prefs = get_preferences_manager()
                prefs.preferences.calibration_prefs.active_profile_path = filepath
                prefs.preferences.calibration_prefs.calibration_enabled = True
                prefs.save_preferences()
            except Exception as e:
                logger.warning(f"Could not save calibration preference: {e}")
            
            self._update_status()
            self._populate_results()
            
            messagebox.showinfo(
                "Profile Loaded",
                f"Calibration profile '{cal.profile_name}' loaded and activated.",
                parent=self.root
            )
        else:
            messagebox.showerror(
                "Load Error",
                "Failed to load calibration profile.",
                parent=self.root
            )


def show_scanner_calibration_dialog(parent=None):
    """Show the scanner calibration dialog.
    
    Args:
        parent: Parent tkinter window
    """
    dialog = ScannerCalibrationDialog(parent)
    return dialog
