#!/usr/bin/env python3
"""
Scanner Calibration Module for StampZ

CR30-grounded 20-patch scanner characterization.

The calibration model follows the newer test approach:
    scanner RGB -> linearized RGB -> affine XYZ transform -> CIE Lab

The CR30 CIE L*a*b* measurements are the calibration ground truth. RGB is
retained only where StampZ needs it to read image pixels, display swatches,
or maintain compatibility with older runtime callers.

Target layout: 4 columns x 5 rows, Black at top-left.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Ground truth: CR30 spectrometer values supplied for the 20-patch target
# ---------------------------------------------------------------------
PATCH_NAMES = [
    "Black", "25% Gray", "50% Gray", "75% Gray",
    "White", "Buff", "Brown", "Orange",
    "Red", "Rose", "Fuschia", "Blue",
    "Violet", "Mauve", "Green", "Yellow",
    "Ultramarine", "Bronze", "Cyan/Teal", "Yellow-Green",
]

CR30_LAB_TARGETS = np.array([
    [10.00,   0.00,   0.00],   # Black - practical V600 floor
    [23.53,   0.51,  -1.10],   # 25% Gray
    [45.79,  -0.03,  -1.38],   # 50% Gray
    [69.65,  -0.68,  -0.06],   # 75% Gray
    [93.70,  -1.67,  -3.68],   # White - target paper
    [86.02,   2.81,   9.59],   # Buff
    [35.38,  25.35,  44.05],   # Brown
    [52.55,  36.68,  55.01],   # Orange
    [43.77,  67.04,  59.57],   # Red
    [44.95,  73.40,  -6.00],   # Rose
    [41.10,  69.82,  -9.63],   # Fuschia
    [52.91,  -4.39, -32.17],   # Blue
    [61.80,  22.11, -36.57],   # Violet
    [72.52,  18.15, -25.06],   # Mauve
    [34.45, -29.08,  40.05],   # Green
    [67.95,  -0.35,  50.27],   # Yellow
    [29.57,  14.09, -38.28],   # Ultramarine
    [54.10,  17.91,  39.98],   # Bronze
    [54.98, -24.77, -11.51],   # Cyan/Teal
    [66.88, -53.28,  58.60],   # Yellow-Green
], dtype=np.float64)

PATCH_LAB: Dict[str, Tuple[float, float, float]] = {
    name: tuple(float(v) for v in lab)
    for name, lab in zip(PATCH_NAMES, CR30_LAB_TARGETS)
}

GRID_ROWS = 5
GRID_COLS = 4

# D65 / 2-degree standard observer, normalized Y=1.
D65_WHITE = np.array([0.95047, 1.00000, 1.08883], dtype=np.float64)


# ---------------------------------------------------------------------
# Color-science helpers
# ---------------------------------------------------------------------
def _srgb_to_linear(rgb01: np.ndarray) -> np.ndarray:
    rgb01 = np.asarray(rgb01, dtype=np.float64)
    return np.where(
        rgb01 > 0.04045,
        ((rgb01 + 0.055) / 1.055) ** 2.4,
        rgb01 / 12.92,
    )


def _linear_to_srgb(rgb_linear: np.ndarray) -> np.ndarray:
    rgb_linear = np.asarray(rgb_linear, dtype=np.float64)
    # The transfer function is only defined for non-negative light values.
    x = np.maximum(rgb_linear, 0.0)
    return np.where(
        x > 0.0031308,
        1.055 * np.power(x, 1.0 / 2.4) - 0.055,
        12.92 * x,
    )


def lab_to_xyz(lab_array: np.ndarray) -> np.ndarray:
    """Convert CIE Lab (D65) rows to normalized XYZ rows."""
    lab = np.atleast_2d(np.asarray(lab_array, dtype=np.float64))
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]

    fy = (L + 16.0) / 116.0
    fx = fy + (a / 500.0)
    fz = fy - (b / 200.0)

    delta = 6.0 / 29.0

    def f_inv(t: np.ndarray) -> np.ndarray:
        return np.where(
            t > delta,
            t ** 3,
            3.0 * (delta ** 2) * (t - 4.0 / 29.0),
        )

    xyz = np.stack([f_inv(fx), f_inv(fy), f_inv(fz)], axis=1)
    return xyz * D65_WHITE


def xyz_to_lab(xyz_array: np.ndarray) -> np.ndarray:
    """Convert normalized XYZ rows to CIE Lab (D65)."""
    xyz = np.atleast_2d(np.asarray(xyz_array, dtype=np.float64))
    ratio = xyz / D65_WHITE

    delta = 6.0 / 29.0
    delta3 = delta ** 3

    def f(t: np.ndarray) -> np.ndarray:
        return np.where(
            t > delta3,
            np.cbrt(t),
            t / (3.0 * delta ** 2) + 4.0 / 29.0,
        )

    fx, fy, fz = f(ratio[:, 0]), f(ratio[:, 1]), f(ratio[:, 2])
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=1)


def srgb_to_xyz(rgb_array: np.ndarray) -> np.ndarray:
    """Convert sRGB-like 0..1 rows to normalized XYZ (D65)."""
    rgb = np.atleast_2d(np.asarray(rgb_array, dtype=np.float64))
    linear = _srgb_to_linear(rgb)
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ], dtype=np.float64)
    return linear @ m.T


def xyz_to_srgb(xyz_array: np.ndarray) -> np.ndarray:
    """Convert normalized XYZ rows (D65) to display sRGB 0..1."""
    xyz = np.atleast_2d(np.asarray(xyz_array, dtype=np.float64))
    m_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252],
    ], dtype=np.float64)
    linear = xyz @ m_inv.T
    return np.clip(_linear_to_srgb(linear), 0.0, 1.0)


def srgb_to_lab(rgb_array: np.ndarray) -> np.ndarray:
    return xyz_to_lab(srgb_to_xyz(rgb_array))


def lab_to_srgb(lab_array: np.ndarray) -> np.ndarray:
    return xyz_to_srgb(lab_to_xyz(lab_array))


def delta_e_76(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    a = np.atleast_2d(np.asarray(lab1, dtype=np.float64))
    b = np.atleast_2d(np.asarray(lab2, dtype=np.float64))
    return np.linalg.norm(a - b, axis=1)


Y_TARGETS_XYZ = lab_to_xyz(CR30_LAB_TARGETS)

# Reference RGB is only for GUI swatches; it is never calibration truth.
_REFERENCE_RGB_01 = lab_to_srgb(CR30_LAB_TARGETS)
REFERENCE_RGB_255 = np.rint(_REFERENCE_RGB_01 * 255.0).astype(int)


@dataclass
class PatchResult:
    name: str
    grid_position: Tuple[int, int]
    reference_lab: Tuple[float, float, float]
    scanned_rgb: Tuple[float, float, float]
    scanned_lab: Tuple[float, float, float]
    corrected_lab: Optional[Tuple[float, float, float]] = None
    corrected_rgb: Optional[Tuple[float, float, float]] = None
    delta_e_before: float = 0.0
    delta_e_after: float = 0.0

    @property
    def digital_rgb(self) -> Tuple[int, int, int]:
        """Legacy GUI name: display RGB generated from CR30 Lab reference."""
        idx = PATCH_NAMES.index(self.name)
        rgb = REFERENCE_RGB_255[idx]
        return int(rgb[0]), int(rgb[1]), int(rgb[2])


# ---------------------------------------------------------------------
# Active calibration API expected by StampZ
# ---------------------------------------------------------------------
_active_calibration: Optional["ScannerCalibration"] = None


def get_active_calibration() -> Optional["ScannerCalibration"]:
    return _active_calibration


def set_active_calibration(calibration: Optional["ScannerCalibration"]) -> None:
    global _active_calibration
    _active_calibration = calibration
    logger.info("Scanner calibration %s", "activated" if calibration else "deactivated")


def apply_calibration_to_rgb(
    rgb: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    """Legacy runtime bridge: calibrated physical color rendered back to sRGB.

    The calibration itself is NOT performed in RGB space. This function exists
    so older StampZ paths that expect corrected RGB continue to operate.
    """
    if _active_calibration and _active_calibration.is_valid:
        return _active_calibration.apply_correction(rgb)
    return rgb


def apply_calibration_to_lab_from_rgb(
    rgb: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    """Preferred runtime path: scanner RGB directly to calibrated CIE Lab."""
    if _active_calibration and _active_calibration.is_valid:
        return _active_calibration.apply_to_lab(rgb)
    rgb01 = np.array(rgb, dtype=np.float64).reshape(1, 3) / 255.0
    lab = srgb_to_lab(rgb01)[0]
    return tuple(float(v) for v in lab)


def apply_lab_calibration(
    lab: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    """Compatibility bridge for callers that already converted scanner RGB to Lab.

    This reconstructs the corresponding sRGB triplet, then applies the active
    scanner RGB->XYZ characterization. New code should prefer
    apply_calibration_to_lab_from_rgb() to avoid this round trip.
    """
    if not (_active_calibration and _active_calibration.is_valid):
        return lab
    rgb01 = lab_to_srgb(np.array(lab, dtype=np.float64).reshape(1, 3))[0]
    return _active_calibration.apply_to_lab(tuple(float(v * 255.0) for v in rgb01))


class ScannerCalibration:
    """StampZ-compatible wrapper around the CR30 RGB->XYZ matrix method."""

    GRID_ROWS = GRID_ROWS
    GRID_COLS = GRID_COLS
    # Kept only because the existing dialog references this attribute.
    # The CR30 matrix fit uses all 20 patches, so none are excluded here.
    GAMUT_THRESHOLD = float("inf")

    def __init__(self) -> None:
        self.patch_results: List[PatchResult] = []
        self.calibration_matrix: Optional[np.ndarray] = None  # 4 x 3
        self.is_valid = False
        self.profile_name = ""
        self.created_date = ""
        self.scanner_info = ""
        self.source_target_path = ""
        self._quality: Optional[Dict[str, Any]] = None

    def detect_patches(self, image_path: str) -> List[PatchResult]:
        """Sample the center 50% of each cell from a cropped 4x5 target scan."""
        img = Image.open(image_path).convert("RGB")
        arr = np.asarray(img, dtype=np.float64)
        h, w, _ = arr.shape

        if h < self.GRID_ROWS * 4 or w < self.GRID_COLS * 4:
            raise ValueError("Target image is too small to sample a 4 x 5 grid reliably.")

        cell_h = h / self.GRID_ROWS
        cell_w = w / self.GRID_COLS
        results: List[PatchResult] = []

        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                # Middle 50% of each nominal grid cell, matching Peter's test code.
                y1 = int(round((r + 0.25) * cell_h))
                y2 = int(round((r + 0.75) * cell_h))
                x1 = int(round((c + 0.25) * cell_w))
                x2 = int(round((c + 0.75) * cell_w))
                crop = arr[y1:y2, x1:x2]
                if crop.size == 0:
                    raise ValueError(f"Empty sample region at target row {r + 1}, column {c + 1}.")

                idx = r * self.GRID_COLS + c
                name = PATCH_NAMES[idx]
                ref_lab = CR30_LAB_TARGETS[idx]
                mean_rgb = crop.mean(axis=(0, 1))
                scan_lab = srgb_to_lab((mean_rgb / 255.0).reshape(1, 3))[0]
                de_before = float(delta_e_76(scan_lab, ref_lab)[0])

                results.append(PatchResult(
                    name=name,
                    grid_position=(r, c),
                    reference_lab=tuple(float(v) for v in ref_lab),
                    scanned_rgb=tuple(float(v) for v in mean_rgb),
                    scanned_lab=tuple(float(v) for v in scan_lab),
                    delta_e_before=de_before,
                ))

        if len(results) != 20:
            raise ValueError(f"Expected 20 target patches; sampled {len(results)}.")

        self.patch_results = results
        self.source_target_path = image_path
        logger.info("Sampled 20 CR30 target patches from %s", image_path)
        return results

    def compute_correction(self) -> Dict[str, Any]:
        """Fit Peter's affine linear-RGB -> CR30 XYZ matrix using all 20 patches."""
        if len(self.patch_results) != 20:
            raise ValueError("No complete 20-patch target is loaded. Run detect_patches() first.")

        scanned_rgb01 = np.array([p.scanned_rgb for p in self.patch_results], dtype=np.float64) / 255.0
        scanned_linear = _srgb_to_linear(scanned_rgb01)
        x_input = np.hstack([scanned_linear, np.ones((len(scanned_linear), 1))])

        weights, _, rank, _ = np.linalg.lstsq(x_input, Y_TARGETS_XYZ, rcond=None)
        if rank < 4:
            raise ValueError("Calibration target data are degenerate; could not solve a stable 4-parameter matrix.")

        self.calibration_matrix = weights
        self.is_valid = True
        self.created_date = datetime.now().isoformat()

        before = []
        after = []
        for p in self.patch_results:
            corrected_lab = self.apply_to_lab(p.scanned_rgb)
            p.corrected_lab = corrected_lab
            p.delta_e_after = float(delta_e_76(
                np.array(corrected_lab).reshape(1, 3),
                np.array(p.reference_lab).reshape(1, 3),
            )[0])
            corrected_rgb = lab_to_srgb(np.array(corrected_lab).reshape(1, 3))[0] * 255.0
            p.corrected_rgb = tuple(float(v) for v in corrected_rgb)
            before.append(p.delta_e_before)
            after.append(p.delta_e_after)

        avg_before = float(np.mean(before))
        avg_after = float(np.mean(after))
        improvement = (1.0 - avg_after / avg_before) * 100.0 if avg_before > 0 else 0.0

        self._quality = {
            "avg_delta_e_before": avg_before,
            "avg_delta_e_after": avg_after,
            "max_delta_e_before": float(np.max(before)),
            "max_delta_e_after": float(np.max(after)),
            "patch_count": 20,
            "patches_used": 20,
            "patches_excluded": 0,
            "improvement_percent": improvement,
            "profile_name": self.profile_name,
            "created_date": self.created_date,
            "metric": "CIE76 Lab",
        }

        logger.info(
            "CR30 calibration computed: avg dE76 %.2f -> %.2f (%.1f%% improvement)",
            avg_before, avg_after, improvement,
        )
        return dict(self._quality)

    def _rgb_to_calibrated_xyz(self, rgb: Tuple[float, float, float]) -> np.ndarray:
        if self.calibration_matrix is None:
            raise ValueError("No calibration matrix is loaded.")
        rgb01 = np.clip(np.asarray(rgb, dtype=np.float64) / 255.0, 0.0, 1.0)
        linear = _srgb_to_linear(rgb01)
        vec = np.append(linear, 1.0)
        xyz = vec @ self.calibration_matrix
        # Small negative values can arise from an affine least-squares fit.
        return np.maximum(xyz, 0.0)

    def apply_to_lab(self, rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Convert scanner RGB directly to calibrated CR30-grounded CIE Lab."""
        if not self.is_valid or self.calibration_matrix is None:
            rgb01 = np.asarray(rgb, dtype=np.float64).reshape(1, 3) / 255.0
            lab = srgb_to_lab(rgb01)[0]
        else:
            xyz = self._rgb_to_calibrated_xyz(rgb).reshape(1, 3)
            lab = xyz_to_lab(xyz)[0]
        return tuple(float(v) for v in lab)

    def apply_correction(self, rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Legacy RGB return path, rendered from the calibrated physical XYZ."""
        if not self.is_valid or self.calibration_matrix is None:
            return tuple(float(v) for v in rgb)
        xyz = self._rgb_to_calibrated_xyz(rgb).reshape(1, 3)
        rgb01 = xyz_to_srgb(xyz)[0]
        return tuple(float(v * 255.0) for v in rgb01)

    def save_profile(self, path: str, name: str = "", scanner_info: str = "") -> bool:
        if not self.is_valid or self.calibration_matrix is None:
            logger.error("Cannot save an invalid calibration profile")
            return False

        self.profile_name = name
        self.scanner_info = scanner_info
        if self._quality is not None:
            self._quality["profile_name"] = name
            self._quality["created_date"] = self.created_date

        profile = {
            "version": "2.0",
            "type": "StampZ Scanner Calibration Profile",
            "calibration_model": "linear scanner RGB -> affine XYZ -> CIE Lab",
            "illuminant": "D65",
            "profile_name": self.profile_name,
            "scanner_info": self.scanner_info,
            "created_date": self.created_date,
            "source_target_path": self.source_target_path,
            "cr30_lab_targets": CR30_LAB_TARGETS.tolist(),
            "calibration_matrix": self.calibration_matrix.tolist(),
            "quality": self._quality,
            "patch_results": [self._patch_to_dict(p) for p in self.patch_results],
        }

        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            logger.info("Saved CR30 calibration profile to %s", path)
            return True
        except Exception as exc:
            logger.error("Failed to save calibration profile: %s", exc)
            return False

    def load_profile(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                profile = json.load(f)

            matrix = profile.get("calibration_matrix")
            if matrix is None:
                # Do not silently reinterpret legacy per-channel RGB profiles as
                # CR30 matrix profiles. They are different calibration models.
                raise ValueError(
                    "This is a legacy RGB calibration profile and does not contain "
                    "a CR30 calibration_matrix. Recalibrate with the 20-patch target."
                )

            m = np.asarray(matrix, dtype=np.float64)
            if m.shape != (4, 3):
                raise ValueError(f"Invalid calibration matrix shape {m.shape}; expected (4, 3).")

            self.calibration_matrix = m
            self.profile_name = profile.get("profile_name", "")
            self.scanner_info = profile.get("scanner_info", "")
            self.created_date = profile.get("created_date", "")
            self.source_target_path = profile.get("source_target_path", "")
            self._quality = profile.get("quality")
            self.patch_results = [
                self._patch_from_dict(item)
                for item in profile.get("patch_results", [])
            ]
            self.is_valid = True
            logger.info("Loaded CR30 calibration profile from %s", path)
            return True
        except Exception as exc:
            logger.error("Failed to load calibration profile: %s", exc)
            self.is_valid = False
            return False

    def get_calibration_quality(self) -> Optional[Dict[str, Any]]:
        if not self.is_valid:
            return None
        if self._quality is not None:
            q = dict(self._quality)
            q["profile_name"] = self.profile_name
            q["created_date"] = self.created_date
            return q
        if self.patch_results:
            before = [p.delta_e_before for p in self.patch_results]
            after = [p.delta_e_after for p in self.patch_results]
            return {
                "avg_delta_e_before": float(np.mean(before)),
                "avg_delta_e_after": float(np.mean(after)),
                "max_delta_e_before": float(np.max(before)),
                "max_delta_e_after": float(np.max(after)),
                "patch_count": len(self.patch_results),
                "patches_used": len(self.patch_results),
                "patches_excluded": 0,
                "profile_name": self.profile_name,
                "created_date": self.created_date,
                "metric": "CIE76 Lab",
            }
        return {
            "profile_name": self.profile_name,
            "created_date": self.created_date,
            "avg_delta_e_after": 0.0,
            "patch_count": 0,
            "patches_used": 0,
            "patches_excluded": 0,
            "metric": "CIE76 Lab",
        }

    @staticmethod
    def _patch_to_dict(p: PatchResult) -> Dict[str, Any]:
        return {
            "name": p.name,
            "grid_position": list(p.grid_position),
            "reference_lab": list(p.reference_lab),
            "scanned_rgb": list(p.scanned_rgb),
            "scanned_lab": list(p.scanned_lab),
            "corrected_lab": list(p.corrected_lab) if p.corrected_lab else None,
            "corrected_rgb": list(p.corrected_rgb) if p.corrected_rgb else None,
            "delta_e_before": p.delta_e_before,
            "delta_e_after": p.delta_e_after,
        }

    @staticmethod
    def _patch_from_dict(data: Dict[str, Any]) -> PatchResult:
        name = data["name"]
        ref_lab = data.get("reference_lab", PATCH_LAB.get(name, (0.0, 0.0, 0.0)))
        scanned_rgb = tuple(data.get("scanned_rgb", (0.0, 0.0, 0.0)))
        scanned_lab = data.get("scanned_lab")
        if scanned_lab is None:
            rgb01 = np.asarray(scanned_rgb, dtype=np.float64).reshape(1, 3) / 255.0
            scanned_lab = srgb_to_lab(rgb01)[0].tolist()
        corrected_lab = data.get("corrected_lab")
        corrected_rgb = data.get("corrected_rgb")
        return PatchResult(
            name=name,
            grid_position=tuple(data.get("grid_position", (0, 0))),
            reference_lab=tuple(float(v) for v in ref_lab),
            scanned_rgb=tuple(float(v) for v in scanned_rgb),
            scanned_lab=tuple(float(v) for v in scanned_lab),
            corrected_lab=(tuple(float(v) for v in corrected_lab) if corrected_lab else None),
            corrected_rgb=(tuple(float(v) for v in corrected_rgb) if corrected_rgb else None),
            delta_e_before=float(data.get("delta_e_before", 0.0)),
            delta_e_after=float(data.get("delta_e_after", 0.0)),
        )


def calculate_calibration_matrix(
    scanned_target_path: str,
    output_matrix_path: str = "calibration_matrix.json",
) -> np.ndarray:
    """Standalone compatibility helper retained from Peter's test module."""
    cal = ScannerCalibration()
    cal.detect_patches(scanned_target_path)
    cal.compute_correction()
    assert cal.calibration_matrix is not None
    with open(output_matrix_path, "w", encoding="utf-8") as f:
        json.dump(cal.calibration_matrix.tolist(), f, indent=2)
    return cal.calibration_matrix
