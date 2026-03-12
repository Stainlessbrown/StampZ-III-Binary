#!/usr/bin/env python3
"""
Scanner Calibration Module for StampZ

Provides scanner normalization using the StampZ printed color target.
The target is a 3×4 grid of 12 patches (11 unique colors + 1 duplicate White)
selected for accurate reproduction by photo-lab printers.

Maps scanner RGB output to a standard reference color space so that color libraries
and measurements are comparable across different scanners.

Correction model: per-channel linear fit from in-gamut patches
(scanned values → digital reference values).
"""

import json
import os
import math
import logging
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# Module-level active calibration instance
_active_calibration: Optional['ScannerCalibration'] = None


def get_active_calibration() -> Optional['ScannerCalibration']:
    """Get the currently active scanner calibration, or None if not calibrated."""
    return _active_calibration


def set_active_calibration(calibration: Optional['ScannerCalibration']) -> None:
    """Set the active scanner calibration."""
    global _active_calibration
    _active_calibration = calibration
    if calibration:
        logger.info("Scanner calibration activated")
    else:
        logger.info("Scanner calibration deactivated")


def apply_calibration_to_rgb(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Apply active calibration to an RGB tuple. Returns uncorrected values if no calibration active.
    
    Args:
        rgb: RGB values as (r, g, b) floats 0-255
        
    Returns:
        Corrected RGB values as (r, g, b) floats 0-255
    """
    if _active_calibration and _active_calibration.is_valid:
        return _active_calibration.apply_correction(rgb)
    return rgb


# Patch layout for the StampZ calibration target (v1.1 — 3×4 grid)
# Maps grid position (row, col) in the scanned image to (name, digital_rgb)
# Target is oriented with Black at top-left when scanned
# 12 cells: 11 unique colors selected for photo-lab gamut + 1 duplicate White
PATCH_MAP = {
    (0, 0): ("Black",         (0x17, 0x16, 0x15)),
    (0, 1): ("Rose",          (0xFF, 0x00, 0x7F)),
    (0, 2): ("Light Gray",    (0xD0, 0xCF, 0xCF)),
    (1, 0): ("Buff",          (0xFF, 0xE8, 0xCB)),
    (1, 1): ("White",         (0xFF, 0xFF, 0xFF)),
    (1, 2): ("Violet",        (0xBF, 0x7F, 0xFF)),
    (2, 0): ("Brown",         (0x96, 0x4B, 0x00)),
    (2, 1): ("White 2",       (0xFF, 0xFF, 0xFF)),
    (2, 2): ("Lavender",      (0xE4, 0xAF, 0xF3)),
    (3, 0): ("Red",           (0xFF, 0x00, 0x00)),
    (3, 1): ("Magenta",       (0xE5, 0x00, 0x7C)),
    (3, 2): ("Dark Green",    (0x00, 0x63, 0x00)),
}

# Ordered list of patch names for consistent iteration
PATCH_NAMES = [name for _, (name, _) in sorted(PATCH_MAP.items())]


@dataclass
class PatchResult:
    """Result of detecting and measuring a single color patch."""
    name: str
    grid_position: Tuple[int, int]
    digital_rgb: Tuple[int, int, int]       # Known reference value
    scanned_rgb: Tuple[float, float, float]  # Measured from user's scan
    corrected_rgb: Optional[Tuple[float, float, float]] = None  # After correction
    delta_e_before: float = 0.0              # ΔE before correction
    delta_e_after: float = 0.0               # ΔE after correction


class ScannerCalibration:
    """Scanner calibration using the StampZ color target.
    
    Uses per-channel 2nd-order polynomial correction to map scanner RGB
    to the standard reference color space.
    """
    
    def __init__(self):
        self.reference_data: Optional[Dict] = None
        self.patch_results: List[PatchResult] = []
        self.correction_coefficients: Optional[Dict[str, List[float]]] = None
        self.is_valid: bool = False
        self.profile_name: str = ""
        self.created_date: str = ""
        self.scanner_info: str = ""
    
    def load_reference(self, reference_path: Optional[str] = None) -> bool:
        """Load reference values from JSON file.
        
        Args:
            reference_path: Path to reference_values.json. If None, uses bundled default.
            
        Returns:
            True if loaded successfully
        """
        if reference_path is None:
            from .path_utils import get_calibration_dir
            reference_path = os.path.join(get_calibration_dir(), "reference_values.json")
        
        try:
            with open(reference_path, 'r') as f:
                self.reference_data = json.load(f)
            logger.info(f"Loaded reference data from {reference_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load reference data: {e}")
            return False
    
    # Expected grid dimensions
    GRID_COLS = 3
    GRID_ROWS = 4
    
    def detect_patches(self, image_path: str) -> List[PatchResult]:
        """Auto-detect the color patches from a scanned target image.
        
        Args:
            image_path: Path to the scanned target TIFF/image
            
        Returns:
            List of PatchResult objects with scanned RGB values
        """
        try:
            img = Image.open(image_path)
            arr = np.array(img)
            if arr.ndim == 2:
                # Grayscale — can't calibrate
                raise ValueError("Image is grayscale. RGB image required for calibration.")
            if arr.shape[2] == 4:
                # RGBA — drop alpha
                arr = arr[:, :, :3]
            
            h, w = arr.shape[:2]
            gray = np.mean(arr.astype(float), axis=2)
            
            # Find patch grid using brightness profile analysis
            col_ranges = self._find_patch_ranges(
                np.mean(gray[h // 4:3 * h // 4, :], axis=0)
            )
            row_ranges = self._find_patch_ranges(
                np.mean(gray[:, w // 4:3 * w // 4], axis=1)
            )
            
            # Fallback: very light patches (especially white) can blend with
            # white paper and disappear from threshold-based detection.
            # If we detect outer ranges but miss interior ones, infer a
            # regular grid from the first/last detected centers.
            if len(col_ranges) != self.GRID_COLS and len(col_ranges) >= 2:
                inferred_cols = self._interpolate_grid_ranges(
                    col_ranges, self.GRID_COLS, axis_size=w
                )
                if len(inferred_cols) == self.GRID_COLS:
                    col_ranges = inferred_cols
            if len(row_ranges) != self.GRID_ROWS and len(row_ranges) >= 2:
                inferred_rows = self._interpolate_grid_ranges(
                    row_ranges, self.GRID_ROWS, axis_size=h
                )
                if len(inferred_rows) == self.GRID_ROWS:
                    row_ranges = inferred_rows
            
            if len(col_ranges) != self.GRID_COLS or len(row_ranges) != self.GRID_ROWS:
                raise ValueError(
                    f"Expected {self.GRID_COLS} columns × {self.GRID_ROWS} rows of patches, "
                    f"found {len(col_ranges)} × {len(row_ranges)}. "
                    f"Check that the target is properly cropped and oriented "
                    f"(Black patch top-left)."
                )
            
            # Extract average color from center 60% of each patch
            self.patch_results = []
            for ri, (ry1, ry2) in enumerate(row_ranges):
                for ci, (cx1, cx2) in enumerate(col_ranges):
                    pos = (ri, ci)
                    if pos not in PATCH_MAP:
                        continue
                    
                    name, digital_rgb = PATCH_MAP[pos]
                    
                    # Inset 20% from each edge to avoid border effects
                    margin_x = int((cx2 - cx1) * 0.2)
                    margin_y = int((ry2 - ry1) * 0.2)
                    patch = arr[ry1 + margin_y:ry2 - margin_y,
                                cx1 + margin_x:cx2 - margin_x]
                    
                    mean_rgb = np.mean(patch.reshape(-1, 3), axis=0)
                    
                    result = PatchResult(
                        name=name,
                        grid_position=pos,
                        digital_rgb=digital_rgb,
                        scanned_rgb=(float(mean_rgb[0]), float(mean_rgb[1]), float(mean_rgb[2])),
                    )
                    # Calculate pre-correction ΔE
                    result.delta_e_before = self._delta_e_rgb(
                        result.scanned_rgb, result.digital_rgb
                    )
                    self.patch_results.append(result)
            
            logger.info(f"Detected {len(self.patch_results)} patches from {image_path}")
            return self.patch_results
            
        except Exception as e:
            logger.error(f"Failed to detect patches: {e}")
            raise
    
    # Maximum pre-correction ΔE for a patch to be included in the fit.
    # Patches above this threshold are outside the printer's reproducible gamut
    # and would skew the correction model. They are still detected and displayed
    # but do not influence the correction coefficients.
    GAMUT_THRESHOLD = 50.0
    
    def compute_correction(self) -> Dict[str, Any]:
        """Compute per-channel linear correction from detected patches.
        
        Uses 1st-order (linear) fit per channel: corrected = a*x + b
        where x is the scanned value and corrected maps to the digital reference.
        
        Patches with pre-correction ΔE above GAMUT_THRESHOLD are excluded from
        the fit — they represent printer gamut limitations, not scanner error.
        All patches still receive corrected values for display purposes.
        
        Returns:
            Dict with correction quality metrics
        """
        if not self.patch_results:
            raise ValueError("No patches detected. Run detect_patches() first.")
        
        # Filter to patches within printer gamut for the fit
        fit_patches = [p for p in self.patch_results
                       if p.delta_e_before <= self.GAMUT_THRESHOLD]
        excluded_patches = [p for p in self.patch_results
                           if p.delta_e_before > self.GAMUT_THRESHOLD]
        
        if len(fit_patches) < 3:
            raise ValueError(
                f"Only {len(fit_patches)} patches within gamut threshold "
                f"(ΔE ≤ {self.GAMUT_THRESHOLD}). Need at least 3 for a fit."
            )
        
        logger.info(
            f"Using {len(fit_patches)} of {len(self.patch_results)} patches for fit "
            f"({len(excluded_patches)} excluded, ΔE > {self.GAMUT_THRESHOLD})"
        )
        
        # Build paired data arrays from in-gamut patches only
        scanned = np.array([p.scanned_rgb for p in fit_patches])
        reference = np.array([p.digital_rgb for p in fit_patches])
        
        coefficients = {}
        channel_names = ['R', 'G', 'B']
        
        for ch_idx, ch_name in enumerate(channel_names):
            x = scanned[:, ch_idx]
            y = reference[:, ch_idx]
            
            # Fit 1st-order (linear): y = a*x + b
            coeffs = np.polyfit(x, y, 1)
            coefficients[ch_name] = coeffs.tolist()
        
        self.correction_coefficients = coefficients
        self.correction_order = 1
        self.is_valid = True
        self.created_date = datetime.now().isoformat()
        
        # Calculate corrected values and post-correction ΔE for ALL patches
        # (including excluded ones, for display purposes)
        total_delta_e_before = 0
        total_delta_e_after = 0
        max_delta_e_after = 0
        fit_delta_e_before = 0
        fit_delta_e_after = 0
        
        fit_names = {p.name for p in fit_patches}
        
        for patch in self.patch_results:
            patch.corrected_rgb = self.apply_correction(patch.scanned_rgb)
            patch.delta_e_after = self._delta_e_rgb(
                patch.corrected_rgb, patch.digital_rgb
            )
            total_delta_e_before += patch.delta_e_before
            total_delta_e_after += patch.delta_e_after
            max_delta_e_after = max(max_delta_e_after, patch.delta_e_after)
            if patch.name in fit_names:
                fit_delta_e_before += patch.delta_e_before
                fit_delta_e_after += patch.delta_e_after
        
        n_fit = len(fit_patches)
        n_all = len(self.patch_results)
        quality = {
            'avg_delta_e_before': fit_delta_e_before / n_fit,
            'avg_delta_e_after': fit_delta_e_after / n_fit,
            'max_delta_e_after': max_delta_e_after,
            'patch_count': n_all,
            'patches_used': n_fit,
            'patches_excluded': len(excluded_patches),
            'improvement_percent': (
                (1 - fit_delta_e_after / fit_delta_e_before) * 100
                if fit_delta_e_before > 0 else 0
            ),
        }
        
        logger.info(
            f"Calibration computed: avg ΔE {quality['avg_delta_e_before']:.1f} → "
            f"{quality['avg_delta_e_after']:.1f} ({quality['improvement_percent']:.0f}% improvement, "
            f"{n_fit} patches used)"
        )
        
        return quality
    
    def apply_correction(self, rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Apply correction to an RGB tuple.
        
        Supports both linear (2 coefficients) and quadratic (3 coefficients)
        profiles for backward compatibility.
        
        Args:
            rgb: RGB values as (r, g, b) floats 0-255
            
        Returns:
            Corrected RGB values, clamped to 0-255
        """
        if not self.correction_coefficients:
            return rgb
        
        corrected = []
        channel_names = ['R', 'G', 'B']
        
        for ch_idx, ch_name in enumerate(channel_names):
            coeffs = self.correction_coefficients[ch_name]
            x = float(rgb[ch_idx])
            if len(coeffs) == 3:
                # Quadratic: a*x² + b*x + c (legacy profiles)
                y = coeffs[0] * x * x + coeffs[1] * x + coeffs[2]
            else:
                # Linear: a*x + b
                y = coeffs[0] * x + coeffs[1]
            # Clamp to valid range
            y = max(0.0, min(255.0, y))
            corrected.append(y)
        
        return (corrected[0], corrected[1], corrected[2])
    
    def save_profile(self, path: str, name: str = "", scanner_info: str = "") -> bool:
        """Save calibration profile to JSON file.
        
        Args:
            path: Output file path
            name: Profile name (e.g., "My Epson V600")
            scanner_info: Optional scanner description
            
        Returns:
            True if saved successfully
        """
        if not self.is_valid:
            logger.error("Cannot save invalid calibration profile")
            return False
        
        self.profile_name = name
        self.scanner_info = scanner_info
        
        profile = {
            'version': '1.1',
            'type': 'StampZ Scanner Calibration Profile',
            'correction_order': getattr(self, 'correction_order', 2),
            'profile_name': self.profile_name,
            'scanner_info': self.scanner_info,
            'created_date': self.created_date,
            'correction_coefficients': self.correction_coefficients,
            'patch_results': [
                {
                    'name': p.name,
                    'grid_position': list(p.grid_position),
                    'digital_rgb': list(p.digital_rgb),
                    'scanned_rgb': list(p.scanned_rgb),
                    'corrected_rgb': list(p.corrected_rgb) if p.corrected_rgb else None,
                    'delta_e_before': p.delta_e_before,
                    'delta_e_after': p.delta_e_after,
                }
                for p in self.patch_results
            ],
        }
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(profile, f, indent=2)
            logger.info(f"Saved calibration profile to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save calibration profile: {e}")
            return False
    
    def load_profile(self, path: str) -> bool:
        """Load a calibration profile from JSON file.
        
        Args:
            path: Path to profile JSON file
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(path, 'r') as f:
                profile = json.load(f)
            
            self.correction_coefficients = profile['correction_coefficients']
            self.profile_name = profile.get('profile_name', '')
            self.scanner_info = profile.get('scanner_info', '')
            self.created_date = profile.get('created_date', '')
            
            # Restore patch results if available
            self.patch_results = []
            for p in profile.get('patch_results', []):
                result = PatchResult(
                    name=p['name'],
                    grid_position=tuple(p['grid_position']),
                    digital_rgb=tuple(p['digital_rgb']),
                    scanned_rgb=tuple(p['scanned_rgb']),
                    corrected_rgb=tuple(p['corrected_rgb']) if p.get('corrected_rgb') else None,
                    delta_e_before=p.get('delta_e_before', 0),
                    delta_e_after=p.get('delta_e_after', 0),
                )
                self.patch_results.append(result)
            
            self.is_valid = True
            logger.info(f"Loaded calibration profile from {path}: {self.profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load calibration profile: {e}")
            self.is_valid = False
            return False
    
    def get_calibration_quality(self) -> Optional[Dict[str, Any]]:
        """Get quality metrics for the current calibration.
        
        Returns:
            Dict with quality metrics, or None if not calibrated
        """
        if not self.is_valid or not self.patch_results:
            return None
        
        delta_e_before = [p.delta_e_before for p in self.patch_results]
        delta_e_after = [p.delta_e_after for p in self.patch_results]
        
        return {
            'avg_delta_e_before': sum(delta_e_before) / len(delta_e_before),
            'avg_delta_e_after': sum(delta_e_after) / len(delta_e_after),
            'max_delta_e_before': max(delta_e_before),
            'max_delta_e_after': max(delta_e_after),
            'min_delta_e_after': min(delta_e_after),
            'patch_count': len(self.patch_results),
            'profile_name': self.profile_name,
            'created_date': self.created_date,
        }
    
    # ---- Internal helpers ----
    
    @staticmethod
    def _find_patch_ranges(profile: np.ndarray, threshold: float = 220) -> List[Tuple[int, int]]:
        """Find contiguous non-white regions in a 1D brightness profile.
        
        Args:
            profile: 1D array of brightness values
            threshold: Values below this are considered part of a patch
            
        Returns:
            List of (start, end) pixel ranges
        """
        in_patch = False
        ranges = []
        start = 0
        
        for i, val in enumerate(profile):
            if not in_patch and val < threshold:
                start = i
                in_patch = True
            elif in_patch and val >= threshold:
                ranges.append((start, i))
                in_patch = False
        if in_patch:
            ranges.append((start, len(profile)))
        
        # Merge small gaps (< 30 pixels) — handles slight printing artifacts
        merged = []
        for r in ranges:
            if merged and r[0] - merged[-1][1] < 30:
                merged[-1] = (merged[-1][0], r[1])
            else:
                merged.append(r)
        
        # Filter out tiny ranges (< 100 pixels) — noise/borders
        return [(s, e) for s, e in merged if e - s > 100]
    
    @staticmethod
    def _interpolate_grid_ranges(
        detected: List[Tuple[int, int]],
        expected: int,
        axis_size: Optional[int] = None
    ) -> List[Tuple[int, int]]:
        """Infer a full regular grid from a partial set of detected ranges.
        
        This is used when one or more interior patches are too close in
        brightness to the background (e.g. white patch on white paper).
        
        Args:
            detected: Existing detected ranges (must be sorted)
            expected: Expected number of ranges in this axis
            axis_size: Optional axis length for bounds clipping
        
        Returns:
            Reconstructed list of ranges, or original ranges if interpolation
            is not feasible.
        """
        if len(detected) < 2 or len(detected) >= expected:
            return detected
        
        widths = [e - s for s, e in detected if e > s]
        if not widths:
            return detected
        avg_width = int(round(float(np.mean(widths))))
        
        first_center = (detected[0][0] + detected[0][1]) / 2.0
        last_center = (detected[-1][0] + detected[-1][1]) / 2.0
        if expected <= 1:
            return detected
        
        spacing = (last_center - first_center) / (expected - 1)
        half = avg_width // 2
        
        interpolated = []
        for i in range(expected):
            center = int(round(first_center + i * spacing))
            start = center - half
            end = center + half
            
            if axis_size is not None:
                start = max(0, start)
                end = min(axis_size, end)
            
            if end <= start:
                return detected
            interpolated.append((start, end))
        
        logger.info(
            f"Interpolated {expected} ranges from {len(detected)} detected "
            f"(width={avg_width}, spacing={spacing:.1f})"
        )
        return interpolated
    
    @staticmethod
    def _delta_e_rgb(rgb1: Tuple[float, float, float],
                     rgb2: Tuple[float, float, float]) -> float:
        """Calculate Euclidean distance between two RGB values.
        
        This is a simple RGB distance, not perceptual ΔE in L*a*b*.
        Used as a quick quality metric during calibration.
        """
        return math.sqrt(
            (rgb1[0] - rgb2[0]) ** 2 +
            (rgb1[1] - rgb2[1]) ** 2 +
            (rgb1[2] - rgb2[2]) ** 2
        )
