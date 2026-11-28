"""
Bulk Image Alignment Dialog for StampZ

Provides a GUI for batch processing multiple images through alignment.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.image_alignment import ImageAlignmentManager


def reference_status(alignment_manager):
    """Describe the actual loaded reference and bulk readiness."""
    from pathlib import Path

    info = alignment_manager.get_reference_info()

    if not info:
        return "No active reference", False

    width, height = info["size"]
    details = (
        f"Features: {info['num_features']} detected\\n"
        f"Size: {width} x {height} pixels"
    )

    filepath = info.get("filepath")

    if not filepath:
        return (
            "Reference selected - not saved and activated\\n"
            + details,
            False
        )

    path = Path(filepath)
    image_path = path.with_name(
        path.stem + "_reference.png"
    )

    if not path.is_file() or not image_path.is_file():
        return (
            f"Reference incomplete: {path.name}\\n"
            "Saved template or companion image is missing.",
            False
        )

    return (
        f"Active reference: {path.name}\\n"
        f"Location: {path.parent}\\n"
        + details,
        True
    )


class BulkAlignmentDialog:
    """Dialog for bulk image alignment processing."""
    
    def __init__(self, parent: tk.Tk, alignment_manager: 'ImageAlignmentManager'):
        """
        Initialize the bulk alignment dialog.
        
        Args:
            parent: Parent Tk window
            alignment_manager: ImageAlignmentManager instance with reference set
        """
        self.parent = parent
        self.alignment_manager = alignment_manager
        self.selected_files = []
        self.output_directory = ""
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Image Alignment")
        self.dialog.geometry("700x680")
        self.dialog.resizable(True, True)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self._center_dialog()
        
        # Create UI
        self._create_widgets()
        
        # Update reference info
        self._update_reference_info()
    
    def _center_dialog(self):
        """Center the dialog on the parent window."""
        self.dialog.update_idletasks()
        
        # Get parent position and size
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Get dialog size
        dialog_width = 700
        dialog_height = 680
        
        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _create_widgets(self):
        """Create the dialog widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Bulk Image Alignment",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Reference info section
        ref_frame = ttk.LabelFrame(main_frame, text="Reference Template", padding=10)
        ref_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.ref_info_label = ttk.Label(ref_frame, text="", justify=tk.LEFT)
        self.ref_info_label.pack()
        
        # Input files section
        input_frame = ttk.LabelFrame(main_frame, text="Input Images", padding=10)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # File selection buttons
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Select Images...",
            command=self._select_files
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Clear List",
            command=self._clear_files
        ).pack(side=tk.LEFT)
        
        self.file_count_label = ttk.Label(button_frame, text="0 images selected")
        self.file_count_label.pack(side=tk.RIGHT)
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(input_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.EXTENDED,
            font=("Courier", 10)
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # Sensitivity settings section
        sensitivity_frame = ttk.LabelFrame(main_frame, text="Alignment Sensitivity", padding=10)
        sensitivity_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Min matches spinbox
        min_matches_frame = ttk.Frame(sensitivity_frame)
        min_matches_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(min_matches_frame, text="Min Feature Matches:", width=20).pack(side=tk.LEFT)
        self.min_matches_var = tk.IntVar(value=self.alignment_manager.min_matches)
        ttk.Spinbox(
            min_matches_frame,
            from_=3,
            to=50,
            textvariable=self.min_matches_var,
            width=5
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            min_matches_frame,
            text="(lower = more tolerant, 3-50)",
            font=("Arial", 8),
            foreground="gray"
        ).pack(side=tk.LEFT)
        
        # RANSAC threshold spinbox
        ransac_frame = ttk.Frame(sensitivity_frame)
        ransac_frame.pack(fill=tk.X)
        
        ttk.Label(ransac_frame, text="RANSAC Pixel Threshold:", width=20).pack(side=tk.LEFT)
        self.ransac_threshold_var = tk.DoubleVar(value=self.alignment_manager.ransac_threshold)
        ttk.Spinbox(
            ransac_frame,
            from_=1.0,
            to=20.0,
            increment=0.5,
            textvariable=self.ransac_threshold_var,
            width=5
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            ransac_frame,
            text="(higher = more tolerant, 1.0-20.0)",
            font=("Arial", 8),
            foreground="gray"
        ).pack(side=tk.LEFT)
        
        # Output directory section
        output_frame = ttk.LabelFrame(main_frame, text="Output Directory", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill=tk.X)
        
        self.output_dir_var = tk.StringVar()
        ttk.Entry(
            dir_frame,
            textvariable=self.output_dir_var,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(
            dir_frame,
            text="Browse...",
            command=self._select_output_dir
        ).pack(side=tk.RIGHT)
        
        # Option to copy reference image
        self.copy_reference_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            output_frame,
            text="Copy reference image to output directory",
            variable=self.copy_reference_var
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Progress section (initially hidden)
        self.progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding=10)
        
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Status text area
        status_scroll = ttk.Scrollbar(self.progress_frame)
        status_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.status_text = tk.Text(
            self.progress_frame,
            height=8,
            yscrollcommand=status_scroll.set,
            font=("Courier", 9),
            state=tk.DISABLED
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)
        status_scroll.config(command=self.status_text.yview)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.process_button = ttk.Button(
            button_frame,
            text="Process Images",
            command=self._process_images
        )
        self.process_button.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Close",
            command=self.dialog.destroy
        ).pack(side=tk.RIGHT)
    
    def _update_reference_info(self):
        """Display the actual active saved reference."""
        text, ready = reference_status(self.alignment_manager)

        self.ref_info_label.config(
            text=text,
            foreground="green" if ready else "red",
            wraplength=620
        )

        self.process_button.config(
            state=tk.NORMAL if ready else tk.DISABLED
        )

    def _select_files(self):
        """Open file dialog to select images."""
        filetypes = [
            ("Image Files", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.cr3 *.cr2 *.nef *.arw *.orf *.rw2 *.dng"),
            ("Camera RAW", "*.cr3 *.cr2 *.nef *.arw *.orf *.rw2 *.dng"),
            ("PNG Files", "*.png"),
            ("JPEG Files", "*.jpg *.jpeg"),
            ("TIFF Files", "*.tif *.tiff"),
            ("All Files", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            parent=self.dialog,
            title="Select Images to Align",
            filetypes=filetypes
        )
        
        if files:
            # Add to selected files (avoid duplicates)
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
            
            self._update_file_list()
    
    def _clear_files(self):
        """Clear the selected files list."""
        self.selected_files = []
        self._update_file_list()
    
    def _update_file_list(self):
        """Update the file listbox display."""
        self.file_listbox.delete(0, tk.END)
        
        for filepath in self.selected_files:
            filename = os.path.basename(filepath)
            self.file_listbox.insert(tk.END, filename)
        
        count = len(self.selected_files)
        self.file_count_label.config(text=f"{count} image{'s' if count != 1 else ''} selected")
    
    def _select_output_dir(self):
        """Open directory dialog to select output directory."""
        directory = filedialog.askdirectory(
            parent=self.dialog,
            title="Select Output Directory"
        )
        
        if directory:
            self.output_directory = directory
            self.output_dir_var.set(directory)
    
    def _update_status(self, message: str, append: bool = True):
        """Update the status text area."""
        self.status_text.config(state=tk.NORMAL)
        if append:
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
        else:
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, message + "\n")
        self.status_text.config(state=tk.DISABLED)
    
    def _progress_callback(self, current: int, total: int, filename: str, status: str):
        """Callback for progress updates during bulk processing."""
        # Update progress bar
        self.progress_bar['value'] = (current / total) * 100
        
        # Update progress label
        self.progress_label.config(text=f"Processing {current} of {total}: {filename}")
        
        # Update status text
        self._update_status(f"[{current}/{total}] {filename}: {status}")
        
        # Force GUI update
        self.dialog.update_idletasks()
    
    def _choose_existing_destination(self, path: str):
        """Ask the user whether to replace, rename, or skip one aligned TIFF."""
        if getattr(self, "_overwrite_all", False):
            return ("overwrite", None)

        choice = {"action": "cancel", "apply_all": False}
        window = tk.Toplevel(self.dialog)
        window.title("File Already Exists")
        window.transient(self.dialog)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", lambda: close("cancel"))
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame, text=f"{os.path.basename(path)} already exists.",
            font=("Arial", 12, "bold"), wraplength=440
        ).pack(anchor=tk.W, pady=(0, 8))
        ttk.Label(
            frame, text="Overwrite the existing file, save under another name, or cancel?",
            wraplength=440
        ).pack(anchor=tk.W, pady=(0, 12))
        apply_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Apply Overwrite to all remaining existing files",
            variable=apply_all
        ).pack(anchor=tk.W, pady=(0, 12))
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)

        def close(action):
            choice["action"] = action
            choice["apply_all"] = bool(apply_all.get()) if action == "overwrite" else False
            window.destroy()

        ttk.Button(buttons, text="Overwrite", command=lambda: close("overwrite")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Save As…", command=lambda: close("save_as")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=lambda: close("cancel")).pack(side=tk.RIGHT)
        window.update_idletasks()
        window.grab_set()
        self.dialog.wait_window(window)
        if self.dialog.winfo_exists():
            self.dialog.grab_set()

        if choice["action"] == "overwrite":
            if choice["apply_all"]:
                self._overwrite_all = True
            return ("overwrite", None)
        if choice["action"] == "save_as":
            new_path = filedialog.asksaveasfilename(
                parent=self.dialog,
                title="Save Aligned TIFF As",
                initialdir=os.path.dirname(path),
                initialfile=os.path.basename(path),
                defaultextension=".tif",
                filetypes=[("TIFF Images", "*.tif *.tiff")],
            )
            return ("save_as", new_path) if new_path else ("cancel", None)
        return ("cancel", None)

    def _process_images(self):
        """Process the selected images."""
        # Validate reference before producing any output.
        text, ready = reference_status(self.alignment_manager)

        if not ready:
            self._update_reference_info()
            messagebox.showerror(
                "Reference Not Ready",
                text + "\\n\\nUse Alignment Reference to save or load a reference.",
                parent=self.dialog
            )
            return

        if not self.selected_files:
            messagebox.showwarning(
                "No Images",
                "Please select images to process.",
                parent=self.dialog
            )
            return
        
        if not self.output_directory:
            messagebox.showwarning(
                "No Output Directory",
                "Please select an output directory.",
                parent=self.dialog
            )
            return
        
        # Confirm processing
        count = len(self.selected_files)
        response = messagebox.askyesno(
            "Confirm Processing",
            f"Process {count} image{'s' if count != 1 else ''} and save to:\n"
            f"{self.output_directory}\n\n"
            f"Aligned images will be saved with '_aligned' suffix.",
            parent=self.dialog
        )
        
        if not response:
            return
        
        self._overwrite_all = False

        # Show progress frame
        self.progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Disable process button
        self.process_button.config(state=tk.DISABLED)
        
        # Clear status
        self._update_status("Starting bulk alignment...", append=False)
        
        # Apply user-selected sensitivity thresholds
        min_matches = self.min_matches_var.get()
        ransac_threshold = self.ransac_threshold_var.get()
        self.alignment_manager.min_matches = min_matches
        self.alignment_manager.ransac_threshold = ransac_threshold
        self._update_status(f"Sensitivity settings: min_matches={min_matches}, ransac_threshold={ransac_threshold}")
        
        try:
            # Copy reference image if requested
            if self.copy_reference_var.get():
                try:
                    ref_image = self.alignment_manager.get_reference_image()
                    if ref_image is not None:
                        ref_filename = "reference_template.tif"
                        ref_path = os.path.join(self.output_directory, ref_filename)
                        ref_image.save(ref_path)
                        self._update_status(f"✓ Copied reference template to output directory")
                except Exception as e:
                    self._update_status(f"⚠ Could not copy reference: {str(e)}")
            
            # Process images
            successful, failed = self.alignment_manager.bulk_align_images(
                self.selected_files,
                self.output_directory,
                progress_callback=self._progress_callback,
                collision_callback=self._choose_existing_destination
            )
            
            skipped = getattr(self.alignment_manager, "last_bulk_skipped", [])

            # Show results
            self._update_status("\n" + "="*50)
            self._update_status("PROCESSING COMPLETE")
            self._update_status("="*50)
            self._update_status(f"✓ Successfully aligned: {len(successful)}")
            self._update_status(f"– Skipped: {len(skipped)}")
            self._update_status(f"✗ Failed: {len(failed)}")
            
            if skipped:
                self._update_status("\nSkipped images:")
                for filepath, _ in skipped:
                    self._update_status(f"  - {os.path.basename(filepath)}: save cancelled")

            if failed:
                self._update_status("\nFailed images:")
                for filepath, error in failed:
                    filename = os.path.basename(filepath)
                    self._update_status(f"  - {filename}: {error}")
            
            # Show summary dialog
            messagebox.showinfo(
                "Processing Complete",
                f"Bulk alignment complete!\n\n"
                f"✓ Successful: {len(successful)}\n"
                f"– Skipped: {len(skipped)}\n"
                f"✗ Failed: {len(failed)}\n\n"
                f"Aligned images saved to:\n{self.output_directory}",
                parent=self.dialog
            )
            
        except Exception as e:
            self._update_status(f"\nERROR: {str(e)}")
            messagebox.showerror(
                "Processing Error",
                f"An error occurred during processing:\n\n{str(e)}",
                parent=self.dialog
            )
        
        finally:
            # Re-enable process button
            self.process_button.config(state=tk.NORMAL)
