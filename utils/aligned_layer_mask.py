"""Transfer an aligned segmentation mask to original 16-bit source pixels."""

import numpy as np


def native_layer_from_aligned_mask(
    source_pixels, aligned_mask, transform, crop_box
):
    """
    Return native-source-grid uint16 RGBA pixels.

    Mask membership is assigned by nearest-neighbor lookup in the
    aligned reference. Retained RGB values are copied without alteration.

    Original alpha=0 pixels are excluded. Partially transparent source
    pixels are also excluded to avoid ambiguous analytical color values.
    """
    source = np.asarray(source_pixels)
    mask = np.asarray(aligned_mask)

    if source.dtype != np.uint16:
        raise ValueError("Source pixels must be uint16")

    if source.ndim != 3 or source.shape[2] not in (3, 4):
        raise ValueError("Source must be 16-bit RGB or RGBA")

    if mask.ndim != 2 or mask.dtype != np.bool_:
        raise ValueError("Aligned mask must be a 2D boolean array")

    sh, sw = source.shape[:2]
    rh, rw = mask.shape

    if min(sh, sw, rh, rw) <= 0:
        raise ValueError("Invalid image dimensions")

    M = np.asarray(transform, dtype=np.float64)

    if M.shape == (2, 3):
        H = np.vstack((M, [0.0, 0.0, 1.0]))
    elif M.shape == (3, 3):
        H = M
    else:
        raise ValueError("Invalid alignment transform")

    if not np.isfinite(H).all():
        raise ValueError("Nonfinite alignment transform")

    if abs(np.linalg.det(H)) < 1e-12:
        raise ValueError("Singular alignment transform")

    if len(crop_box) != 4:
        raise ValueError("Invalid crop box")

    x0, y0, x1, y1 = map(int, crop_box)

    if not (0 <= x0 < x1 <= sw and 0 <= y0 < y1 <= sh):
        raise ValueError("Crop outside original source")

    yy, xx = np.mgrid[y0:y1, x0:x1]

    cx = xx.astype(np.float64) - x0
    cy = yy.astype(np.float64) - y0

    denominator = H[2, 0] * cx + H[2, 1] * cy + H[2, 2]

    valid = (
        np.isfinite(denominator)
        & (np.abs(denominator) > 1e-12)
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        rx = (
            H[0, 0] * cx + H[0, 1] * cy + H[0, 2]
        ) / denominator

        ry = (
            H[1, 0] * cx + H[1, 1] * cy + H[1, 2]
        ) / denominator

    valid &= np.isfinite(rx) & np.isfinite(ry)

    # Nearest-neighbor mask classification; no RGB interpolation.
    safe_rx = np.where(valid, rx, -1.0)
    safe_ry = np.where(valid, ry, -1.0)

    ix = np.floor(safe_rx + 0.5).astype(np.int64)
    iy = np.floor(safe_ry + 0.5).astype(np.int64)

    valid &= (
        (ix >= 0) & (ix < rw)
        & (iy >= 0) & (iy < rh)
    )

    selected = np.zeros(cx.shape, dtype=bool)
    selected[valid] = mask[iy[valid], ix[valid]]

    if source.shape[2] == 4:
        selected &= source[y0:y1, x0:x1, 3] == 65535

    source_mask = np.zeros((sh, sw), dtype=bool)
    source_mask[y0:y1, x0:x1] = selected

    output = np.empty((sh, sw, 4), dtype=np.uint16)
    output[:, :, :3] = 65535
    output[:, :, 3] = 0

    output[:, :, :3][source_mask] = source[:, :, :3][source_mask]
    output[:, :, 3][source_mask] = 65535

    return output
