#!/usr/bin/env python3
"""
Scanner Calibration Module for StampZ

Provides scanner normalization using the StampZ printed color target (20 patches).
Maps scanner RGB output to a standard reference color space so that color libraries
and measurements are comparable across different scanners.

Correction model: per-channel 2nd-order polynomial fit from 20 paired data points
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


# Patch layout for the StampZ calibration target
# Maps grid position (row, col) in the scanned image to (name, digital_rgb)
# Target is oriented with Black at top-left when scanned
PATCH_MAP = {
    (0, 0): ("Black",         (0x17, 0x16, 0x15)),
    (0, 1): ("Dark Gray",     (0x62, 0x62, 0x61)),
    (0, 2): ("Medium Gray",   (0x9C, 0x9C, 0x9B)),
    (0, 3): ("Light Gray",    (0xD0, 0xCF, 0xCF)),
    (1, 0): ("White",         (0xFF, 0xFF, 0xFF)),
    (1, 1): ("Rose",          (0xFF, 0x00, 0x7F)),
    (1, 2): ("Buff",          (0xFF, 0xE8, 0xCB)),
    (1, 3): ("Prussian Blue", (0x00, 0x5A, 0x96)),
    (2, 0): ("Green",         (0x00, 0xFF, 0x00)),
    (2, 1): ("Yellow",        (0xFF, 0xED, 0x00)),
    (2, 2): ("Violet",        (0xBF, 0x7F, 0xFF)),
    (2, 3): ("Vermillion",    (0xE3, 0x42, 0x34)),
    (3, 0): ("Blue",          (0x00, 0x00, 0xFF)),
    (3, 1): ("Magenta",       (0xE5, 0x00, 0x7C)),
    (3, 2): ("Lavender",      (0xE4, 0xAF, 0xF3)),
    (3, 3): ("Brown",         (0x96, 0x4B, 0x00)),
    (4, 0): ("Red",           (0xFF, 0x00, 0x00)),
    (4, 1): ("Cyan",          (0x00, 0x9E, 0xE3)),
    (4, 2): ("Dark Green",    (0x00, 0x63, 0x00)),
    (4, 3): ("Khaki",         (0x85, 0x6D, 0x4D)),
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
    
    def detect_patches(self, image_path: str) -> List[PatchResult]:
        """Auto-detect the 20 color patches from a scanned target image.
        
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
            
            if len(col_ranges) != 4 or len(row_ranges) != 5:
                raise ValueError(
                    f"Expected 4 columns × 5 rows of patches, "
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
    
    def compute_correction(self) -> Dict[str, Any]:
        """Compute per-channel polynomial correction from detected patches.
        
        Uses 2nd-order polynomial per channel: corrected = a*x² + b*x + c
        where x is the scanned value and corrected maps to the digital reference.
        
        Returns:
            Dict with correction quality metrics
        """
        if not self.patch_results:
            raise ValueError("No patches detected. Run detect_patches() first.")
        
        # Build paired data arrays for each channel
        scanned = np.array([p.scanned_rgb for p in self.patch_results])
        reference = np.array([p.digital_rgb for p in self.patch_results])
        
        coefficients = {}
        channel_names = ['R', 'G', 'B']
        
        for ch_idx, ch_name in enumerate(channel_names):
            x = scanned[:, ch_idx]
            y = reference[:, ch_idx]
            
            # Fit 2nd-order polynomial: y = a*x² + b*x + c
            coeffs = np.polyfit(x, y, 2)
            coefficients[ch_name] = coeffs.tolist()
        
        self.correction_coefficients = coefficients
        self.is_valid = True
        self.created_date = datetime.now().isoformat()
        
        # Calculate corrected values and post-correction ΔE for all patches
        total_delta_e_before = 0
        total_delta_e_after = 0
        max_delta_e_after = 0
        
        for patch in self.patch_results:
            patch.corrected_rgb = self.apply_correction(patch.scanned_rgb)
            patch.delta_e_after = self._delta_e_rgb(
                patch.corrected_rgb, patch.digital_rgb
            )
            total_delta_e_before += patch.delta_e_before
            total_delta_e_after += patch.delta_e_after
            max_delta_e_after = max(max_delta_e_after, patch.delta_e_after)
        
        n = len(self.patch_results)
        quality = {
            'avg_delta_e_before': total_delta_e_before / n,
            'avg_delta_e_after': total_delta_e_after / n,
            'max_delta_e_after': max_delta_e_after,
            'patch_count': n,
            'improvement_percent': (
                (1 - total_delta_e_after / total_delta_e_before) * 100
                if total_delta_e_before > 0 else 0
            ),
        }
        
        logger.info(
            f"Calibration computed: avg ΔE {quality['avg_delta_e_before']:.1f} → "
            f"{quality['avg_delta_e_after']:.1f} ({quality['improvement_percent']:.0f}% improvement)"
        )
        
        return quality
    
    def apply_correction(self, rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Apply polynomial correction to an RGB tuple.
        
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
            # Evaluate polynomial: a*x² + b*x + c
            y = coeffs[0] * x * x + coeffs[1] * x + coeffs[2]
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
            'version': '1.0',
            'type': 'StampZ Scanner Calibration Profile',
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
