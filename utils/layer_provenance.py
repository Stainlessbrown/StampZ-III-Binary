"""Versioned provenance helpers for native-source StampZ layers."""

import base64
import hashlib
import numpy as np


LAYER_PROVENANCE_VERSION = 1
LAYER_PROVENANCE_SCHEMA = "stampz.native_layer_provenance"


def encode_layer_mask(mask):
    """Encode a 2D boolean mask without losing pixel membership."""
    array = np.asarray(mask)

    if array.ndim != 2 or array.dtype != np.bool_:
        raise ValueError("Layer mask must be a 2D boolean array")

    height, width = array.shape

    if height <= 0 or width <= 0:
        raise ValueError("Invalid layer mask dimensions")

    packed = np.packbits(
        array.reshape(-1),
        bitorder="big",
    ).tobytes()

    return {
        "encoding": "packbits-base64-big",
        "size": [width, height],
        "selected_pixels": int(array.sum()),
        "sha256": hashlib.sha256(packed).hexdigest(),
        "data": base64.b64encode(packed).decode("ascii"),
    }


def decode_layer_mask(record):
    """Decode and authenticate every stored mask pixel."""
    if not isinstance(record, dict):
        raise ValueError("Invalid layer mask record")

    if record.get("encoding") != "packbits-base64-big":
        raise ValueError("Unsupported layer mask encoding")

    size = record.get("size")

    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(v) is not int or v <= 0 for v in size)
    ):
        raise ValueError("Invalid layer mask dimensions")

    width, height = size
    expected_bytes = (width * height + 7) // 8

    encoded = record.get("data")

    if not isinstance(encoded, str):
        raise ValueError("Missing layer mask data")

    try:
        packed = base64.b64decode(
            encoded,
            validate=True,
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Invalid layer mask Base64") from exc

    if len(packed) != expected_bytes:
        raise ValueError("Incorrect packed mask length")

    digest = hashlib.sha256(packed).hexdigest()

    if digest != record.get("sha256"):
        raise ValueError("Layer mask SHA-256 mismatch")

    values = np.unpackbits(
        np.frombuffer(packed, dtype=np.uint8),
        bitorder="big",
        count=width * height,
    )

    mask = values.reshape(height, width).astype(bool)

    if int(mask.sum()) != record.get("selected_pixels"):
        raise ValueError("Layer mask selected-pixel count mismatch")

    return mask


def layer_companion_path(layer_path):
    """Companion filename distinct from alignment provenance."""
    from pathlib import Path
    return Path(layer_path).with_suffix(".layer.json")


def write_layer_provenance(
    layer_path,
    aligned_path,
    layer_type,
    aligned_mask,
    source_encoding,
    raw_derived,
):
    """Authenticate a native-source TIFF before recording provenance."""
    import json
    import os
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    import tifffile

    from utils.alignment_provenance import (
        companion_path,
        read_alignment_provenance,
        sha256_file,
    )
    from utils.aligned_layer_mask import native_layer_from_aligned_mask
    from utils.image_processor import load_image

    if layer_type not in (
        "ink", "paper", "ink2", "cancellation", "stamp"
    ):
        raise ValueError("Unsupported layer type")

    if source_encoding not in ("linear", "srgb"):
        raise ValueError("Unsupported source encoding")

    if type(raw_derived) is not bool:
        raise ValueError("RAW provenance must be boolean")

    layer = Path(layer_path).resolve(strict=True)
    aligned = Path(aligned_path).resolve(strict=True)

    destination = layer_companion_path(layer)

    if destination.exists():
        raise FileExistsError(
            f"Layer provenance already exists: {destination}"
        )

    alignment = read_alignment_provenance(aligned)

    source_path = alignment["source"]["path"]

    source_image, _ = load_image(
        source_path, display_only=True
    )

    source_pixels = getattr(
        source_image, "_stampz_16bit_data", None
    )

    if source_pixels is None:
        raise ValueError("Original source lacks 16-bit pixels")

    actual_encoding = getattr(
        source_image, "_stampz_16bit_encoding", None
    )

    actual_raw = getattr(
        source_image, "_stampz_is_raw", None
    )

    if actual_encoding != source_encoding:
        raise ValueError("Source encoding mismatch")

    if actual_raw is not raw_derived:
        raise ValueError("Source RAW provenance mismatch")

    mask_record = encode_layer_mask(aligned_mask)
    mask = decode_layer_mask(mask_record)

    expected_size = alignment["aligned"]["size"]

    if list(mask.shape[::-1]) != expected_size:
        raise ValueError("Mask does not match aligned dimensions")

    geometry = alignment["geometry"]

    expected = native_layer_from_aligned_mask(
        source_pixels,
        mask,
        geometry["transform_matrix"],
        geometry["crop_box"],
    )

    actual = tifffile.imread(layer)

    if (
        actual.dtype != np.uint16
        or actual.shape != expected.shape
        or not np.array_equal(actual, expected)
    ):
        raise ValueError(
            "Exported TIFF does not match authenticated native pixels"
        )

    with tifffile.TiffFile(layer) as tif:
        page = tif.pages[0]
        description = page.description or ""

        extrasamples = tuple(
            int(value) for value in page.extrasamples
        )

    if extrasamples != (2,):
        raise ValueError("TIFF must use unassociated alpha")

    description_lower = description.lower()

    if (
        f"encoding={source_encoding}".lower()
        not in description_lower
    ):
        raise ValueError("TIFF pixel encoding description mismatch")

    expected_raw = "raw-derived=yes" if raw_derived else "raw-derived=no"

    if expected_raw not in description_lower:
        raise ValueError("TIFF RAW description mismatch")

    if source_encoding == "linear" and (
        "stampz linear raw" not in description_lower
    ):
        raise ValueError("Linear TIFF designation missing")

    if source_encoding == "srgb" and (
        "stampz linear raw" in description_lower
    ):
        raise ValueError("sRGB TIFF incorrectly designated linear")

    alignment_companion = companion_path(aligned)

    record = {
        "schema": LAYER_PROVENANCE_SCHEMA,
        "version": LAYER_PROVENANCE_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "layer_type": layer_type,
        "pixel_grid": "original-source",
        "pixel_depth": 16,
        "channels": "RGBA",
        "alpha": "unassociated-binary-exclusion",
        "source_encoding": source_encoding,
        "raw_derived": raw_derived,
        "layer": {
            "path": str(layer),
            "sha256": sha256_file(layer),
            "size": list(layer_image_size(expected)),
        },
        "alignment": {
            "path": str(aligned),
            "companion_path": str(alignment_companion),
            "companion_sha256": sha256_file(alignment_companion),
            "source_sha256": alignment["source"]["sha256"],
        },
        "segmentation_mask": mask_record,
        "mask_transfer": "source-forward-nearest-neighbor-v1",
    }

    # Atomic creation without replacing an existing companion.
    serialized = json.dumps(
        record, indent=2, allow_nan=False
    ) + "\n"

    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".stampz_layer_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

        # Publish the completed file atomically without overwriting
        # an existing provenance record.
        os.link(temporary, destination)

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return destination


def layer_image_size(array):
    """Return [width, height] for a NumPy image array."""
    return (int(array.shape[1]), int(array.shape[0]))


def read_layer_provenance(layer_path):
    """Authenticate a saved native-source layer against its original scan."""
    import json
    from pathlib import Path

    import tifffile

    from utils.alignment_provenance import (
        companion_path,
        read_alignment_provenance,
        sha256_file,
    )
    from utils.aligned_layer_mask import native_layer_from_aligned_mask
    from utils.image_processor import load_image

    layer = Path(layer_path).resolve(strict=True)
    companion = layer_companion_path(layer)

    with open(companion, "r", encoding="utf-8") as handle:
        record = json.load(handle)

    if not isinstance(record, dict):
        raise ValueError("Invalid layer provenance record")

    if record.get("schema") != LAYER_PROVENANCE_SCHEMA:
        raise ValueError("Unknown layer provenance schema")

    if (
        type(record.get("version")) is not int
        or record["version"] != LAYER_PROVENANCE_VERSION
    ):
        raise ValueError("Unsupported layer provenance version")

    if record.get("layer_type") not in (
        "ink", "paper", "ink2", "cancellation", "stamp"
    ):
        raise ValueError("Unsupported layer type")

    if (
        record.get("pixel_grid") != "original-source"
        or record.get("pixel_depth") != 16
        or record.get("channels") != "RGBA"
        or record.get("alpha") != "unassociated-binary-exclusion"
        or record.get("mask_transfer") != "source-forward-nearest-neighbor-v1"
    ):
        raise ValueError("Unsupported native-layer format")

    encoding = record.get("source_encoding")
    raw_derived = record.get("raw_derived")

    if encoding not in ("linear", "srgb"):
        raise ValueError("Invalid source encoding")

    if type(raw_derived) is not bool:
        raise ValueError("Invalid RAW provenance")

    layer_info = record.get("layer")
    alignment_info = record.get("alignment")

    if not isinstance(layer_info, dict):
        raise ValueError("Missing layer details")

    if not isinstance(alignment_info, dict):
        raise ValueError("Missing alignment details")

    if Path(layer_info.get("path", "")).resolve() != layer:
        raise ValueError("Layer provenance belongs to another file")

    if sha256_file(layer) != layer_info.get("sha256"):
        raise ValueError("Layer TIFF SHA-256 mismatch")

    aligned = Path(
        alignment_info.get("path", "")
    ).resolve(strict=True)

    alignment_companion = companion_path(aligned)

    if (
        str(alignment_companion)
        != alignment_info.get("companion_path")
    ):
        raise ValueError("Alignment companion path mismatch")

    if (
        sha256_file(alignment_companion)
        != alignment_info.get("companion_sha256")
    ):
        raise ValueError("Alignment provenance SHA-256 mismatch")

    alignment = read_alignment_provenance(aligned)

    if (
        alignment["source"]["sha256"]
        != alignment_info.get("source_sha256")
    ):
        raise ValueError("Original source SHA-256 mismatch")

    source_image, _ = load_image(
        alignment["source"]["path"], display_only=True
    )

    source_pixels = getattr(
        source_image, "_stampz_16bit_data", None
    )

    if source_pixels is None or source_pixels.dtype != np.uint16:
        raise ValueError("Original source lacks native 16-bit RGB")

    if (
        getattr(source_image, "_stampz_16bit_encoding", None)
        != encoding
    ):
        raise ValueError("Original source encoding mismatch")

    if (
        getattr(source_image, "_stampz_is_raw", None)
        is not raw_derived
    ):
        raise ValueError("Original RAW provenance mismatch")

    mask = decode_layer_mask(record.get("segmentation_mask"))

    if list(mask.shape[::-1]) != alignment["aligned"]["size"]:
        raise ValueError("Segmentation dimensions mismatch")

    geometry = alignment["geometry"]

    expected = native_layer_from_aligned_mask(
        source_pixels,
        mask,
        geometry["transform_matrix"],
        geometry["crop_box"],
    )

    actual = tifffile.imread(layer)

    if (
        actual.dtype != np.uint16
        or actual.shape != expected.shape
        or not np.array_equal(actual, expected)
    ):
        raise ValueError("Native layer does not match original source")

    if layer_info.get("size") != list(layer_image_size(actual)):
        raise ValueError("Layer dimensions mismatch")

    with tifffile.TiffFile(layer) as tif:
        page = tif.pages[0]
        description = (page.description or "").lower()
        extrasamples = tuple(int(v) for v in page.extrasamples)

    if extrasamples != (2,):
        raise ValueError("Layer TIFF must use unassociated alpha")

    if f"encoding={encoding}" not in description:
        raise ValueError("Layer TIFF encoding mismatch")

    expected_raw = (
        "raw-derived=yes" if raw_derived else "raw-derived=no"
    )

    if expected_raw not in description:
        raise ValueError("Layer TIFF RAW provenance mismatch")

    if encoding == "linear":
        if "stampz linear raw" not in description:
            raise ValueError("Missing linear RAW designation")
    elif "stampz linear raw" in description:
        raise ValueError("sRGB layer mislabeled as linear RAW")

    return record
