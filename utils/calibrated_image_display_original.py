"""
Calibrated image display for StampZ.

Experimental display-only conversion using the active
CR30 local Lab correction.

Does not modify source images or analytical measurements.
"""

import numpy as np
from PIL import Image
from skimage.color import lab2rgb


def render_calibrated_preview(image, calibration, max_size=(600, 600)):
    """
    Return an RGB PIL image rendered through the existing
    scanner calibration's Lab correction.

    This first version prioritizes correctness over speed.
    """

    if not calibration.is_valid:
        raise ValueError("A valid scanner calibration is required.")

    preview = image.copy()
    preview.thumbnail(max_size, Image.Resampling.LANCZOS)
    preview = preview.convert("RGB")

    pixels = np.asarray(preview)
    height, width, _ = pixels.shape

    # Convert each distinct RGB color only once.
    unique_rgb, inverse = np.unique(
        pixels.reshape(-1, 3),
        axis=0,
        return_inverse=True
    )

    calibrated_lab = np.array([
        calibration.apply_to_lab(tuple(map(float, rgb)))
        for rgb in unique_rgb
    ], dtype=np.float64)

    # Convert calibrated Lab to display sRGB.
    display_rgb = lab2rgb(
        calibrated_lab.reshape(1, -1, 3)
    ).reshape(-1, 3)

    display_rgb = np.clip(
        np.rint(display_rgb * 255.0),
        0,
        255
    ).astype(np.uint8)

    result = display_rgb[inverse].reshape(height, width, 3)

    return Image.fromarray(result, mode="RGB")