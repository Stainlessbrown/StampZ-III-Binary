"""
Calibrated image display for StampZ.

Display-only CR30 local Lab correction.
Uses vectorized calculations and 256-color conversion batches.

Does not modify source images, analytical measurements,
calibration profiles, or database values.
"""

import numpy as np
from PIL import Image
from skimage.color import lab2rgb

from utils.scanner_calibration import srgb_to_lab


BATCH_SIZE = 256


def _vectorized_cr30(rgb_values, calibration):
    """Apply the existing CR30 local Lab correction in batches."""

    scanned = np.asarray(
        [p.scanned_lab for p in calibration.patch_results],
        dtype=np.float64
    )
    reference = np.asarray(
        [p.reference_lab for p in calibration.patch_results],
        dtype=np.float64
    )

    corrections = reference - scanned

    anchor_chroma = np.hypot(scanned[:, 1], scanned[:, 2])
    chromatic_idx = np.where(anchor_chroma >= 5.0)[0]
    neutral_idx = np.where(anchor_chroma < 5.0)[0]

    if len(chromatic_idx) == 0 or len(neutral_idx) == 0:
        raise ValueError("CR30 calibration anchors are incomplete.")

    chromatic_anchors = scanned[chromatic_idx]
    chromatic_C = np.hypot(
        chromatic_anchors[:, 1],
        chromatic_anchors[:, 2]
    )
    chromatic_H = np.arctan2(
        chromatic_anchors[:, 2],
        chromatic_anchors[:, 1]
    )

    results = []

    for start in range(0, len(rgb_values), BATCH_SIZE):
        rgb = np.asarray(
            rgb_values[start:start + BATCH_SIZE],
            dtype=np.float64
        )

        # RGB-to-Lab conversion in small batches.
        lab = srgb_to_lab(np.clip(rgb / 255.0, 0.0, 1.0))

        L = lab[:, 0]
        C = np.hypot(lab[:, 1], lab[:, 2])
        H = np.arctan2(lab[:, 2], lab[:, 1])

        # Three nearest chromatic anchors.
        dh = np.arctan2(
            np.sin(H[:, None] - chromatic_H[None, :]),
            np.cos(H[:, None] - chromatic_H[None, :])
        )

        distances = np.sqrt(
            (
                (L[:, None] - chromatic_anchors[None, :, 0])
                / 35.0
            ) ** 2
            + (
                (C[:, None] - chromatic_C[None, :])
                / 25.0
            ) ** 2
            + (dh / 0.35) ** 2
        )

        order = np.argsort(distances, axis=1)[:, :3]
        chosen = chromatic_idx[order]

        chosen_distances = np.take_along_axis(
            distances, order, axis=1
        )

        weights = 1.0 / ((chosen_distances + 0.05) ** 4)
        weights /= weights.sum(axis=1, keepdims=True)

        chromatic_correction = np.sum(
            corrections[chosen] * weights[:, :, None],
            axis=1
        )

        # Three nearest neutral anchors.
        neutral_distances = (
            np.abs(
                L[:, None] - scanned[neutral_idx, 0][None, :]
            ) / 20.0
        )

        neutral_order = np.argsort(
            neutral_distances, axis=1
        )[:, :3]

        neutral_chosen = neutral_idx[neutral_order]

        chosen_neutral_distances = np.take_along_axis(
            neutral_distances,
            neutral_order,
            axis=1
        )

        neutral_weights = (
            1.0 / ((chosen_neutral_distances + 0.1) ** 2)
        )
        neutral_weights /= neutral_weights.sum(
            axis=1, keepdims=True
        )

        neutral_correction = np.sum(
            corrections[neutral_chosen]
            * neutral_weights[:, :, None],
            axis=1
        )

        # Preserve the original CR30 blending formula.
        alpha = C / (C + 4.0)

        correction = (
            alpha[:, None] * chromatic_correction
            + (1.0 - alpha[:, None]) * neutral_correction
        )

        results.append(lab + correction)

    return np.vstack(results)


def render_calibrated_preview(
    image,
    calibration,
    max_size=(600, 600)
):
    """
    Return a calibrated RGB PIL image for display only.

    max_size=(600, 600): conventional preview.
    max_size=None: retain original image resolution.
    """

    if not calibration.is_valid:
        raise ValueError("A valid scanner calibration is required.")

    if len(calibration.patch_results) < 20:
        raise ValueError("Insufficient calibration patch results.")

    preview = image.copy()

    if max_size is not None:
        preview.thumbnail(
            max_size,
            Image.Resampling.LANCZOS
        )

    preview = preview.convert("RGB")

    pixels = np.asarray(preview)
    height, width, _ = pixels.shape

    # Process each distinct RGB color only once.
    unique_rgb, inverse = np.unique(
        pixels.reshape(-1, 3),
        axis=0,
        return_inverse=True
    )

    calibrated_lab = _vectorized_cr30(
        unique_rgb, calibration
    )

    # Convert Lab to display RGB in 256-color batches.
    display_rgb = np.empty(
        (len(calibrated_lab), 3),
        dtype=np.uint8
    )

    for start in range(
        0, len(calibrated_lab), BATCH_SIZE
    ):
        batch = calibrated_lab[
            start:start + BATCH_SIZE
        ]

        rgb = lab2rgb(
            batch.reshape(1, -1, 3)
        ).reshape(-1, 3)

        display_rgb[
            start:start + len(batch)
        ] = np.clip(
            np.rint(rgb * 255.0),
            0,
            255
        ).astype(np.uint8)

    result = display_rgb[inverse].reshape(
        height, width, 3
    )

    return Image.fromarray(result, mode="RGB")