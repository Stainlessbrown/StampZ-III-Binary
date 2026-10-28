"""
Image processing utilities for the StampZ application.
Handles loading, saving, and manipulating images using Pillow (PIL).
"""

from pathlib import Path
from typing import Tuple, Optional, Union
from PIL import Image, ImageTk
import logging
import numpy as np
# High-precision PNG decoding (16-bit RGB/RGBA)
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    cv2 = None
    HAS_OPENCV = False

# Import 16-bit TIFF loader
try:
    from .true_16bit_loader import load_16bit_tiff
    HAS_16BIT_LOADER = True
except ImportError:
    HAS_16BIT_LOADER = False

# Camera RAW support via rawpy (wraps LibRaw)
try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

# Supported camera RAW extensions
RAW_EXTENSIONS = {'.cr3', '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng'}

# Configure logging
logger = logging.getLogger(__name__)


def _apply_srgb_gamma_16bit(arr: np.ndarray) -> np.ndarray:
    """Convert a linear 16-bit uint16 array to sRGB gamma-encoded uint16.

    VueScan RAW TIFFs with ColorSpace=Uncalibrated store linear sensor
    values.  The rest of the StampZ pipeline (and the Lab conversion) expect
    sRGB gamma-encoded values, so we apply the standard IEC 61966-2-1 sRGB
    transfer function here.

    This is the inverse of the linearisation step inside any RGB→Lab
    converter, so the resulting Lab values match those from a standard
    gamma-encoded scan of the same stamp.
    """
    norm = arr.astype(np.float64) / 65535.0
    srgb = np.where(
        norm <= 0.0031308,
        12.92 * norm,
        1.055 * np.power(np.maximum(norm, 1e-12), 1.0 / 2.4) - 0.055,
    )
    return (np.clip(srgb, 0.0, 1.0) * 65535.0).astype(np.uint16)


def _is_vuescan_linear_tiff(file_path) -> bool:
    """Return True if this TIFF appears to be a VueScan linear RAW file.

    Checks for three simultaneous conditions that uniquely identify a
    VueScan 'Uncalibrated' RAW output:
      • Software TIFF tag contains 'VueScan'
      • EXIF ColorSpace tag is 0xFFFF (Uncalibrated)
      • No embedded ICC profile
    Standard scans (Epson Scan 2, SilverFast, Image Capture) fail at least
    one of these tests and are left unchanged.
    """
    try:
        import tifffile as _tf
        with _tf.TiffFile(str(file_path)) as tif:
            page = tif.pages[0]
            tags = page.tags

            # Tag 305: Software
            sw_tag = tags.get(305)
            software = str(sw_tag.value) if sw_tag is not None else ''

            # Tag 34665: EXIF IFD pointer — tifffile resolves it to a dict
            # containing the nested EXIF tags including ColorSpace (40961).
            # ColorSpace values: 1 = sRGB, 65535 (0xFFFF) = Uncalibrated.
            color_space = None
            exif_tag = tags.get(34665)
            if exif_tag is not None:
                exif_dict = exif_tag.value or {}
                color_space = exif_dict.get('ColorSpace')

            # Tag 700 / info dict: ICC profile presence
            has_icc = tags.get(34675) is not None  # Tag 34675 = ICC Profile

            return (
                'vuescan' in software.lower()
                and color_space == 65535
                and not has_icc
            )
    except Exception:
        return False

def _is_vuescan_linear_png(file_path) -> bool:
    """Return True if this PNG appears to be a VueScan linear RAW file."""
    try:
        with Image.open(file_path) as img:
            exif = img.getexif()

            # EXIF tag 305: Software
            software = str(exif.get(305, ''))

            # EXIF IFD tag 40961: ColorSpace
            # 65535 (0xFFFF) = Uncalibrated
            color_space = None
            try:
                exif_ifd = exif.get_ifd(34665)
                color_space = exif_ifd.get(40961)
            except Exception:
                pass

            # A normal color-managed PNG may contain an ICC profile.
            has_icc = 'icc_profile' in img.info

            return (
                'vuescan' in software.lower()
                and color_space == 65535
                and not has_icc
            )

    except Exception:
        return False


def _read_stampz_png_metadata(png_info):
    """Read explicit StampZ encoding and RAW provenance from PNG metadata."""
    encoding = png_info.get("StampZ-Encoding")
    raw_text = png_info.get("StampZ-RAW-Derived")

    if encoding is None and raw_text is None:
        return None

    if encoding not in ("linear", "srgb"):
        raise ImageLoadError("Invalid StampZ PNG encoding metadata")

    if raw_text not in ("Yes", "No"):
        raise ImageLoadError("Invalid StampZ PNG provenance metadata")

    return {
        "encoding": encoding,
        "is_raw": raw_text == "Yes",
    }



