"""Display-only bridge for RAW images in StampZ.

This module transforms a copy of RAW RGB image data for human viewing.
It must never be used for sampling, calibration, color analysis, database
values, or saved analytical image data.
"""

import numpy as np
from PIL import Image

BRIDGE_VERSION = "1.0"

# Empirically validated RAW display bridge parameters.
TONE_K = 1.0
WHITE_MIX = 0.10

def analysis_rgb_to_native_raw(image: Image.Image) -> Image.Image:
    """Return a display-only native-linear version of analysis RGB.

    RAW images are sRGB gamma-encoded before StampZ analysis. This reverses
    that encoding so a RAW-derived RGB value can be displayed in the same
    native-linear state as a RAW image loaded with display_only=True.

    The input image is never modified.
    """
    arr = np.array(image)

    # Preserve alpha unchanged if present.
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError(
            f"RAW display conversion requires an RGB or RGBA image; "
            f"received mode {image.mode!r}"
        )

    rgb = arr[..., :3]

    if rgb.dtype != np.uint8:
        raise ValueError(
            f"RAW display conversion requires 8-bit display RGB data; "
            f"received {rgb.dtype}"
        )

    # Normalize the stored sRGB analysis values to 0..1.
    srgb = rgb.astype(np.float64) / 255.0

    # Exact inverse of StampZ's _apply_srgb_gamma_16bit().
    linear = np.where(
        srgb <= 0.04045,
        srgb / 12.92,
        np.power((srgb + 0.055) / 1.055, 2.4),
    )

    linear_rgb = np.rint(
        np.clip(linear, 0.0, 1.0) * 255.0
    ).astype(np.uint8)

    output = arr.copy()
    output[..., :3] = linear_rgb

    return Image.fromarray(output)

def apply_raw_display_bridge(image: Image.Image) -> Image.Image:
    """Return a display-only copy with the StampZ RAW bridge applied.

    The input image is never modified. The bridge operates directly on
    normalized RGB channel values and does not perform Lab conversion,
    gamma linearization, ICC conversion, or analytical calibration.
    """
    arr = np.array(image)

    # Preserve alpha unchanged if present.
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError(
            f"RAW display bridge requires an RGB or RGBA image; "
            f"received mode {image.mode!r}"
        )

    rgb = arr[..., :3]

    # Determine the numeric range from the actual array precision.
    if rgb.dtype == np.uint8:
        max_value = 255.0
    else:
        raise ValueError(
            f"RAW display bridge requires 8-bit display RGB data; "
            f"received {rgb.dtype}"
        )

    # Work on a floating-point copy. Original image data remains untouched.
    x = rgb.astype(np.float64) / max_value

    # Frozen StampZ RAW Display Bridge v1.
    tone = x + TONE_K * x * (1.0 - x)
    bridged = tone + WHITE_MIX * (1.0 - tone)

    bridged_rgb = np.rint(
        np.clip(bridged, 0.0, 1.0) * max_value
    ).astype(rgb.dtype)

    # Build a new array so the source image cannot be modified.
    output = arr.copy()
    output[..., :3] = bridged_rgb

    return Image.fromarray(output)