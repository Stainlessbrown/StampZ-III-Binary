"""Map reference sampling regions to original, uninterpolated pixels."""

import numpy as np


def native_sample_indices(
    source_shape, reference_size, transform, crop_box,
    marker_xy, sample_size, sample_type="circle"
):
    """Return native source pixel indices for a reference sample region.

    Reference markers use bottom-left Cartesian coordinates.
    Alignment matrices map cropped source -> top-left reference.
    """

    source_h, source_w = map(int, source_shape[:2])
    ref_w, ref_h = map(int, reference_size)

    if min(source_h, source_w, ref_w, ref_h) <= 0:
        raise ValueError("Invalid image dimensions")

    if sample_type not in ("circle", "rectangle"):
        raise ValueError("Unsupported sample type")

    sw, sh = map(float, sample_size)

    if not np.isfinite([sw, sh]).all() or sw <= 0 or sh <= 0:
        raise ValueError("Invalid sample dimensions")

    if not np.isfinite(marker_xy).all():
        raise ValueError("Invalid marker coordinates")

    # Match StampZ's existing integer-coordinate conventions.
    x, y = (round(float(v)) for v in marker_xy)
    py = ref_h - y

    half_w = sw / 2.0
    half_h = (sw if sample_type == "circle" else sh) / 2.0

    left = max(0, int(x - half_w))
    right = min(ref_w, int(x + half_w))
    top = max(0, int(py - half_h))
    bottom = min(ref_h, int(py + half_h))

    empty = (
        np.empty(0, dtype=np.intp),
        np.empty(0, dtype=np.intp)
    )

    if left >= right or top >= bottom:
        return empty

    # Reproduce existing StampZ circle behavior after clipping.
    center_x = (left + right) / 2.0
    center_y = (top + bottom) / 2.0
    radius = min(right - left, bottom - top) / 2.0

    M = np.asarray(transform, dtype=np.float64)

    if M.shape == (2, 3):
        H = np.vstack((M, [0.0, 0.0, 1.0]))
    elif M.shape == (3, 3):
        H = M.copy()
    else:
        raise ValueError("Transform must be 2x3 or 3x3")

    if not np.isfinite(H).all() or abs(np.linalg.det(H)) < 1e-12:
        raise ValueError("Invalid or singular transform")

    if len(crop_box) != 4:
        raise ValueError("Invalid crop box")

    crop_x, crop_y = map(float, crop_box[:2])
    inverse = np.linalg.inv(H)

    corners = np.array([
        [left, top, 1],
        [right, top, 1],
        [right, bottom, 1],
        [left, bottom, 1],
    ], dtype=np.float64).T

    projected = inverse @ corners

    if np.any(np.abs(projected[2]) < 1e-12):
        raise ValueError("Invalid inverse projection")

    positions = projected[:2] / projected[2]
    positions[0] += crop_x
    positions[1] += crop_y

    sx0 = max(0, int(np.floor(positions[0].min())) - 2)
    sx1 = min(source_w, int(np.ceil(positions[0].max())) + 3)
    sy0 = max(0, int(np.floor(positions[1].min())) - 2)
    sy1 = min(source_h, int(np.ceil(positions[1].max())) + 3)

    if sx0 >= sx1 or sy0 >= sy1:
        return empty

    yy, xx = np.mgrid[sy0:sy1, sx0:sx1]

    cx = xx.astype(np.float64) - crop_x
    cy = yy.astype(np.float64) - crop_y

    denominator = H[2, 0] * cx + H[2, 1] * cy + H[2, 2]
    valid = np.abs(denominator) > 1e-12

    with np.errstate(divide="ignore", invalid="ignore"):
        rx = (
            H[0, 0] * cx + H[0, 1] * cy + H[0, 2]
        ) / denominator

        ry = (
            H[1, 0] * cx + H[1, 1] * cy + H[1, 2]
        ) / denominator

    inside = (
        valid &
        (rx >= left) &
        (rx < right) &
        (ry >= top) &
        (ry < bottom)
    )

    if sample_type == "circle":
        inside &= (
            (rx - center_x) ** 2 +
            (ry - center_y) ** 2 <= radius ** 2
        )

    return yy[inside], xx[inside]


def native_sample_pixels(source_rgb, *args, **kwargs):
    """Select original RGB values without resampling the image."""

    if (
        not isinstance(source_rgb, np.ndarray)
        or source_rgb.ndim != 3
        or source_rgb.shape[2] < 3
    ):
        raise ValueError("Expected an H x W x C RGB array")

    rows, cols = native_sample_indices(
        source_rgb.shape, *args, **kwargs
    )

    return source_rgb[rows, cols, :3].copy()
