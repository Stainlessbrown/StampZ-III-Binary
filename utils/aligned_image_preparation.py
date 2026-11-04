"""
Central preparation of aligned images for native-pixel analysis.

Display pixels remain separate from authoritative source pixels.
Ordinary images retain their existing behavior.
"""

from pathlib import Path

from utils.alignment_provenance import (
    companion_path,
    read_alignment_provenance,
)


class AlignmentPreparationError(ValueError):
    """An aligned image cannot be safely prepared for analysis."""


def prepare_aligned_image(image, image_path):
    """
    Attach verified original-source image and alignment geometry.

    Does not replace display pixels or modify color measurements.
    """
    path = Path(image_path).resolve()
    companion = companion_path(path)

    is_aligned = (
        path.stem.lower().endswith("_aligned")
        or companion.exists()
    )

    if not is_aligned:
        return image

    try:
        record = read_alignment_provenance(path)

        from utils.image_processor import load_image

        source_path = record["source"]["path"]
        source_image, source_metadata = load_image(
            source_path,
            display_only=True,
        )

        expected_size = tuple(record["source"]["size"])

        if source_image.size != expected_size:
            raise ValueError(
                "Original source dimensions do not match provenance"
            )

        if image.size != tuple(record["aligned"]["size"]):
            raise ValueError(
                "Aligned image dimensions do not match provenance"
            )

        if source_metadata.get("original_bit_depth") == 16:
            import numpy as np

            source_data = getattr(
                source_image, "_stampz_16bit_data", None
            )

            if not (
                isinstance(source_data, np.ndarray)
                and source_data.dtype == np.uint16
                and source_data.ndim == 3
                and source_data.shape[:2]
                    == (source_image.height, source_image.width)
                and source_data.shape[2] >= 3
                and getattr(
                    source_image, "_stampz_16bit_encoding", None
                ) in ("linear", "srgb")
            ):
                raise ValueError(
                    "Original 16-bit analytical data unavailable"
                )

        image._stampz_alignment_record = record
        image._stampz_alignment_source_image = source_image
        image._stampz_alignment_source_metadata = source_metadata

        return image

    except Exception as exc:
        raise AlignmentPreparationError(
            f"Aligned image cannot be authenticated: {exc}"
        ) from exc