def _is_vuescan_raw_uncertain(file_path) -> bool:
    """Return True when a VueScan TIFF has ambiguous RAW metadata.

    Some VueScan versions, including 9.7.99, may omit the EXIF
    ColorSpace tag from a linear RAW TIFF. In that situation StampZ
    should not assume either RAW or non-RAW.
    """
    try:
        import tifffile as _tf

        with _tf.TiffFile(str(file_path)) as tif:
            page = tif.pages[0]
            tags = page.tags

            sw_tag = tags.get(305)
            software = str(sw_tag.value) if sw_tag is not None else ''

            # Only interested in VueScan-created TIFFs.
            if 'vuescan' not in software.lower():
                return False

            # An embedded ICC profile removes this particular ambiguity.
            if tags.get(34675) is not None:
                return False

            color_space = None
            exif_tag = tags.get(34665)

            if exif_tag is not None:
                try:
                    exif_dict = exif_tag.value or {}
                    color_space = exif_dict.get('ColorSpace')
                except Exception:
                    pass

            # Missing ColorSpace is the ambiguity encountered with
            # VueScan 9.7.99.
            return color_space is None

    except Exception:
        return False

def _is_stampz_linear_raw_tiff(file_path) -> bool:
    """Return True if this TIFF was saved by StampZ from linear RAW data."""
    try:
        import tifffile as _tf
        with _tf.TiffFile(str(file_path)) as tif:
            page = tif.pages[0]
            desc_tag = page.tags.get(270)  # ImageDescription
            description = str(desc_tag.value) if desc_tag is not None else ''

            return 'stampz linear raw' in description.lower()
    except Exception:
        return False


def _is_stampz_raw_derived_tiff(file_path) -> bool:
    """Identify explicit StampZ RAW-derived TIFF provenance."""
    try:
        import tifffile

        with tifffile.TiffFile(str(file_path)) as tif:
            description = tif.pages[0].description or ""

        return "raw-derived=yes" in description.lower()

    except Exception:
        return False


class ImageLoadError(Exception):
    """Exception raised when image loading fails."""
    pass

class ImageSaveError(Exception):
    """Exception raised when image saving fails."""
    pass

