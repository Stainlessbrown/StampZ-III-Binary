"""
Save functionality for the StampZ application.
Handles image saving with support for multiple formats and save options.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from tkinter import filedialog
from PIL import Image
import numpy as np

from .image_processor import ImageSaveError

# Configure logging
logger = logging.getLogger(__name__)

class SaveFormat:
    """Constants for supported save formats."""
    JPEG = 'JPEG'
    TIFF = 'TIFF'
    PNG = 'PNG'
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Get list of supported save formats."""
        return [cls.TIFF, cls.PNG]
    
    @classmethod
    def get_extension(cls, format: str) -> str:
        """Get file extension for format."""
        format = format.upper()
        if format == cls.JPEG:
            return '.jpg'
        elif format == cls.TIFF:
            return '.tif'
        elif format == cls.PNG:
            return '.png'
        raise ValueError(f"Unsupported format: {format}")

    @classmethod
    def detect_format_from_extension(cls, filepath: str) -> str:
        """
        Detect format from file extension.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Detected format (PNG or JPEG)
            
        Raises:
            ValueError if extension is not supported
        """
        ext = os.path.splitext(filepath)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            return cls.JPEG
        elif ext in ['.tif', '.tiff']:
            return cls.TIFF
        elif ext == '.png':
            return cls.PNG
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
    
    @classmethod
    def validate_format(cls, format: str) -> str:
        """Validate and normalize format string."""
        format = format.upper().strip()
        if format not in cls.get_supported_formats():
            raise ValueError(f"Unsupported format: {format}")
        return format

class SaveOptions:
    """Configuration for image save operation."""
    
    def __init__(
        self,
        format: str = SaveFormat.TIFF,
        jpeg_quality: int = 95,
        optimize: bool = True
    ):
        """
        Initialize save options.
        
        Args:
            format: Output format ('TIFF' or 'PNG')
            jpeg_quality: JPEG quality (1-100, deprecated - kept for compatibility)
            optimize: Whether to optimize the output file
        """
        self.format = SaveFormat.validate_format(format)
        self.jpeg_quality = max(1, min(100, jpeg_quality))  # Clamp between 1-100
        self.optimize = optimize
    
    @property
    def extension(self) -> str:
        """Get appropriate file extension for current format."""
        return SaveFormat.get_extension(self.format)
    
    @property
    def save_kwargs(self) -> Dict:
        """Get PIL save keyword arguments for current options."""
        kwargs = {
            'format': self.format
        }
        
        # JPEG-specific options
        if self.format == SaveFormat.JPEG:
            kwargs['quality'] = self.jpeg_quality
            kwargs['optimize'] = self.optimize
        # TIFF-specific options
        elif self.format == SaveFormat.TIFF:
            kwargs['compression'] = None  # Uncompressed TIFF for accurate color analysis
        # PNG-specific options
        elif self.format == SaveFormat.PNG:
            kwargs['optimize'] = self.optimize
            
        return kwargs

