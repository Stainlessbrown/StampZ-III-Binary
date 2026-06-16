#!/usr/bin/env python3
"""
Stamp Layer Separator for StampZ

Separates a stamp image into distinct layers:
  1. Background (scanner lid / card behind stamp)
  2. Paper (unprinted substrate)
  3. Ink (printed design — engraved lines, solid areas)
  4. Cancellation (postmark — dark overprint)

The ink layer can then be analyzed as a whole to produce a single
aggregate L*a*b* measurement representing the stamp's perceived color.

Usage from StampZ:
    separator = StampLayerSeparator(pil_image)
    separator.set_background_color(r, g, b)          # from user click
    result = separator.separate()
    ink_lab = result['ink_aggregate_lab']              # the "whole stamp" color
"""

import numpy as np
from PIL import Image
from typing import Dict, Optional, Tuple
from colorspacious import cspace_convert


class LayerResult:
    """Result of a layer separation."""

    def __init__(self):
        # Boolean masks (same shape as input image H×W)
        self.background_mask: Optional[np.ndarray] = None
        self.cancellation_mask: Optional[np.ndarray] = None
        self.paper_mask: Optional[np.ndarray] = None
        self.ink_mask: Optional[np.ndarray] = None

        # Aggregate color measurements
        self.ink_aggregate_rgb: Optional[Tuple[float, float, float]] = None
        self.ink_aggregate_lab: Optional[Tuple[float, float, float]] = None
        self.ink_median_rgb: Optional[Tuple[float, float, float]] = None
        self.ink_median_lab: Optional[Tuple[float, float, float]] = None
        self.paper_aggregate_rgb: Optional[Tuple[float, float, float]] = None
        self.paper_aggregate_lab: Optional[Tuple[float, float, float]] = None

        # Statistics
        self.total_pixels: int = 0
        self.background_pixels: int = 0
        self.cancellation_pixels: int = 0
        self.paper_pixels: int = 0
        self.ink_pixels: int = 0
        self.ink_percentage: float = 0.0
        self.paper_percentage: float = 0.0


