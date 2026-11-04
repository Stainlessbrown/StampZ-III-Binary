"""
Display-only RGB conversion for authenticated aligned-image samples.

Analytical RGB, Lab, calibration, and audit data are never modified.
"""

from PIL import Image

from utils.raw_display_bridge import (
    analysis_rgb_to_raw_display_rgb,
    apply_raw_display_bridge,
)


def aligned_swatch_rgb(calibrated_rgb, source_encoding, bridge_enabled):
    """
    Convert calibrated display RGB according to original pixel encoding.

    source_encoding:
        'linear' - preserve the established linear RAW display pathway
        'srgb'   - preserve sRGB values without reversing gamma
    """
    if source_encoding not in ("linear", "srgb"):
        raise ValueError(
            f"Unknown aligned source encoding: {source_encoding!r}"
        )

    pixel = tuple(
        max(0, min(255, int(round(float(value)))))
        for value in calibrated_rgb[:3]
    )

    if source_encoding == "linear":
        return analysis_rgb_to_raw_display_rgb(
            pixel,
            bridge_enabled=bridge_enabled,
        )

    if not bridge_enabled:
        return pixel

    display_image = Image.new("RGB", (1, 1), pixel)
    return apply_raw_display_bridge(display_image).getpixel((0, 0))
