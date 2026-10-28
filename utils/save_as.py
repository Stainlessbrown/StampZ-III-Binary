"""
Save functionality for the StampZ application.
Handles image saving with support for multiple formats and save options.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from tkinter import filedialog
from PIL import Image
import numpy as np

from .image_processor import ImageSaveError

# Configure logging
logger = logging.getLogger(__name__)


def _add_stampz_png_metadata(filepath, encoding, raw_derived, icc_bytes=None):
    """Preserve PNG encoding, RAW provenance, and ICC without re-encoding pixels."""
    import struct
    import zlib

    if encoding not in ("linear", "srgb"):
        raise ImageSaveError("Cannot save PNG: pixel encoding is unknown.")

    if encoding == "linear" and icc_bytes:
        raise ImageSaveError("Linear PNG must not carry an sRGB ICC profile.")

    if encoding == "srgb" and not icc_bytes:
        raise ImageSaveError("sRGB ICC profile unavailable; PNG not finalized.")

    filepath = Path(filepath)
    data = filepath.read_bytes()
    signature = bytes((137, 80, 78, 71, 13, 10, 26, 10))

    if not data.startswith(signature):
        raise ImageSaveError("Invalid PNG signature")

    def make_chunk(kind, payload):
        crc = zlib.crc32(kind + payload) & 0xffffffff
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", crc)
        )

    fields = {
        "StampZ-Encoding": encoding,
        "StampZ-RAW-Derived": "Yes" if raw_derived else "No",
    }

    chunks = b"".join(
        make_chunk(
            b"tEXt",
            name.encode("ascii") + bytes((0,)) + value.encode("ascii")
        )
        for name, value in fields.items()
    )

    if icc_bytes:
        # PNG iCCP: profile name, null, compression method 0,
        # followed by zlib-compressed ICC profile bytes.
        payload = (
            b"StampZ sRGB"
            + bytes((0, 0))
            + zlib.compress(bytes(icc_bytes))
        )
        chunks += make_chunk(b"iCCP", payload)

    offset = 8
    insertion = None

    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length

        if end > len(data):
            raise ImageSaveError("Invalid PNG chunk length")

        if kind == b"IDAT":
            insertion = offset
            break

        if kind == b"IEND":
            break

        offset = end

    if insertion is None:
        raise ImageSaveError("PNG image data chunk not found")

    updated = data[:insertion] + chunks + data[insertion:]
    filepath.write_bytes(updated)


def _verify_staged_image(path, expected_pixels, fmt,
                         is_16bit, encoding, raw_derived,
                         icc_bytes):
    """Validate staged pixels and required metadata before publication."""
    from PIL import Image
    import numpy as np

    if is_16bit:
        if fmt == "TIFF":
            import tifffile

            with tifffile.TiffFile(path) as tif:
                actual = tif.asarray()
                page = tif.pages[0]
                description = page.description or ""
                icc_tag = page.tags.get(34675)
                saved_icc = icc_tag.value if icc_tag else None

            assert (
                ("stampz linear raw" in description.lower())
                == (encoding == "linear")
            ), "TIFF encoding marker mismatch"

            if encoding in ("linear", "srgb"):
                assert (
                    ("raw-derived=yes" in description.lower())
                    == raw_derived
                ), "TIFF RAW provenance mismatch"

        elif fmt == "PNG":
            import cv2

            encoded = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if encoded is None:
                raise ImageSaveError("Staged PNG could not be decoded")

            code = (
                cv2.COLOR_BGRA2RGBA
                if expected_pixels.shape[2] == 4
                else cv2.COLOR_BGR2RGB
            )
            actual = cv2.cvtColor(encoded, code)

            with Image.open(path) as img:
                assert (
                    img.info.get("StampZ-Encoding") == encoding
                ), "PNG encoding metadata mismatch"
                assert (
                    img.info.get("StampZ-RAW-Derived")
                    == ("Yes" if raw_derived else "No")
                ), "PNG provenance metadata mismatch"
                saved_icc = img.info.get("icc_profile")

        else:
            raise ImageSaveError("Unsupported staged 16-bit format")

        if actual.dtype != np.uint16:
            raise ImageSaveError("Staged image lost 16-bit precision")

        if not np.array_equal(actual, expected_pixels):
            raise ImageSaveError("Staged image pixels differ from source")

        if icc_bytes:
            if saved_icc != icc_bytes:
                raise ImageSaveError("Staged ICC profile mismatch")
        elif saved_icc:
            raise ImageSaveError("Unexpected ICC profile in linear image")

    else:
        with Image.open(path) as img:
            img.load()
            actual = np.array(img)

        if not np.array_equal(actual, expected_pixels):
            raise ImageSaveError("Staged 8-bit image pixels differ")


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
        is_raw = getattr(image, '_stampz_is_raw', False)
        
        img = image.copy()
        
        # Re-attach 16-bit data after copy if it existed
        if has_16bit_data:
            img._stampz_16bit_data = sixteen_bit_data
        img._stampz_is_raw = is_raw

        # Preserve separate transparency mask for 16-bit crops.
        if hasattr(image, '_stampz_alpha_mask'):
            img._stampz_alpha_mask = image._stampz_alpha_mask.copy()

        # Preserve actual pixel encoding (linear or sRGB).
        if hasattr(image, '_stampz_16bit_encoding'):
            img._stampz_16bit_encoding = image._stampz_16bit_encoding
        
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

            # Stage output in the destination directory.
            # Retain the real extension for OpenCV and Pillow.
            fd, temporary_name = tempfile.mkstemp(
                prefix=".stampz_save_",
                suffix=filepath.suffix,
                dir=str(filepath.parent)
            )
            os.close(fd)
            temporary_path = Path(temporary_name)
            output_path = temporary_path
            
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
            
            # Construct high-precision output without modifying analytical RGB.
            if is_16bit:
                if (
                    not isinstance(img_array, np.ndarray)
                    or img_array.dtype != np.uint16
                    or img_array.ndim != 3
                    or img_array.shape[2] != 3
                    or img_array.shape[:2] != (img_to_save.height, img_to_save.width)
                ):
                    raise ImageSaveError(
                        "Invalid 16-bit RGB data: expected H x W x 3 uint16 "
                        "matching the cropped image dimensions."
                    )

                alpha_mask = getattr(
                    img_to_save, '_stampz_alpha_mask', None
                )

                if alpha_mask is not None:
                    alpha_mask = np.asarray(alpha_mask)

                    if (
                        alpha_mask.dtype != np.uint8
                        or alpha_mask.shape != img_array.shape[:2]
                    ):
                        raise ImageSaveError(
                            "Invalid crop transparency mask dimensions or type."
                        )

                    alpha_16bit = (
                        alpha_mask.astype(np.uint16) * 257
                    )

                    output_16bit = np.dstack(
                        (img_array, alpha_16bit)
                    )
                else:
                    output_16bit = img_array

                logger.info(
                    "Prepared 16-bit output: shape=%s dtype=%s",
                    output_16bit.shape,
                    output_16bit.dtype
                )

            # Resolve an ICC profile to embed. StampZ normalises every
            # loaded image to sRGB (see utils.image_processor.load_image),
            # so the saved file's pixels really are sRGB-coded — tagging
            # with sRGB stops macOS / browsers from re-interpreting them
            # under another assumed colour space.
            from .icc_profiles import get_save_icc_profile
            # ICC tagging follows actual pixel encoding, not RAW origin.
            encoding = getattr(
                img_to_save, '_stampz_16bit_encoding', None
            )

            if encoding == 'linear':
                icc_bytes = None
                logger.info(
                    "Linear 16-bit data: omitting sRGB ICC profile"
                )
            else:
                icc_bytes = get_save_icc_profile(img_to_save)
            
            if is_16bit and options.format == SaveFormat.TIFF:
                # Use tifffile to save 16-bit TIFF properly
                try:
                    import tifffile
                    logger.info("Saving as 16-bit TIFF using tifffile to preserve precision")
                    tifffile_kwargs = {"photometric": "rgb"}

                    if output_16bit.shape[2] == 4:
                        # Straight alpha: RGB values are not premultiplied.
                        tifffile_kwargs["extrasamples"] = "UNASSALPHA"

                    # Describe actual pixel encoding, not RAW provenance.
                    encoding = getattr(
                        img_to_save, '_stampz_16bit_encoding', None
                    )

                    # Record provenance independently of pixel encoding.
                    raw_derived = bool(
                        getattr(img_to_save, '_stampz_is_raw', False)
                    )

                    if encoding == 'linear':
                        tifffile_kwargs["description"] = (
                            "StampZ Linear RAW; Encoding=linear; "
                            f"RAW-derived={'Yes' if raw_derived else 'No'}"
                        )
                    elif encoding == 'srgb':
                        tifffile_kwargs["description"] = (
                            "StampZ RAW-derived; Encoding=sRGB; RAW-derived=Yes"
                            if raw_derived
                            else "StampZ; Encoding=sRGB; RAW-derived=No"
                        )
                    # Never silently omit an available ICC profile.
                    if icc_bytes:
                        tifffile.imwrite(
                            str(output_path), output_16bit,
                            iccprofile=icc_bytes, **tifffile_kwargs
                        )
                    else:
                        tifffile.imwrite(
                            str(output_path), output_16bit,
                            **tifffile_kwargs
                        )
                    logger.debug(f"16-bit TIFF save completed successfully")
                except ImportError as e:
                    logger.error("Cannot save 16-bit TIFF: tifffile unavailable")
                    raise ImageSaveError(
                        "16-bit TIFF saving requires tifffile. Image was not saved."
                    ) from e
                except Exception as e:
                    logger.exception("16-bit TIFF save failed")
                    raise ImageSaveError(
                        f"Failed to save 16-bit TIFF {filepath}: {e}"
                    ) from e
            elif is_16bit and options.format == SaveFormat.PNG:
                # OpenCV preserves 16 bits per RGB/alpha channel.
                try:
                    import cv2

                    if output_16bit.shape[2] == 4:
                        png_array = cv2.cvtColor(
                            output_16bit, cv2.COLOR_RGBA2BGRA
                        )
                    else:
                        png_array = cv2.cvtColor(
                            output_16bit, cv2.COLOR_RGB2BGR
                        )

                    success = cv2.imwrite(
                        str(output_path),
                        png_array
                    )

                    if not success:
                        raise ImageSaveError(
                            f"OpenCV failed to write 16-bit PNG: {filepath}"
                        )

                    # Preserve pixel encoding and RAW provenance.
                    _add_stampz_png_metadata(
                        output_path,
                        getattr(img_to_save, '_stampz_16bit_encoding', None),
                        bool(getattr(img_to_save, '_stampz_is_raw', False)),
                        icc_bytes=icc_bytes
                    )

                    logger.info(
                        "Saved 16-bit PNG with provenance: shape=%s",
                        output_16bit.shape
                    )

                except Exception as e:
                    logger.exception("16-bit PNG save failed")
                    raise ImageSaveError(
                        f"Failed to save 16-bit PNG {filepath}: {e}"
                    ) from e

            else:
                # Standard save operation for 8-bit images or non-TIFF formats.
                # PIL accepts icc_profile= for both PNG and TIFF and silently
                # ignores it for JPEG (which is not a save target here anyway).
                pil_kwargs = dict(options.save_kwargs)
                if icc_bytes:
                    pil_kwargs["icc_profile"] = icc_bytes
                img_to_save.save(str(output_path), **pil_kwargs)
                logger.debug(f"Save completed successfully")

            # Verify all pixels and required metadata before publication.
            _verify_staged_image(
                temporary_path,
                output_16bit if is_16bit else np.asarray(img_to_save),
                options.format,
                is_16bit,
                encoding,
                bool(getattr(img_to_save, '_stampz_is_raw', False)),
                icc_bytes
            )

            # Publish only after successful verification.
            os.replace(temporary_path, filepath)
            temporary_path = None
            
        except Exception as e:
            staged = locals().get("temporary_path")
            if staged is not None:
                try:
                    Path(staged).unlink(missing_ok=True)
                except OSError:
                    logger.exception("Could not remove temporary save file")

            if isinstance(e, ImageSaveError):
                raise

            raise ImageSaveError(
                f"Failed to save image {filepath}: {e}"
            ) from e
    
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