class SaveManager:
    """Manages image save operations and dialogs."""
    
    def __init__(self):
        """Initialize SaveManager."""
        self._default_options = SaveOptions()
    
    def prepare_image_for_save(
        self,
        image: Image.Image,
        options: SaveOptions
    ) -> Image.Image:
        """
        Prepare image for saving in specified format.
        
        Args:
            image: PIL Image to prepare
            options: Save options
            
        Returns:
            Prepared PIL Image
        """
        # Check if there's attached 16-bit data before copying
        has_16bit_data = hasattr(image, '_stampz_16bit_data')
        sixteen_bit_data = image._stampz_16bit_data if has_16bit_data else None
        
        img = image.copy()
        
        # Re-attach 16-bit data after copy if it existed
        if has_16bit_data:
            img._stampz_16bit_data = sixteen_bit_data
        
        if options.format == SaveFormat.JPEG:
            # Convert to RGB for JPEG if needed
            if img.mode in ('RGBA', 'LA'):
                # Create white background
                background = Image.new('RGB', img.size, 'white')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img, mask=img.split()[1])
                img = background
                # Re-attach 16-bit data if it was there
                if has_16bit_data:
                    img._stampz_16bit_data = sixteen_bit_data
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                # Re-attach 16-bit data if it was there
                if has_16bit_data:
                    img._stampz_16bit_data = sixteen_bit_data
                
        return img
    
    def get_save_filepath(
        self,
        suggested_name: Optional[str] = None,
        current_file: Optional[str] = None,
        options: Optional[SaveOptions] = None,
        respect_extension: bool = True
    ) -> Optional[str]:
        """
        Show save file dialog and return selected path.
        
        Args:
            suggested_name: Suggested filename (without extension)
            current_file: Path to currently open file
            options: Save options
            
        Returns:
            Selected filepath or None if cancelled
        """
        options = options or self._default_options
        
        # Determine suggested filename
        if not suggested_name:
            if current_file:
                base = os.path.splitext(os.path.basename(current_file))[0]
                suggested_name = f"{base}_cropped"
            else:
                suggested_name = "cropped"
        else:
            # If suggested_name is provided, use it as-is (without extension)
            # Remove extension if it was included in the suggested name
            suggested_name = os.path.splitext(suggested_name)[0]
        
        # Add appropriate extension
        suggested_name = f"{suggested_name}{options.extension}"
        
        # Set up filetypes for dialog
        if options.format == SaveFormat.PNG:
            filetypes = [
                ('PNG files', '*.png'),
                ('All files', '*.*')
            ]
        else:  # TIFF (default)
            filetypes = [
                ('TIFF files', '*.tif'),
                ('All files', '*.*')
            ]
        
        # Show save dialog
        filepath = filedialog.asksaveasfilename(
            title="Save Image",
            defaultextension=options.extension,
            initialfile=suggested_name,
            filetypes=filetypes
        )
        
        if filepath:
            base_name, ext = os.path.splitext(filepath)
            
            # Handle format selection based on extension and options
            if respect_extension and ext.lower() in ['.tif', '.tiff', '.png']:
                try:
                    detected_format = SaveFormat.detect_format_from_extension(filepath)
                    if detected_format != options.format:
                        logger.info(f"Adjusting format to match extension: {detected_format}")
                        options.format = detected_format
                except ValueError:
                    # If extension is not recognized, use the selected format
                    logger.info(f"Using selected format {options.format} for unknown extension")
                    ext = options.extension
            else:
                # Use the format from options
                ext = options.extension
                
            filepath = f"{base_name}{ext}"
            logger.debug(f"Final filepath: {filepath}, format: {options.format}")
            
        return filepath if filepath else None
    
    def save_image(
        self,
        image: Image.Image,
        filepath: Union[str, Path],
        options: Optional[SaveOptions] = None,
        add_to_recent: bool = True
    ) -> None:
        """
        Save image with specified options.
        
        Args:
            image: PIL Image to save
            filepath: Path where image should be saved
            options: Save options
            add_to_recent: Whether to add the saved file to recent files
            
        Raises:
            ImageSaveError: If save operation fails
        """
        options = options or self._default_options
        filepath = Path(filepath)
        
        try:
            # Validate format matches file extension
            try:
                file_format = SaveFormat.detect_format_from_extension(filepath)
                if file_format != options.format:
                    logger.warning(
                        f"Format mismatch: File extension indicates {file_format}, "
                        f"but saving as {options.format}"
                    )
            except ValueError:
                logger.warning(f"Unrecognized file extension, using format: {options.format}")

            # Prepare image for saving
            img_to_save = self.prepare_image_for_save(image, options)
            
            # Ensure save directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Log save operation details
            logger.info(f"Saving image with format: {options.format}")
            logger.debug(f"Save path: {filepath}")
            logger.debug(f"Image mode: {img_to_save.mode}")
            logger.debug(f"Save options: {options.save_kwargs}")
            
            # Check if this is a 16-bit image that needs special handling
            # First check if there's attached 16-bit data (from rotation operations)
            if hasattr(img_to_save, '_stampz_16bit_data'):
                img_array = img_to_save._stampz_16bit_data
                is_16bit = True
                logger.info("Found attached 16-bit data from rotation operation")
            else:
                img_array = np.array(img_to_save)
                is_16bit = img_array.dtype == np.uint16
            
            if is_16bit and options.format == SaveFormat.TIFF:
                # Use tifffile to save 16-bit TIFF properly
                try:
                    import tifffile
                    logger.info("Saving as 16-bit TIFF using tifffile to preserve precision")
                    tifffile.imwrite(str(filepath), img_array, photometric='rgb')
                    logger.debug(f"16-bit TIFF save completed successfully")
                except ImportError:
                    logger.warning("tifffile not available - saving with PIL (may lose 16-bit precision)")
                    img_to_save.save(str(filepath), **options.save_kwargs)
                except Exception as e:
                    logger.error(f"Error saving with tifffile: {e}, falling back to PIL")
                    img_to_save.save(str(filepath), **options.save_kwargs)
            else:
                # Standard save operation for 8-bit images or non-TIFF formats
                img_to_save.save(str(filepath), **options.save_kwargs)
                logger.debug(f"Save completed successfully")
            
        except (OSError, ValueError) as e:
            raise ImageSaveError(f"Failed to save image {filepath}: {str(e)}")
    
    def quick_save(
        self,
        image: Image.Image,
        suggested_name: Optional[str] = None,
        current_file: Optional[str] = None,
        options: Optional[SaveOptions] = None
    ) -> Optional[str]:
        """
        Perform complete save operation with dialog.
        
        Args:
            image: PIL Image to save
            suggested_name: Suggested filename
            current_file: Path to currently open file
            options: Save options
            
        Returns:
            Path where image was saved, or None if cancelled
        """
        filepath = self.get_save_filepath(
            suggested_name=suggested_name,
            current_file=current_file,
            options=options
        )
        
        if filepath:
            self.save_image(image, filepath, options)
            return filepath
            
        return None

# Convenience functions for simple usage
def save_with_dialog(
    image: Image.Image,
    suggested_name: Optional[str] = None,
    format: str = SaveFormat.TIFF,
    jpeg_quality: int = 95
) -> Optional[str]:
    """
    Simple function to save image with dialog.
    
    Args:
        image: PIL Image to save
        suggested_name: Suggested filename
        format: Output format (TIFF or PNG only)
        jpeg_quality: Deprecated parameter, kept for compatibility
        
    Returns:
        Path where image was saved, or None if cancelled
    """
    manager = SaveManager()
    options = SaveOptions(format=format, jpeg_quality=jpeg_quality)
    return manager.quick_save(image, suggested_name=suggested_name, options=options)