def load_image(file_path: Union[str, Path], display_only: bool = False) -> Tuple[Image.Image, dict]:
    """
    Load an image file and return a PIL Image object with proper color profile handling.
    For TIFF files, attempts to preserve 16-bit precision when possible.
    
    Args:
        file_path: Path to the image file to load
        
    Returns:
        Tuple of (PIL Image object converted to sRGB color space, metadata dict)
        
    Raises:
        ImageLoadError: If the file cannot be loaded or is not a valid image
    """
    metadata = {
        'format_info': '',
        'precision_preserved': False,
        'original_bit_depth': None,        # bits per channel if known (int or list)
        'samples_per_pixel': None,         # channels count if known
        'photometric': None,               # e.g., 'RGB', 'GRAY'
        'icc_profile_name': None,          # if embedded
    }
    
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise ImageLoadError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()
        supported = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'} | RAW_EXTENSIONS
        if suffix not in supported:
            raise ImageLoadError(f"Unsupported file format: {file_path.suffix}")

        # ── Camera RAW files (CR3, CR2, NEF, ARW …) ────────────────────
        if suffix in RAW_EXTENSIONS:
            if not HAS_RAWPY:
                raise ImageLoadError(
                    "rawpy is required to open camera RAW files. "
                    "Install it with: pip install rawpy"
                )
            try:
                with rawpy.imread(str(file_path)) as raw:
                    # Process with controlled settings for colorimetric accuracy:
                    # • Camera-recorded white balance (consistent with stamp shots)
                    # • No auto-brightness adjustment
                    # • 16-bit output, sRGB gamma — matches scanner TIFF pipeline
                    img_array = raw.postprocess(
                        use_camera_wb=True,
                        no_auto_bright=True,
                        output_bps=16,
                        gamma=(2.222, 4.5),   # sRGB standard
                    )
                # img_array is uint16 RGB (H × W × 3)
                img_array_8bit = (img_array / 65535.0 * 255.0).astype(np.uint8)
                image = Image.fromarray(img_array_8bit)
                image._stampz_16bit_data = img_array
                image._stampz_source_file = str(file_path)
                image._stampz_is_raw = bool(metadata.get('is_raw', False))
                metadata.update({
                    'format_info': f"Camera RAW ({suffix.upper()}) loaded via rawpy — 16-bit, sRGB",
                    'precision_preserved': True,
                    'original_bit_depth': 16,
                    'samples_per_pixel': 3,
                    'photometric': 'RGB',
                    'color_profile': 'sRGB (rawpy postprocess)',
                    'is_raw': True,
                })
                logger.info(f"Loaded camera RAW {suffix.upper()} via rawpy: {file_path}")
                return image, metadata
            except Exception as e:
                raise ImageLoadError(f"Failed to load RAW file {file_path}: {e}")

        # Preserve 16-bit RGB PNG precision independently of display depth.
        if suffix == '.png' and HAS_OPENCV:
            import io
            from PIL import ImageCms

            with Image.open(file_path) as png_info:
                icc_bytes = png_info.info.get('icc_profile')
                png_info_dict = dict(png_info.info)

            # Prefer explicit StampZ encoding and provenance metadata.
            stampz_png = _read_stampz_png_metadata(png_info_dict)

            if stampz_png is not None:
                is_linear_raw = stampz_png["encoding"] == "linear"
                raw_provenance = stampz_png["is_raw"]
            else:
                is_linear_raw = _is_vuescan_linear_png(file_path)
                raw_provenance = is_linear_raw

            is_srgb = False
            profile_description = None

            if icc_bytes:
                try:
                    profile = ImageCms.ImageCmsProfile(
                        io.BytesIO(icc_bytes)
                    )
                    profile_description = ImageCms.getProfileDescription(
                        profile
                    )
                    is_srgb = 'srgb' in profile_description.lower()
                except Exception as exc:
                    logger.warning(
                        f"Could not identify PNG ICC profile: {exc}"
                    )
            else:
                # No ICC profile: ordinary PNGs are provisionally
                # interpreted as sRGB, unless identified as linear RAW.
                is_srgb = not is_linear_raw

            # Non-sRGB embedded profiles require a separate
            # color-managed high-bit-depth conversion.
            if is_srgb or is_linear_raw:
                png_array = cv2.imread(
                    str(file_path), cv2.IMREAD_UNCHANGED
                )

                if (
                    png_array is not None
                    and png_array.dtype == np.uint16
                    and png_array.ndim == 3
                    and png_array.shape[2] in (3, 4)
                ):
                    # Separate alpha before any RGB gamma processing.
                    if png_array.shape[2] == 4:
                        rgba16 = cv2.cvtColor(
                            png_array, cv2.COLOR_BGRA2RGBA
                        )
                        rgb16 = rgba16[:, :, :3].copy()
                        alpha16 = rgba16[:, :, 3].copy()
                    else:
                        rgb16 = cv2.cvtColor(
                            png_array, cv2.COLOR_BGR2RGB
                        )
                        alpha16 = None

                    if is_linear_raw and not display_only:
                        rgb16 = _apply_srgb_gamma_16bit(rgb16)

                    rgb8 = np.round(
                        rgb16.astype(np.float64) / 257.0
                    ).astype(np.uint8)

                    # Preserve the original 16-bit analytical RGB.
                    # Alpha is separate and must never receive gamma correction.
                    image = Image.fromarray(rgb8, mode='RGB')

                    if alpha16 is not None:
                        alpha8 = np.round(
                            alpha16.astype(np.float64) / 257.0
                        ).astype(np.uint8)

                        image.putalpha(
                            Image.fromarray(alpha8, mode='L')
                        )

                        image._stampz_alpha_mask = alpha8

                    image._stampz_16bit_data = rgb16
                    image._stampz_16bit_encoding = (
                        'linear'
                        if is_linear_raw and display_only
                        else 'srgb'
                    )
                    image._stampz_source_file = str(file_path)
                    image._stampz_is_raw = raw_provenance

                    metadata.update({
                        'format_info': (
                            'VueScan linear RAW PNG — 16-bit preserved'
                            if is_linear_raw
                            else '16-bit RGB PNG — full precision preserved'
                        ),
                        'precision_preserved': True,
                        'original_bit_depth': 16,
                        'samples_per_pixel': 3,
                        'photometric': 'RGB',
                        'data_type': 'uint16',
                        'value_range': (
                            int(rgb16.min()), int(rgb16.max())
                        ),
                        'icc_profile_name': profile_description,
                        'color_profile': (
                            'Uncalibrated linear RAW'
                            if is_linear_raw
                            else 'Embedded sRGB'
                            if icc_bytes
                            else 'Assumed sRGB (no ICC profile)'
                        ),
                        'is_raw': raw_provenance,
                        'linear_gamma_corrected': (
                            is_linear_raw and not display_only
                        ),
                    })

                    logger.info(
                        f"Loaded 16-bit PNG with full precision: "
                        f"{file_path}, RAW={is_linear_raw}, "
                        f"display_only={display_only}"
                    )
                    return image, metadata

        # Handle TIFF files with 16-bit loader if available
        if file_path.suffix.lower() in ['.tif', '.tiff'] and HAS_16BIT_LOADER:
            try:
                img_array, tiff_metadata = load_16bit_tiff(str(file_path), preserve_16bit=True)
                
                # Update our metadata
                metadata.update({
                    'format_info': f"TIFF loaded with {'16-bit' if tiff_metadata.get('true_16bit') else '8-bit'} precision",
                    'precision_preserved': tiff_metadata.get('true_16bit', False),
                    'original_bit_depth': tiff_metadata.get('bits_per_sample'),
                    'data_type': tiff_metadata.get('data_type'),
                    'value_range': tiff_metadata.get('value_range'),
                    'samples_per_pixel': tiff_metadata.get('samples_per_pixel'),
                    'photometric': tiff_metadata.get('photometric')
                })
                
                # Convert numpy array to PIL Image
                if tiff_metadata.get('true_16bit', False):
                    # Separate alpha before any color/gamma processing.
                    # Keep the analytical data as three-channel RGB.
                    if img_array.ndim == 3 and img_array.shape[2] == 4:
                        alpha16 = img_array[:, :, 3].copy()
                        img_array = img_array[:, :, :3].copy()
                    else:
                        alpha16 = None
                    # Detect VueScan linear RAW and apply sRGB gamma so the
                    # rest of the pipeline (Lab conversion, calibration) sees
                    # correctly gamma-encoded values.
                    is_vuescan_linear = _is_vuescan_linear_tiff(file_path)
                    is_stampz_linear = _is_stampz_linear_raw_tiff(file_path)
                    is_linear = is_vuescan_linear or is_stampz_linear

                    # RAW provenance is independent of pixel encoding.
                    is_stampz_raw_derived = _is_stampz_raw_derived_tiff(
                        file_path
                    )
                    raw_provenance = is_linear or is_stampz_raw_derived
                    metadata['is_raw'] = raw_provenance

                    # Flag VueScan TIFFs whose RAW status cannot be determined reliably.
                    vuescan_raw_uncertain = _is_vuescan_raw_uncertain(file_path)
                    metadata['raw_detection_uncertain'] = vuescan_raw_uncertain

                    linear_source = "VueScan" if is_vuescan_linear else "StampZ-derived"

                    if is_linear:
                        metadata['is_raw'] = True

                        if display_only:
                            # Preserve native linear VueScan RAW values for display.
                            # The optional Display Bridge will handle perceptual rendering.
                            metadata['format_info'] = (
                                f"{linear_source} linear RAW TIFF — native linear display"
                            )
                            
                            metadata['linear_gamma_corrected'] = False
                            logger.info(
                                f"{linear_source} linear RAW detected, native display preserved: {file_path}"
                            )
                        else:
                            # Analysis path: retain existing sRGB gamma treatment.
                            img_array = _apply_srgb_gamma_16bit(img_array)
                            metadata['format_info'] = (
                                f"{linear_source} linear RAW TIFF — sRGB gamma applied "
                                "(Uncalibrated → sRGB)"
                            )
                            metadata['linear_gamma_corrected'] = True
                            logger.info(
                                f"{linear_source} linear RAW detected, sRGB gamma applied: {file_path}"
                            )
                    else:
                        metadata['linear_gamma_corrected'] = False

                    # Scale to 8-bit for display; preserve 16-bit for analysis
                    img_array_8bit = (img_array / 65535.0 * 255.0).astype(np.uint8)
                    image = Image.fromarray(img_array_8bit)

                    # Restore transparency without altering analytical RGB.
                    if alpha16 is not None:
                        alpha8 = np.round(
                            alpha16.astype(np.float64) / 257.0
                        ).astype(np.uint8)

                        image.putalpha(
                            Image.fromarray(alpha8, mode='L')
                        )

                        image._stampz_alpha_mask = alpha8

                    image._stampz_16bit_data = img_array
                    image._stampz_16bit_encoding = (
                        "linear"
                        if is_linear and not metadata.get('linear_gamma_corrected', False)
                        else "srgb"
                    )                   
                    image._stampz_source_file = str(file_path)
                    image._stampz_is_raw = raw_provenance
                    logger.info(f"Loaded 16-bit TIFF with full precision, attached _stampz_16bit_data: {file_path}")
                else:
                    image = Image.fromarray(img_array)
                    logger.info(f"Loaded TIFF as 8-bit: {file_path}")
                    
            except Exception as e:
                logger.warning(f"16-bit TIFF loading failed, falling back to PIL: {e}")
                metadata['format_info'] = "TIFF loaded with PIL (may be downsampled)"
                image = Image.open(file_path)
                image.load()
        else:
            # Use PIL for non-TIFF files or when 16-bit loader not available
            image = Image.open(file_path)
            image.load()  # Load image data immediately
            
            # Set format info for non-TIFF files
            if file_path.suffix.lower() == '.png':
                if _is_vuescan_linear_png(file_path):
                    metadata['is_raw'] = True
                    image._stampz_is_raw = True

                    if display_only:
                        # Preserve native linear VueScan RAW values for display.
                        metadata['format_info'] = (
                            "VueScan linear RAW PNG — native linear display"
                        )
                        metadata['linear_gamma_corrected'] = False
                        logger.info(
                            f"VueScan linear RAW PNG detected, "
                            f"native display preserved: {file_path}"
                        )
                    else:
                        # Analysis path: apply linear -> sRGB gamma,
                        # matching the VueScan RAW TIFF analysis path.
                        arr = np.asarray(image).astype(np.float64) / 255.0
                        srgb = np.where(
                            arr <= 0.0031308,
                            12.92 * arr,
                            1.055 * np.power(
                                np.maximum(arr, 1e-12), 1.0 / 2.4
                            ) - 0.055
                        )
                        arr_8bit = (
                            np.clip(srgb, 0.0, 1.0) * 255.0
                        ).astype(np.uint8)

                        image = Image.fromarray(arr_8bit, mode='RGB')
                        image._stampz_is_raw = True

                        metadata['format_info'] = (
                            "VueScan linear RAW PNG — sRGB gamma applied"
                        )
                        metadata['linear_gamma_corrected'] = True

                        logger.info(
                            f"VueScan linear RAW PNG detected, "
                            f"sRGB gamma applied: {file_path}"
                        )
                else:
                    metadata['format_info'] = "PNG loaded (lossless, good for color analysis)"
            elif file_path.suffix.lower() in ['.jpg', '.jpeg']:
                metadata['format_info'] = "JPEG loaded (compressed, not ideal for precise color analysis)"
            elif file_path.suffix.lower() in ['.tif', '.tiff']:
                metadata['format_info'] = "TIFF loaded with PIL (install 'tifffile' for 16-bit support)"

        logger.info(f"DEBUG DISPLAY: is_raw={metadata.get('is_raw')}, display_only={display_only}")
        logger.info(f"DEBUG DISPLAY: image.info={image.info}")

        # Handle color profile conversion to ensure consistent sRGB color space
        if hasattr(image, 'info') and 'icc_profile' in image.info:
            logger.info(f"Converting image with embedded color profile to sRGB: {file_path}")
            try:
                # Convert to sRGB using the embedded ICC profile
                from PIL import ImageCms
                
                # Create sRGB profile
                srgb_profile = ImageCms.createProfile('sRGB')
                
                # Get embedded profile
                input_profile = ImageCms.ImageCmsProfile(image.info['icc_profile'])
                try:
                    metadata['icc_profile_name'] = ImageCms.getProfileName(input_profile)
                except Exception:
                    metadata['icc_profile_name'] = 'Embedded ICC'
                
                # Create transformation — preserve alpha if present
                if image.mode == 'RGBA':
                    alpha = image.split()[3]
                    rgb_img = image.convert('RGB')
                    transform = ImageCms.buildTransform(input_profile, srgb_profile, 'RGB', 'RGB')
                    rgb_img = ImageCms.applyTransform(rgb_img, transform)
                    rgb_img.putalpha(alpha)
                    image = rgb_img
                else:
                    transform = ImageCms.buildTransform(input_profile, srgb_profile, 'RGB', 'RGB')
                    image = ImageCms.applyTransform(image, transform)
                
                logger.info(f"Successfully converted to sRGB color space")
                metadata['color_profile'] = "Converted from embedded profile to sRGB"
                
            except Exception as e:
                logger.warning(f"Failed to convert color profile, using image as-is: {e}")
                # Fall back to converting to RGB without profile transformation
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGB')
                metadata['color_profile'] = "Profile conversion failed, using as RGB"
        else:
            # No embedded profile, ensure RGB or RGBA mode
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')
            metadata['color_profile'] = "No embedded profile, assumed sRGB"
        
        # Derive fallback bit-depth/channels if missing
        try:
            metadata.setdefault('samples_per_pixel', len(image.getbands()))
            if metadata.get('original_bit_depth') is None:
                # Infer from mode
                if image.mode in ('I;16', 'I;16B', 'I;16L'):
                    metadata['original_bit_depth'] = 16
                elif image.mode in ('I', 'F'):
                    # 32-bit int or 32-bit float; treat as 32
                    metadata['original_bit_depth'] = 32
                else:
                    metadata['original_bit_depth'] = 8
            metadata.setdefault('photometric', image.mode)
        except Exception:
            pass
                
        return image, metadata
        
    except (OSError, IOError) as e:
        raise ImageLoadError(f"Failed to load image {file_path}: {str(e)}")

