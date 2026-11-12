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



def read_alignment_provenance(aligned_path):
    """
    Read and authenticate an aligned image's provenance record.

    Returns the verified record or raises an exception.
    Never silently falls back to aligned-image pixels.
    """
    import numpy as np
    from PIL import Image

    aligned = Path(aligned_path).resolve(strict=True)
    companion = companion_path(aligned)

    with open(companion, "r", encoding="utf-8") as handle:
        record = json.load(handle)

    if not isinstance(record, dict):
        raise ValueError("Invalid alignment provenance record")

    if record.get("schema") != "stampz.alignment_provenance":
        raise ValueError("Unknown alignment provenance schema")

    if type(record.get("version")) is not int or record["version"] != PROVENANCE_VERSION:
        raise ValueError("Unsupported alignment provenance version")

    paths = {}

    for role in ("source", "aligned", "reference"):
        entry = record.get(role)

        if not isinstance(entry, dict):
            raise ValueError(f"Missing {role} provenance")

        recorded_path = entry.get("path")
        recorded_hash = entry.get("sha256")
        recorded_size = entry.get("size")

        if not isinstance(recorded_path, str) or not recorded_path:
            raise ValueError(f"Invalid {role} path")

        if (
            not isinstance(recorded_hash, str)
            or len(recorded_hash) != 64
            or any(c not in "0123456789abcdef" for c in recorded_hash)
        ):
            raise ValueError(f"Invalid {role} SHA-256")

        if (
            not isinstance(recorded_size, list)
            or len(recorded_size) != 2
            or any(type(v) is not int or v <= 0 for v in recorded_size)
        ):
            raise ValueError(f"Invalid {role} dimensions")

        path = Path(recorded_path).resolve(strict=True)

        if role == "aligned" and path != aligned:
            raise ValueError("Companion belongs to a different aligned image")

        if not path.is_file():
            raise ValueError(f"{role} is not a regular file")

        if sha256_file(path) != recorded_hash:
            raise ValueError(f"{role} SHA-256 mismatch")

        if path.suffix.lower() in (
            ".cr3", ".cr2", ".nef", ".arw",
            ".orf", ".rw2", ".dng"
        ):
            from utils.image_processor import load_image
            source_image, _ = load_image(
                str(path), display_only=True
            )
            actual_size = list(source_image.size)
        else:
            with Image.open(path) as image:
                actual_size = list(image.size)

        if actual_size != recorded_size:
            raise ValueError(f"{role} dimensions mismatch")

        paths[role] = path

    if len(set(paths.values())) != 3:
        raise ValueError("Source, aligned and reference must be distinct files")

    if record["aligned"]["size"] != record["reference"]["size"]:
        raise ValueError("Aligned and reference dimensions differ")

    geometry = record.get("geometry")

    if not isinstance(geometry, dict):
        raise ValueError("Missing alignment geometry")

    if geometry.get("coordinate_origin") != "top-left":
        raise ValueError("Unsupported coordinate origin")

    if geometry.get("transform_direction") != "cropped-source-to-reference":
        raise ValueError("Unsupported transform direction")

    matrix = geometry.get("transform_matrix")

    try:
        M = np.asarray(matrix, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid transformation matrix") from exc

    if M.shape not in ((2, 3), (3, 3)):
        raise ValueError("Invalid transformation matrix dimensions")

    if not np.isfinite(M).all():
        raise ValueError("Nonfinite transformation matrix")

    H = np.vstack((M, [0, 0, 1])) if M.shape == (2, 3) else M

    if abs(float(np.linalg.det(H))) < 1e-12:
        raise ValueError("Singular transformation matrix")

    crop = geometry.get("crop_box")
    source_width, source_height = record["source"]["size"]

    if (
        not isinstance(crop, list)
        or len(crop) != 4
        or any(type(v) is not int for v in crop)
    ):
        raise ValueError("Invalid crop box")

    left, top, right, bottom = crop

    if not (
        0 <= left < right <= source_width
        and 0 <= top < bottom <= source_height
    ):
        raise ValueError("Crop box outside original image")

    return record
