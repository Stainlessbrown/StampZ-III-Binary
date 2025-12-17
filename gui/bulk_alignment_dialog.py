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
        self.dialog.geometry("700x600")
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
        dialog_height = 600
        
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
        """Update the reference template information display."""
        if self.alignment_manager.has_reference():
            info = self.alignment_manager.get_reference_info()
            ref_text = (
                f"✓ Reference loaded\n"
                f"Features: {info['num_features']} detected\n"
                f"Size: {info['size'][0]}×{info['size'][1]} pixels"
            )
            self.ref_info_label.config(text=ref_text, foreground="green")
        else:
            self.ref_info_label.config(
                text="✗ No reference set",
                foreground="red"
            )
    
    def _select_files(self):
        """Open file dialog to select images."""
        filetypes = [
            ("Image Files", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
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
    
    def _process_images(self):
        """Process the selected images."""
        # Validate inputs
        if not self.alignment_manager.has_reference():
            messagebox.showerror(
                "No Reference",
                "No reference template is set. Please set a reference first.",
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
        
        # Show progress frame
        self.progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Disable process button
        self.process_button.config(state=tk.DISABLED)
        
        # Clear status
        self._update_status("Starting bulk alignment...", append=False)
        
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
                progress_callback=self._progress_callback
            )
            
            # Show results
            self._update_status("\n" + "="*50)
            self._update_status("PROCESSING COMPLETE")
            self._update_status("="*50)
            self._update_status(f"✓ Successfully aligned: {len(successful)}")
            self._update_status(f"✗ Failed: {len(failed)}")
            
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
