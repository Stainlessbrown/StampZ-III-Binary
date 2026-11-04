"""
StampZ-III alignment provenance.

Creates atomic JSON companion records linking aligned images to
their original acquisition and reference image.

No image pixels are modified.
"""

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PROVENANCE_VERSION = 1


def sha256_file(path):
    """Calculate SHA-256 of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def companion_path(aligned_path):
    """Return the JSON companion filename for an aligned image."""
    return Path(aligned_path).with_suffix(".alignment.json")


def write_alignment_provenance(
    source_path,
    aligned_path,
    reference_path,
    transform_matrix,
    crop_box,
    reference_size,
    source_size,
):
    """Write a versioned alignment record after image saving succeeds."""

    source = Path(source_path).resolve(strict=True)
    aligned = Path(aligned_path).resolve(strict=True)
    reference = Path(reference_path).resolve(strict=True)

    if source == aligned:
        raise ValueError("Source and aligned image must be different files")

    matrix = (
        transform_matrix.tolist()
        if hasattr(transform_matrix, "tolist")
        else transform_matrix
    )

    if not isinstance(matrix, (list, tuple)) or len(matrix) not in (2, 3):
        raise ValueError("Invalid transformation matrix")

    expected_columns = 3
    if any(
        not isinstance(row, (list, tuple))
        or len(row) != expected_columns
        for row in matrix
    ):
        raise ValueError("Invalid transformation matrix shape")

    matrix = [[float(value) for value in row] for row in matrix]

    if not all(math.isfinite(value) for row in matrix for value in row):
        raise ValueError("Transformation contains nonfinite values")

    if len(matrix) == 2:
        determinant = (
            matrix[0][0] * matrix[1][1]
            - matrix[0][1] * matrix[1][0]
        )
    else:
        a, b, c = matrix
        determinant = (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )

    if abs(determinant) < 1e-12:
        raise ValueError("Transformation is singular")

    width, height = map(int, source_size)
    ref_width, ref_height = map(int, reference_size)
    left, top, right, bottom = map(int, crop_box)

    if width <= 0 or height <= 0 or ref_width <= 0 or ref_height <= 0:
        raise ValueError("Invalid image dimensions")

    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("Invalid crop box")

    record = {
        "schema": "stampz.alignment_provenance",
        "version": PROVENANCE_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(source),
            "sha256": sha256_file(source),
            "size": [width, height],
        },
        "aligned": {
            "path": str(aligned),
            "sha256": sha256_file(aligned),
            "size": [ref_width, ref_height],
        },
        "reference": {
            "path": str(reference),
            "sha256": sha256_file(reference),
            "size": [ref_width, ref_height],
        },
        "geometry": {
            "transform_matrix": matrix,
            "crop_box": [left, top, right, bottom],
            "coordinate_origin": "top-left",
            "transform_direction": "cropped-source-to-reference",
        },
    }

    destination = companion_path(aligned)
    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".stampz_alignment_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, destination)
        temporary = None

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return destination
