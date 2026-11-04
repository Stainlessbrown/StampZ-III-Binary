"""Authenticate native-source separated layers before analytical use."""

from pathlib import Path

import numpy as np
import tifffile

from utils.layer_provenance import (
    layer_companion_path,
    read_layer_provenance,
)


class NativeLayerPreparationError(ValueError):
    """A native analytical layer cannot be safely opened."""


def prepare_native_layer(image, image_path):
    """Authenticate native-layer TIFFs and their loaded analytical pixels."""

    path = Path(image_path).resolve()

    if path.suffix.lower() not in (".tif", ".tiff"):
        return image

    companion = layer_companion_path(path)

    # A native-layer marker identifies an exported analytical layer
    # even if its companion has subsequently gone missing.
    with tifffile.TiffFile(path) as tif:
        description = (tif.pages[0].description or "").lower()

    identified = (
        companion.exists()
        or description.startswith("stampz linear raw; encoding=")
        or description.startswith("stampz raw-derived; encoding=")
        or description.startswith("stampz; encoding=")
    )

    if not identified:
        return image

    try:
        record = read_layer_provenance(path)

        pixels = getattr(image, "_stampz_16bit_data", None)

        if not (
            isinstance(pixels, np.ndarray)
            and pixels.dtype == np.uint16
            and pixels.ndim == 3
            and pixels.shape[2] == 3
        ):
            raise ValueError("Native RGB16 analytical pixels unavailable")

        actual = tifffile.imread(path)

        if (
            actual.dtype != np.uint16
            or actual.ndim != 3
            or actual.shape[2] != 4
            or pixels.shape != actual[:, :, :3].shape
            or not np.array_equal(pixels, actual[:, :, :3])
        ):
            raise ValueError("Loaded RGB16 pixels differ from authenticated TIFF")

        if getattr(image, "_stampz_16bit_encoding", None) != record["source_encoding"]:
            raise ValueError("Loaded pixel encoding differs from provenance")

        if getattr(image, "_stampz_is_raw", None) is not record["raw_derived"]:
            raise ValueError("Loaded RAW provenance differs from provenance record")

        alpha = getattr(image, "_stampz_alpha_mask", None)

        if (
            not isinstance(alpha, np.ndarray)
            or alpha.shape != actual.shape[:2]
            or not np.array_equal(alpha != 0, actual[:, :, 3] != 0)
        ):
            raise ValueError("Loaded transparency differs from authenticated layer")

        # Authentication has passed. Reconstruct the leveled display
        # while retaining original acquisition pixels for analysis.
        from utils.image_processor import load_image
        from utils.aligned_image_preparation import prepare_aligned_image
        from utils.aligned_layer_working import create_aligned_working_layer
        from utils.layer_provenance import decode_layer_mask

        aligned_path = record["alignment"]["path"]

        aligned_image, _ = load_image(
            aligned_path, display_only=True
        )

        aligned_image = prepare_aligned_image(
            aligned_image, aligned_path
        )

        if not hasattr(aligned_image, "_stampz_alignment_record"):
            raise ValueError("Authenticated alignment unavailable")

        aligned_mask = decode_layer_mask(
            record["segmentation_mask"]
        )

        working = create_aligned_working_layer(
            aligned_image, aligned_mask
        )

        # Native exclusion mask is on the original scanner grid.
        native_mask = actual[:, :, 3] == 65535

        source = aligned_image._stampz_alignment_source_image
        source16 = getattr(source, "_stampz_16bit_data", None)

        if (
            not isinstance(source16, np.ndarray)
            or source16.dtype != np.uint16
            or source16.shape[:2] != native_mask.shape
        ):
            raise ValueError("Original native RGB16 source unavailable")

        # Preserve the authenticated analytical context.
        working._stampz_alignment_record = (
            aligned_image._stampz_alignment_record
        )
        working._stampz_alignment_source_image = source
        working._stampz_alignment_source_metadata = (
            aligned_image._stampz_alignment_source_metadata
        )
        working._stampz_native_layer_mask = native_mask
        working._stampz_native_layer_record = record
        working._stampz_authenticated_native_layer = True
        working._stampz_is_raw = record["raw_derived"]

        return working

    except Exception as exc:
        raise NativeLayerPreparationError(
            f"Native layer cannot be authenticated: {exc}"
        ) from exc
