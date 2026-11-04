"""Aligned-size presentation images for authenticated separated layers."""

import numpy as np
from PIL import Image


def create_aligned_working_layer(aligned_image, layer_mask):
    """Create an RGBA layer without changing aligned-image geometry.

    The RGB data is for presentation only. Analytical sampling must use
    authenticated native source pixels and the layer exclusion mask.
    """
    mask = np.asarray(layer_mask)

    if (
        mask.ndim != 2
        or mask.dtype != np.bool_
        or mask.shape != (aligned_image.height, aligned_image.width)
    ):
        raise ValueError("Layer mask dimensions do not match aligned image")

    rgba = np.asarray(aligned_image.convert("RGBA")).copy()

    # Preserve the existing aligned-image exclusion boundary.
    source_valid = rgba[:, :, 3] != 0

    # The separated layer can only remove eligible pixels,
    # never restore pixels excluded by the original alpha.
    eligible = mask & source_valid

    rgba[:, :, 3] = np.where(eligible, 255, 0).astype(np.uint8)

    result = Image.fromarray(rgba, "RGBA")

    return result
