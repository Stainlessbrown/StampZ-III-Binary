
"""Native source-pixel analysis for authenticated aligned images."""

import numpy as np

from utils.alignment_sampling import native_sample_indices_from_bounds


def analyze_aligned_region(analyzer, image, bounds, sample_type):
    """Return the existing StampZ sampling result format."""

    record = image._stampz_alignment_record
    source = image._stampz_alignment_source_image

    shape = (
        "circle" if getattr(sample_type, "name", "").upper() == "CIRCLE"
        else "rectangle" if getattr(sample_type, "name", "").upper() == "RECTANGLE"
        else None
    )
    if shape is None:
        raise ValueError("Unsupported aligned sample shape")

    source_metadata = image._stampz_alignment_source_metadata
    declared_depth = source_metadata.get("original_bit_depth")

    source16 = getattr(source, "_stampz_16bit_data", None)
    use16 = source16 is not None

    # Never silently downgrade an original 16-bit acquisition.
    if declared_depth == 16 and not use16:
        raise ValueError(
            "Original source is 16-bit but native data is unavailable"
        )

    if declared_depth == 8 and use16:
        raise ValueError(
            "Original bit-depth metadata conflicts with source data"
        )

    if declared_depth not in (8, 16):
        raise ValueError(
            "Original source bit depth is missing or unsupported"
        )

    if use16:
        if (
            not isinstance(source16, np.ndarray)
            or source16.dtype != np.uint16
            or source16.ndim != 3
            or source16.shape[:2] != (source.height, source.width)
            or source16.shape[2] < 3
        ):
            raise ValueError("Invalid original 16-bit source data")

        source_array = source16
        encoding = getattr(source, "_stampz_16bit_encoding", None)
        if encoding not in ("linear", "srgb"):
            raise ValueError("Unknown original 16-bit encoding")
    else:
        source_array = np.asarray(source.convert("RGB"))
        encoding = "srgb"

    geometry = record["geometry"]

    rows, cols = native_sample_indices_from_bounds(
        source_array.shape,
        record["aligned"]["size"],
        geometry["transform_matrix"],
        geometry["crop_box"],
        bounds,
        shape,
    )

    if len(rows) == 0:
        raise ValueError("No original source pixels in sample region")

    # Authenticated working layers further restrict eligible source
    # pixels using the native-grid ink/paper exclusion mask.
    layer_mask = getattr(
        image, "_stampz_native_layer_mask", None
    )

    if layer_mask is not None:
        rows, cols = filter_native_indices_by_layer_mask(
            rows, cols, layer_mask, source_array.shape
        )

        if len(rows) == 0:
            raise ValueError(
                "No eligible original pixels in separated layer sample"
            )

    alpha = getattr(source, "_stampz_alpha_mask", None)

    if alpha is not None:
        alpha = np.asarray(alpha)
        if alpha.shape != (source.height, source.width):
            raise ValueError("Invalid source transparency mask")
        keep = alpha[rows, cols] != 0
        rows, cols = rows[keep], cols[keep]

    if use16 and source_array.shape[2] >= 4:
        keep = source_array[rows, cols, 3] != 0
        rows, cols = rows[keep], cols[keep]

    if source.mode == "RGBA":
        alpha8 = np.asarray(source.getchannel("A"))
        keep = alpha8[rows, cols] != 0
        rows, cols = rows[keep], cols[keep]

    if len(rows) == 0:
        raise ValueError("No opaque original pixels in sample region")

    rgb = source_array[rows, cols, :3].copy()

    if use16:
        if encoding == "linear":
            from utils.image_processor import _apply_srgb_gamma_16bit
            rgb = _apply_srgb_gamma_16bit(rgb)

        rgb = rgb.astype(np.float64) * (255.0 / 65535.0)
    else:
        rgb = rgb.astype(np.float64)

    if not np.isfinite(rgb).all():
        raise ValueError("Nonfinite source RGB values")

    mean = tuple(float(v) for v in rgb.mean(axis=0))
    rgb_stddev = tuple(float(v) for v in rgb.std(axis=0))

    lab = np.asarray(
        [analyzer.rgb_to_lab(tuple(pixel)) for pixel in rgb],
        dtype=np.float64,
    )

    if lab.shape != (len(rgb), 3) or not np.isfinite(lab).all():
        raise ValueError("Invalid Lab calculations")

    lab_stddev = tuple(float(v) for v in lab.std(axis=0))

    analyzer.last_sampling_bit_depth = 16 if use16 else 8
    analyzer.last_sampling_channels = source_array.shape[2]

    return [mean], rgb_stddev, lab_stddev


def filter_native_indices_by_layer_mask(
    rows, cols, native_mask, source_shape
):
    """Restrict native source indices to an authenticated layer.

    native_mask is a boolean array on the original acquisition grid.
    Sample coordinates remain in the aligned reference system.
    """
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    mask = np.asarray(native_mask)

    if (
        mask.ndim != 2
        or mask.dtype != np.bool_
        or mask.shape != tuple(source_shape[:2])
    ):
        raise ValueError("Invalid native-layer exclusion mask")

    if rows.ndim != 1 or cols.ndim != 1 or rows.shape != cols.shape:
        raise ValueError("Invalid native sampling coordinates")

    if (
        np.any(rows < 0)
        or np.any(cols < 0)
        or np.any(rows >= mask.shape[0])
        or np.any(cols >= mask.shape[1])
    ):
        raise ValueError("Sampling coordinates outside original source")

    keep = mask[rows, cols]

    return rows[keep], cols[keep]
