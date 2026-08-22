#!/usr/bin/env python3
"""
Camera Calibration Module for StampZ

Provides colour normalisation for camera-based stamp capture (Canon EOS R50
or any tethered RAW camera) using the StampZ camera calibration target.

The camera target is a reduced-size version of the scanner target (6.5 mm
square patches, printed at a photo lab) designed to fit within the macro
lens field of view at the working distance used for stamp photography.
The patch layout and colour content are identical to the scanner target;
only the physical size and the reference Lab values (measured from that
specific print) differ.

Grid layout (4 columns × 5 rows, 20 patches):
    Row 0: Black | 25% Gray | 50% Gray | 75% Gray
    Row 1: White | Buff     | Brown    | Orange
    Row 2: Red   | Rose     | Fuschia  | Blue
    Row 3: Violet| Mauve    | Green    | Yellow
    Row 4: Ultramarine | Bronz | Cyan/Teal | Yellow-Green

Black patch must be at top-left in the captured image.

Spectrometer reference values measured August 2026.
"""

import logging
from typing import Optional, Tuple

from .scanner_calibration import (
    ScannerCalibration,
    PATCH_MAP,
    set_active_calibration,
    get_active_calibration,
    apply_calibration_to_rgb,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Camera-target spectrometer Lab values
# Same patch layout as the scanner target; different print → different values.
# ---------------------------------------------------------------------------

CAMERA_PATCH_LAB = {
    "Black":        ( 0.00,   0.00,   0.00),
    "25% Gray":     (24.53,   0.19,  -1.58),
    "50% Gray":     (46.35,  -0.47,  -1.33),
    "75% Gray":     (69.83,  -0.81,  -1.55),
    "White":        (93.86,  -1.59,  -3.42),
    "Buff":         (85.95,   2.53,   9.74),
    "Brown":        (35.96,  24.56,  44.97),
    "Orange":       (52.91,  35.53,  55.16),
    "Red":          (42.96,  67.16,  58.81),
    "Rose":         (44.77,  73.28,  -6.06),
    "Fuschia":      (40.97,  70.29,  -9.47),
    "Blue":         (53.28,  -4.99, -39.64),
    "Violet":       (61.49,  21.95, -36.74),
    "Mauve":        (72.59,  18.23, -25.11),
    "Green":        (34.10, -29.50,  38.96),
    "Yellow":       (69.34,  -0.56,  51.46),
    "Ultramarine":  (29.57,  13.85, -38.60),
    "Bronz":        (54.34,  17.66,  39.22),
    "Cyan/Teal":    (54.51, -25.52, -11.11),
    "Yellow-Green": (67.13, -53.17,  58.70),
}


class CameraCalibration(ScannerCalibration):
    """Calibration for camera-based stamp capture using the small camera target.

    Subclasses ScannerCalibration, inheriting all patch-detection, correction
    fitting, save/load, and apply logic.  Only the reference Lab values and
    the profile-type label differ.
    """

    # Grid dimensions are identical to the scanner target
    GRID_COLS = 4
    GRID_ROWS = 5

    # Override the module-level PATCH_LAB with camera-specific measurements
    _PATCH_LAB_OVERRIDE = CAMERA_PATCH_LAB

    def __init__(self):
        super().__init__()
        # Patch the module-level PATCH_LAB used by the parent class methods
        # so that ΔE computations use the camera spectrometer values.
        import utils.scanner_calibration as _sc
        self._original_patch_lab = _sc.PATCH_LAB
        _sc.PATCH_LAB = CAMERA_PATCH_LAB

    def __del__(self):
        """Restore the module-level PATCH_LAB when this object is destroyed."""
        try:
            import utils.scanner_calibration as _sc
            _sc.PATCH_LAB = self._original_patch_lab
        except Exception:
            pass

    def save_profile(self, path: str, name: str = "",
                     scanner_info: str = "") -> bool:
        """Save camera calibration profile (type tag differs from scanner)."""
        import utils.scanner_calibration as _sc
        _sc.PATCH_LAB = CAMERA_PATCH_LAB          # ensure correct values
        result = super().save_profile(path, name, scanner_info)
        # Patch the saved JSON to indicate camera type
        if result:
            try:
                import json, os
                with open(path) as f:
                    data = json.load(f)
                data['type'] = 'StampZ Camera Calibration Profile'
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.warning(f"Could not update profile type tag: {e}")
        return result


# ---------------------------------------------------------------------------
# Module-level active camera calibration (mirrors scanner_calibration pattern)
# ---------------------------------------------------------------------------

_active_camera_calibration: Optional[CameraCalibration] = None


def get_active_camera_calibration() -> Optional[CameraCalibration]:
    """Return the currently active camera calibration, or None."""
    return _active_camera_calibration


def set_active_camera_calibration(
        calibration: Optional[CameraCalibration]) -> None:
    """Set the active camera calibration."""
    global _active_camera_calibration
    _active_camera_calibration = calibration
    if calibration:
        logger.info("Camera calibration activated")
    else:
        logger.info("Camera calibration deactivated")


def apply_camera_calibration_to_rgb(
        rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Apply active camera calibration to an RGB tuple.

    Returns uncorrected values if no camera calibration is active.
    """
    if _active_camera_calibration and _active_camera_calibration.is_valid:
        return _active_camera_calibration.apply_correction(rgb)
    return rgb
