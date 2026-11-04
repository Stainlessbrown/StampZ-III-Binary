"""Export authenticated native-source layers from aligned masks."""

from pathlib import Path

import numpy as np
import tifffile

from utils.alignment_provenance import read_alignment_provenance
from utils.aligned_layer_mask import native_layer_from_aligned_mask
from utils.image_processor import load_image
from utils.layer_provenance import (
    layer_companion_path,
    read_layer_provenance,
    write_layer_provenance,
)


def export_native_layer(
    aligned_path,
    output_path,
    layer_type,
    aligned_mask,
):
    """Export a native RGBA16 TIFF and authenticated layer companion.

    Output is on the ORIGINAL scanner grid, never the aligned grid.
    Existing outputs are not overwritten.
    """

    aligned = Path(aligned_path).resolve(strict=True)
    output = Path(output_path).resolve()

    if output.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("Native layer output must be TIFF")

    companion = layer_companion_path(output)

    if output.exists() or companion.exists():
        raise FileExistsError(
            "Native layer output or provenance already exists"
        )

    # Authenticate the original acquisition and alignment independently.
    alignment = read_alignment_provenance(aligned)

    source_path = alignment["source"]["path"]

    source_image, _ = load_image(
        source_path,
        display_only=True,
    )

    pixels = getattr(source_image, "_stampz_16bit_data", None)

    if not (
        isinstance(pixels, np.ndarray)
        and pixels.dtype == np.uint16
        and pixels.ndim == 3
        and pixels.shape[2] in (3, 4)
    ):
        raise ValueError("Authenticated source lacks RGB16 data")

    encoding = getattr(
        source_image, "_stampz_16bit_encoding", None
    )

    raw_derived = getattr(
        source_image, "_stampz_is_raw", None
    )

    if encoding not in ("linear", "srgb"):
        raise ValueError("Unknown source pixel encoding")

    if type(raw_derived) is not bool:
        raise ValueError("Unknown RAW provenance")

    mask = np.asarray(aligned_mask)

    if (
        mask.ndim != 2
        or mask.dtype != np.bool_
        or list(mask.shape[::-1]) != alignment["aligned"]["size"]
    ):
        raise ValueError("Invalid aligned segmentation mask")

    geometry = alignment["geometry"]

    rgba16 = native_layer_from_aligned_mask(
        pixels,
        mask,
        geometry["transform_matrix"],
        geometry["crop_box"],
    )

    description = (
        "StampZ Linear RAW; Encoding=linear; "
        f"RAW-derived={'Yes' if raw_derived else 'No'}"
        if encoding == "linear"
        else (
            "StampZ RAW-derived; Encoding=sRGB; RAW-derived=Yes"
            if raw_derived
            else "StampZ; Encoding=sRGB; RAW-derived=No"
        )
    )

    created = False

    try:
        # Exclusive creation prevents accidental replacement.
        with open(output, "xb") as handle:
            created = True
            tifffile.imwrite(
                handle,
                rgba16,
                photometric="rgb",
                extrasamples="UNASSALPHA",
                metadata=None,
                description=description,
            )

        write_layer_provenance(
            layer_path=output,
            aligned_path=aligned,
            layer_type=layer_type,
            aligned_mask=mask,
            source_encoding=encoding,
            raw_derived=raw_derived,
        )

        # Verify the finished pair before reporting success.
        read_layer_provenance(output)

    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise

    return output, companion
