"""
File Manager for StampZ Application

Handles all file operations including open, save, and clear functionality.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import logging
from typing import TYPE_CHECKING

from utils.image_processor import load_image, ImageLoadError, ImageSaveError
from utils.save_as import SaveManager, SaveOptions, SaveFormat
from utils.filename_manager import FilenameManager

if TYPE_CHECKING:
    from .stampz_app import StampZApp

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file operations for the StampZ application."""
    
    def __init__(self, app: 'StampZApp'):
        self.app = app
        self.root = app.root
        
    def open_image(self, filename=None):
        """Open an image file with format optimization for color analysis."""
        # Reorder file types to prioritize formats best for color analysis
        filetypes = [
            ('Recommended for Color Analysis', '*.tif *.png'),
            ('16-bit TIFF (Best)', '*.tif *.tiff'),
            ('PNG (Lossless)', '*.png'),
            ('All Image files', '*.tif *.tiff *.png *.jpg *.jpeg'),
            ('JPEG (Not Recommended)', '*.jpg *.jpeg')
        ]
        
        # Use provided filename, otherwise ask user
        if not filename:
            from utils.user_preferences import get_preferences_manager
            prefs_manager = get_preferences_manager()
            
            # Get the last used directory for opening files
            initial_dir = prefs_manager.get_last_open_directory()
            
            filename = filedialog.askopenfilename(
                title="Open Image", 
                filetypes=filetypes,
                initialdir=initial_dir
            )
            
            # Save the directory for next time if a file was selected
            if filename:
                prefs_manager.set_last_open_directory(filename)

        if filename:
            try:
                image, metadata = load_image(filename)
                self.app.canvas.load_image(image)
                self.app.current_file = filename
                self.app.current_image_metadata = metadata  # Store metadata for later use
                
                # Clear any cached leveling images when new image is loaded
                if hasattr(self.app, 'control_panel') and hasattr(self.app.control_panel, '_true_original_image'):
                    self.app.control_panel._true_original_image = None
                    print("DEBUG: Cleared cached leveling image on new image load")
                
                self.app.control_panel.enable_controls(True)
                base_filename = os.path.basename(filename)
                
                # Determine bit depth for title display
                bit_depth_str = self._get_bit_depth_string(image, metadata)
                self.root.title(f"StampZ - {base_filename} [{bit_depth_str}]")
                
                self.app.control_panel.update_current_filename(filename)
                
                # Update image dimensions display
                width, height = image.size
                self.app.control_panel.update_image_dimensions(width, height)

                # Compose status bar text with mode, bit-depth, ICC
                status_text = self._compose_status_text(image, metadata, width, height)
                if hasattr(self.app, 'control_panel'):
                    self.app.control_panel.update_image_status(status_text)
                
                # Show format information to user
                self._show_format_info(filename, metadata)
                
            except ImageLoadError as e:
                messagebox.showerror("Error", str(e))
    
    def _show_format_info(self, filename, metadata):
        """Show format information to the user based on loaded image metadata."""
        try:
            format_info = metadata.get('format_info', 'Unknown format')
            precision_preserved = metadata.get('precision_preserved', False)
            
            # Only show informational dialogs for significant format situations
            if precision_preserved:
                # 16-bit TIFF loaded successfully - brief positive confirmation
                print(f"✅ Loaded 16-bit TIFF with full precision: {os.path.basename(filename)}")
            elif '16-bit support' in format_info:
                # Could be 16-bit but tifffile not available - show warning
                response = messagebox.askyesno(
                    "16-bit TIFF Detected", 
                    f"This appears to be a 16-bit TIFF file, but it's being loaded as 8-bit.\\n\\n"
                    f"For maximum color accuracy, install the 'tifffile' library:\\n"
                    f"pip install tifffile\\n\\n"
                    f"Would you like to continue with 8-bit loading?"
                )
                if not response:
                    # User chose not to continue, could implement auto-install here
                    pass
            elif 'compressed' in format_info.lower() or 'jpeg' in format_info.lower():
                # JPEG format - show brief warning about compression
                if not hasattr(self.app, 'first_jpeg_warning'):
                    messagebox.showinfo(
                        "JPEG Format Notice", 
                        f"JPEG format detected: {os.path.basename(filename)}\\n\\n"
                        f"Note: JPEG uses lossy compression which may affect color analysis precision.\\n"
                        f"For best results, use TIFF or PNG formats.\\n\\n"
                        f"This notice will only appear once per session."
                    )
                    self.app.first_jpeg_warning = True
            
            # Always log the format info for debugging
            logger.info(f"Loaded {os.path.basename(filename)}: {format_info}")
            
        except Exception as e:
            logger.warning(f"Error showing format info: {e}")

    def _get_bit_depth_string(self, image, metadata):
        """Get bit depth string for display."""
        try:
            mode = getattr(image, 'mode', None) or metadata.get('photometric') or 'RGB'
            bpc = metadata.get('original_bit_depth')
            if isinstance(bpc, (list, tuple)):
                # If all equal, show single; else join
                uniq = sorted(set(bpc))
                return f"{uniq[0]}-bit" if len(uniq) == 1 else " / ".join(str(x) for x in bpc)
            elif isinstance(bpc, int):
                return f"{bpc}-bit"
            else:
                # Fallback based on mode
                return "16-bit" if mode in ('I;16','I;16B','I;16L') else ("32-bit" if mode in ('I','F') else "8-bit")
        except Exception:
            return "8-bit"  # Safe fallback
    
    def _compose_status_text(self, image, metadata, width, height):
        """Create the status bar text: MODE • <bits>-bit • WxH • ICC: <name>"""
        try:
            mode = getattr(image, 'mode', None) or metadata.get('photometric') or 'RGB'
            bpc_str = self._get_bit_depth_string(image, metadata)
            icc = metadata.get('icc_profile_name') or ('sRGB' if 'Converted from embedded profile' in metadata.get('color_profile','') else 'None')
            return f"{mode} • {bpc_str} • {width}×{height} • ICC: {icc}"
        except Exception:
            return f"{image.mode if hasattr(image,'mode') else 'RGB'} • {width}×{height}"

    def save_image(self):
        """Save the cropped or aligned image with format optimization."""
        if not self.app.canvas.original_image:
            messagebox.showwarning("No Image", "Please open an image before saving.")
            return
        
        # Check if we have a crop selection or if we're saving the whole image (e.g., aligned)
        try:
            cropped = self.app.canvas.get_cropped_image()
            is_cropped = True
        except ValueError:
            # No crop selection - save the entire image (e.g., aligned image)
            cropped = self.app.canvas.original_image
            is_cropped = False
            
        try:
            panel_options = self.app.control_panel.get_save_options()
            save_manager = SaveManager()
            
            # Only show formats suitable for color analysis
            filetypes = [
                ('Recommended for Analysis', '*.tif *.png'),
                ('16-bit TIFF (Best Quality)', '*.tif *.tiff'),
                ('PNG (Lossless)', '*.png'),
                ('All Supported files', '*.tif *.tiff *.png')
            ]
            
            # Set default extension based on panel selection
            if panel_options.format == SaveFormat.PNG:
                default_ext = '.png'
            else:  # TIFF (default and best choice for color analysis)
                default_ext = '.tif'

            filename_manager = FilenameManager()
            if is_cropped:
                suggested_name = filename_manager.generate_cropped_filename(
                    original_file=self.app.current_file,
                    cropped_image=cropped,
                    extension=default_ext,
                    use_dimensions=True
                )
            else:
                # For aligned images, suggest name with _aligned suffix
                if self.app.current_file:
                    base = os.path.splitext(os.path.basename(self.app.current_file))[0]
                    suggested_name = f"{base}_aligned{default_ext}"
                else:
                    suggested_name = f"aligned_image{default_ext}"

            from utils.user_preferences import get_preferences_manager
            prefs_manager = get_preferences_manager()
            
            # Default to the same directory as the original image for easier data file merging
            if self.app.current_file:
                initial_dir = os.path.dirname(self.app.current_file)
            else:
                # Fallback to last used directory if no current file
                initial_dir = prefs_manager.get_last_save_directory()
            
            save_title = "Save Cropped Image" if is_cropped else "Save Aligned Image"
            filepath = filedialog.asksaveasfilename(
                title=save_title,
                defaultextension=default_ext,
                initialfile=suggested_name,
                filetypes=filetypes,
                initialdir=initial_dir
            )
            
            # Save the directory for next time if a file was selected
            if filepath:
                prefs_manager.set_last_save_directory(filepath)

            if filepath:
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ['.jpg', '.jpeg']:
                    # JPEG is not supported for saving - show error and suggest alternatives
                    messagebox.showerror(
                        "JPEG Format Not Supported for Saving",
                        "⚠️  JPEG format is not supported for saving in this application.\\n\\n"
                        "JPEG uses lossy compression which reduces color analysis accuracy.\\n\\n"
                        "Please choose a lossless format:\\n"
                        "• .tif extension (16-bit support, best for analysis)\\n"
                        "• .png extension (lossless compression)\\n\\n"
                        "Note: You can still open JPEG files for analysis."
                    )
                    return  # Cancel save operation
                elif ext in ['.tif', '.tiff']:
                    selected_format = SaveFormat.TIFF
                elif ext == '.png':
                    selected_format = SaveFormat.PNG
                else:
                    selected_format = panel_options.format
                    base_name = os.path.splitext(filepath)[0]
                    filepath = f"{base_name}{SaveFormat.get_extension(selected_format)}"

                if selected_format != panel_options.format:
                    panel_options = SaveOptions(
                        format=selected_format,
                        jpeg_quality=95,  # Not used for TIFF/PNG but kept for compatibility
                        optimize=True
                    )

                save_manager.save_image(cropped, filepath, panel_options)
                self.app.recent_files.add_file(filepath)
                
                # Update dimensions display after save
                width, height = cropped.size
                self.app.control_panel.update_image_dimensions(width, height)

                save_type = "Cropped" if is_cropped else "Aligned"
                replace_response = messagebox.askyesno(
                    "Replace Original?", 
                    f"{save_type} image saved successfully!\\n\\n"
                    f"Would you like to replace the original image with the {save_type.lower()} version?\\n\\n"
                    f"This will load the {save_type.lower()} image for further editing."
                )

                if replace_response:
                    try:
                        new_image, new_metadata = load_image(filepath)
                        self.app.canvas.load_image(new_image)
                        self.app.current_file = filepath
                        self.app.current_image_metadata = new_metadata
                        base_filename = os.path.basename(filepath)
                        self.root.title(f"StampZ - {base_filename}")
                        self.app.control_panel.update_current_filename(filepath)
                        w2, h2 = new_image.size
                        self.app.control_panel.update_image_dimensions(w2, h2)
                        try:
                            status_text2 = self._compose_status_text(new_image, new_metadata, w2, h2)
                            self.app.control_panel.update_image_status(status_text2)
                        except Exception:
                            pass
                    except ImageLoadError as e:
                        messagebox.showerror("Error", f"Failed to load cropped image: {str(e)}")

        except (ImageSaveError, OSError) as e:
            messagebox.showerror("Save Error", str(e))

    def clear_image(self):
        """Clear the current image and reset the application to its opening state."""
        if self.app.canvas:
            # Clear canvas and reset image
            self.app.canvas.clear_image()  # Use canvas's clear method
            self.app.current_file = None
            self.app.canvas.configure(width=800, height=600)  # Reset to default size
            
            # Clear all sample markers and reset sample window state
            self.app._clear_samples(skip_confirmation=True, reset_all=True)  # Use existing method to clear samples
            
            # Reset window title
            self.root.title("StampZ_II")
            
            # Reset control panel state
            if hasattr(self.app.control_panel, 'sample_set_name'):
                self.app.control_panel.sample_set_name.set('')
            if hasattr(self.app.control_panel, 'analysis_name'):
                self.app.control_panel.analysis_name.set('')
            
            # Reset all sample controls to defaults
            if hasattr(self.app.control_panel, 'sample_controls'):
                for control in self.app.control_panel.sample_controls:
                    control['shape'].set('rectangle')
                    control['width'].set('20')
                    control['height'].set('20')
                    control['anchor'].set('center')
            
            # Reset mode to template if in sample mode
            if hasattr(self.app.control_panel, 'sample_mode'):
                self.app.control_panel.sample_mode.set('template')
                if hasattr(self.app.control_panel, '_set_template_mode_ui'):
                    self.app.control_panel._set_template_mode_ui()
            
            # Update display
            self.app.canvas.update()

    def quit_app(self):
        """Handle application quit with cleanup."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            # Clean up any temporary coordinate data
            try:
                from utils.coordinate_db import CoordinateDB
                db = CoordinateDB()
                db.cleanup_temporary_data()
            except Exception as e:
                print(f"Warning: Failed to clean up temporary data: {e}")
            
            self.root.quit()
            self.root.destroy()