def copy_image_preserve_16bit(image: Image.Image) -> Image.Image:
    """
    Copy a PIL Image while preserving the _stampz_16bit_data attribute.
    
    PIL's .copy() method does NOT preserve custom attributes, so we need
    this helper to maintain 16-bit data through operations like leveling.
    
    Args:
        image: PIL Image object to copy
        
    Returns:
        Copied PIL Image with _stampz_16bit_data preserved if present
    """
    copied = image.copy()
    
    # Preserve 16-bit data if present
    if hasattr(image, '_stampz_16bit_data'):
        copied._stampz_16bit_data = image._stampz_16bit_data.copy()  # Copy numpy array too
        logger.debug("Preserved _stampz_16bit_data during image copy")
    
    # Preserve source file info if present
    if hasattr(image, '_stampz_source_file'):
        copied._stampz_source_file = image._stampz_source_file

    # Preserve RAW provenance if present
    if hasattr(image, '_stampz_is_raw'):
        copied._stampz_is_raw = image._stampz_is_raw

    # Preserve crop transparency separately from analytical RGB.
    if hasattr(image, '_stampz_alpha_mask'):
        copied._stampz_alpha_mask = image._stampz_alpha_mask.copy()

    # Preserve actual 16-bit pixel encoding.
    if hasattr(image, '_stampz_16bit_encoding'):
        copied._stampz_16bit_encoding = image._stampz_16bit_encoding

    return copied