class StampLayerSeparator:
    """Separates a stamp image into background, paper, ink, and cancellation layers."""

    def __init__(self, image: Image.Image):
        """
        Args:
            image: PIL Image (RGB mode)
        """
        self._original = image.convert('RGB')
        self._arr = np.array(self._original, dtype=np.float32)
        self._bg_rgb: Optional[Tuple[float, float, float]] = None

        # Tunable thresholds
        self.background_delta_e_threshold = 12.0   # ΔE tolerance for background removal
        self.cancellation_brightness_max = 60       # Max brightness for cancellation ink
        self.cancellation_saturation_max = 30       # Max saturation for cancellation ink

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #

    def set_background_color(self, r: float, g: float, b: float) -> None:
        """Set the sampled background color (from user click).

        Args:
            r, g, b: Background color in 0-255 range
        """
        self._bg_rgb = (float(r), float(g), float(b))

    def set_thresholds(
        self,
        background_delta_e: Optional[float] = None,
        cancellation_brightness: Optional[int] = None,
        cancellation_saturation: Optional[int] = None,
    ) -> None:
        """Override default thresholds."""
        if background_delta_e is not None:
            self.background_delta_e_threshold = background_delta_e
        if cancellation_brightness is not None:
            self.cancellation_brightness_max = cancellation_brightness
        if cancellation_saturation is not None:
            self.cancellation_saturation_max = cancellation_saturation

    # ------------------------------------------------------------------ #
    # Core separation
    # ------------------------------------------------------------------ #

    def separate(self) -> LayerResult:
        """Run the full layer separation pipeline.

        Returns:
            LayerResult with masks and aggregate measurements
        """
        result = LayerResult()
        h, w = self._arr.shape[:2]
        result.total_pixels = h * w

        # Step 1: Background mask
        if self._bg_rgb is not None:
            result.background_mask = self._mask_background()
        else:
            result.background_mask = np.zeros((h, w), dtype=bool)

        # Step 2: Cancellation mask (within non-background area)
        result.cancellation_mask = self._mask_cancellation(result.background_mask)

        # Step 3: Separate remaining pixels into ink vs paper
        # "Stamp area" = everything that isn't background or cancellation
        stamp_area = ~result.background_mask & ~result.cancellation_mask
        result.ink_mask, result.paper_mask = self._separate_ink_paper(stamp_area)

        # Step 4: Compute aggregate colors
        self._compute_aggregates(result)

        # Step 5: Statistics
        result.background_pixels = int(np.sum(result.background_mask))
        result.cancellation_pixels = int(np.sum(result.cancellation_mask))
        result.ink_pixels = int(np.sum(result.ink_mask))
        result.paper_pixels = int(np.sum(result.paper_mask))

        stamp_total = result.ink_pixels + result.paper_pixels
        if stamp_total > 0:
            result.ink_percentage = result.ink_pixels / stamp_total * 100
            result.paper_percentage = result.paper_pixels / stamp_total * 100

        return result

    # ------------------------------------------------------------------ #
    # Layer extraction helpers
    # ------------------------------------------------------------------ #

    def _mask_background(self) -> np.ndarray:
        """Create a boolean mask of background pixels using ΔE from sampled color."""
        bg = np.array(self._bg_rgb) / 255.0
        bg_lab = cspace_convert(bg, 'sRGB1', 'CIELab')

        # Convert entire image to Lab
        img_norm = self._arr / 255.0
        # Reshape for batch conversion: (H*W, 3)
        flat = img_norm.reshape(-1, 3)
        flat_lab = cspace_convert(flat, 'sRGB1', 'CIELab')

        # ΔE (Euclidean in Lab space — fast approximation)
        diff = flat_lab - bg_lab
        delta_e = np.sqrt(np.sum(diff ** 2, axis=1))

        mask = delta_e < self.background_delta_e_threshold
        return mask.reshape(img_norm.shape[:2])

    def _mask_cancellation(self, background_mask: np.ndarray) -> np.ndarray:
        """Identify cancellation pixels using multi-pass detection.

        Pass 1: strict thresholds catch heavy/solid cancel strokes.
        Pass 2: relaxed thresholds catch lighter residual strokes,
                but only in the neighbourhood of pass-1 detections
                so we don't grab faint stamp ink by mistake.
        """
        r, g, b = self._arr[:, :, 0], self._arr[:, :, 1], self._arr[:, :, 2]
        brightness = (r + g + b) / 3.0
        max_ch = np.maximum(np.maximum(r, g), b)
        min_ch = np.minimum(np.minimum(r, g), b)
        saturation = max_ch - min_ch
        not_bg = ~background_mask

        # Pass 1: strict (user thresholds)
        pass1 = (brightness < self.cancellation_brightness_max) & \
                (saturation < self.cancellation_saturation_max) & not_bg

        # Pass 2: relaxed (+40% brightness, +50% saturation) but only
        # near existing detections. "Near" = within a dilation radius.
        relax_bright = self.cancellation_brightness_max * 1.4
        relax_sat = self.cancellation_saturation_max * 1.5
        candidates = (brightness < relax_bright) & (saturation < relax_sat) & not_bg & ~pass1

        if np.any(pass1) and np.any(candidates):
            # Dilate pass1 mask to define "neighbourhood"
            from scipy.ndimage import binary_dilation
            struct = np.ones((7, 7), dtype=bool)
            near_cancel = binary_dilation(pass1, structure=struct, iterations=2)
            pass2 = candidates & near_cancel
        else:
            pass2 = np.zeros_like(pass1)

        return pass1 | pass2

    def _separate_ink_paper(
        self, stamp_area: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Split the stamp area into ink and paper using Otsu's method on L*.

        Args:
            stamp_area: boolean mask of pixels that are part of the stamp
                        (not background, not cancellation)

        Returns:
            (ink_mask, paper_mask) — both same shape as stamp_area
        """
        h, w = stamp_area.shape

        # Convert to L* for lightness-based separation
        img_norm = self._arr / 255.0
        flat = img_norm.reshape(-1, 3)
        flat_lab = cspace_convert(flat, 'sRGB1', 'CIELab')
        l_channel = flat_lab[:, 0].reshape(h, w)

        # Extract L* values within the stamp area only
        stamp_l = l_channel[stamp_area]
        if len(stamp_l) == 0:
            return np.zeros((h, w), dtype=bool), np.zeros((h, w), dtype=bool)

        # Otsu's threshold on L* values
        threshold = self._otsu_threshold(stamp_l)

        # Paper = high L* (light), Ink = low L* (dark)
        ink_mask = stamp_area & (l_channel <= threshold)
        paper_mask = stamp_area & (l_channel > threshold)

        return ink_mask, paper_mask

    @staticmethod
    def _otsu_threshold(values: np.ndarray) -> float:
        """Compute Otsu's optimal threshold for a 1D array of values.

        Pure numpy implementation — no OpenCV dependency.
        """
        # Histogram with 256 bins spanning the data range
        hist, bin_edges = np.histogram(values, bins=256)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        total = hist.sum()
        if total == 0:
            return float(np.median(values))

        sum_total = np.sum(bin_centers * hist)
        sum_bg = 0.0
        weight_bg = 0.0
        max_variance = 0.0
        best_threshold = bin_centers[0]

        for i in range(len(hist)):
            weight_bg += hist[i]
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break

            sum_bg += bin_centers[i] * hist[i]
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg

            variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if variance > max_variance:
                max_variance = variance
                best_threshold = bin_centers[i]

        return best_threshold

    # ------------------------------------------------------------------ #
    # Aggregate color computation
    # ------------------------------------------------------------------ #

    def _compute_aggregates(self, result: LayerResult) -> None:
        """Compute mean and median RGB/Lab for ink and paper layers.

        Ink pixels that sit just above the cancellation thresholds
        (dark and low-saturation) are likely cancel bleed-through.
        We exclude them from the aggregate so the ink color isn't
        pulled toward black by remnant postmark pixels.
        """
        # Ink aggregate — with cancel-noise filtering
        if result.ink_mask is not None and np.any(result.ink_mask):
            ink_pixels = self._arr[result.ink_mask]  # shape (N, 3)

            # Filter out dark, low-saturation pixels within the ink layer
            # These are likely cancellation remnants that escaped the cancel mask
            brightness = np.mean(ink_pixels, axis=1)
            max_ch = np.max(ink_pixels, axis=1)
            min_ch = np.min(ink_pixels, axis=1)
            saturation = max_ch - min_ch

            # Keep ink pixels that are brighter OR more saturated than
            # the cancel thresholds (with a small margin)
            margin = 15
            clean_mask = (
                (brightness > self.cancellation_brightness_max + margin) |
                (saturation > self.cancellation_saturation_max + margin)
            )

            clean_ink = ink_pixels[clean_mask]
            if len(clean_ink) < 10:
                # Not enough clean pixels — fall back to all ink pixels
                clean_ink = ink_pixels

            result.ink_aggregate_rgb = tuple(np.mean(clean_ink, axis=0).tolist())
            result.ink_median_rgb = tuple(np.median(clean_ink, axis=0).tolist())

            # Convert mean RGB to Lab
            mean_norm = np.array(result.ink_aggregate_rgb) / 255.0
            result.ink_aggregate_lab = tuple(
                cspace_convert(mean_norm, 'sRGB1', 'CIELab').tolist()
            )
            median_norm = np.array(result.ink_median_rgb) / 255.0
            result.ink_median_lab = tuple(
                cspace_convert(median_norm, 'sRGB1', 'CIELab').tolist()
            )

        # Paper aggregate
        if result.paper_mask is not None and np.any(result.paper_mask):
            paper_pixels = self._arr[result.paper_mask]
            result.paper_aggregate_rgb = tuple(np.mean(paper_pixels, axis=0).tolist())
            mean_norm = np.array(result.paper_aggregate_rgb) / 255.0
            result.paper_aggregate_lab = tuple(
                cspace_convert(mean_norm, 'sRGB1', 'CIELab').tolist()
            )

    # ------------------------------------------------------------------ #
    # Layer image generation (for display / export)
    # ------------------------------------------------------------------ #

    def get_layer_image(
        self, result: LayerResult, layer: str, background_color=(255, 255, 255)
    ) -> Image.Image:
        """Generate a PIL image showing only one layer.

        Args:
            result: LayerResult from separate()
            layer: 'ink', 'paper', 'cancellation', or 'stamp' (ink+paper)
            background_color: RGB tuple for masked-out areas

        Returns:
            PIL Image with only the requested layer visible
        """
        mask_map = {
            'ink': result.ink_mask,
            'paper': result.paper_mask,
            'cancellation': result.cancellation_mask,
            'stamp': (result.ink_mask | result.paper_mask) if
                     result.ink_mask is not None and result.paper_mask is not None
                     else None,
        }
        mask = mask_map.get(layer)
        if mask is None:
            return self._original.copy()

        arr = np.array(self._original)
        out = np.full_like(arr, background_color, dtype=np.uint8)
        out[mask] = arr[mask]
        return Image.fromarray(out)