# Save functionality moved to save_as.py

def scale_image(
    image: Image.Image,
    max_size: Tuple[int, int],
    preserve_aspect: bool = True
) -> Image.Image:
    """
    Scale an image to fit within the specified dimensions while optionally preserving aspect ratio.
    
    Args:
        image: PIL Image object to scale
        max_size: (width, height) tuple specifying maximum dimensions
        preserve_aspect: If True, maintain aspect ratio while scaling
        
    Returns:
        Scaled PIL Image object
    """
    if not isinstance(max_size, tuple) or len(max_size) != 2:
        raise ValueError("max_size must be a (width, height) tuple")
        
    if preserve_aspect:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image
    else:
        return image.resize(max_size, Image.Resampling.LANCZOS)

def create_tk_image(image: Image.Image) -> ImageTk.PhotoImage:
    """
    Convert a PIL Image to a Tkinter-compatible PhotoImage.
    
    Args:
        image: PIL Image object to convert
        
    Returns:
        Tkinter-compatible PhotoImage object
    """
    return ImageTk.PhotoImage(image)

def get_image_dimensions(image: Image.Image) -> Tuple[int, int]:
    """
    Get the dimensions of an image.
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple of (width, height)
    """
    return image.size

def crop_image(
    image: Image.Image,
    vertices: list[Tuple[int, int]]
) -> Optional[Image.Image]:
    """
    Crop an image using a polygon defined by vertices.
    
    Args:
        image: PIL Image object to crop
        vertices: List of (x, y) tuples defining the crop polygon
        
    Returns:
        Cropped PIL Image object, or None if cropping fails
        
    Note:
        This is a placeholder for the actual implementation that will be
        developed as part of the polygon cropping functionality.
    """
    # TODO: Implement polygon cropping
    # This will be implemented when we develop the geometry utilities
    pass

