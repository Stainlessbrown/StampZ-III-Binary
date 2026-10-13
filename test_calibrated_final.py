import time
import warnings
import numpy as np
from tkinter import Tk, filedialog
from PIL import Image
from skimage.color import lab2rgb, deltaE_ciede2000

from utils.scanner_calibration import ScannerCalibration
from utils.scanner_calibration import srgb_to_lab

PROFILE = "data/calibration/profiles/10012026.json"

calibration = ScannerCalibration()
assert calibration.load_profile(PROFILE)

def vectorized_cr30(rgb_values):
    """Vectorized CR30 correction with 256-color RGB-to-Lab batches."""

    scanned = np.asarray(
        [p.scanned_lab for p in calibration.patch_results],
        dtype=np.float64
    )
    reference = np.asarray(
        [p.reference_lab for p in calibration.patch_results],
        dtype=np.float64
    )
    corrections = reference - scanned

    anchor_c = np.hypot(scanned[:, 1], scanned[:, 2])
    chromatic = np.where(anchor_c >= 5.0)[0]
    neutral = np.where(anchor_c < 5.0)[0]

    results = []

    for start in range(0, len(rgb_values), 256):
        rgb = np.asarray(
            rgb_values[start:start + 256],
            dtype=np.float64
        )

        # Small batch avoids large-array matrix warnings
        lab = srgb_to_lab(np.clip(rgb / 255.0, 0.0, 1.0))

        L = lab[:, 0]
        C = np.hypot(lab[:, 1], lab[:, 2])
        H = np.arctan2(lab[:, 2], lab[:, 1])

        anchors = scanned[chromatic]
        Ca = np.hypot(anchors[:, 1], anchors[:, 2])
        Ha = np.arctan2(anchors[:, 2], anchors[:, 1])

        dh = np.arctan2(
            np.sin(H[:, None] - Ha[None, :]),
            np.cos(H[:, None] - Ha[None, :])
        )

        d = np.sqrt(
            ((L[:, None] - anchors[None, :, 0]) / 35.0) ** 2
            + ((C[:, None] - Ca[None, :]) / 25.0) ** 2
            + (dh / 0.35) ** 2
        )

        order = np.argsort(d, axis=1)[:, :3]
        chosen = chromatic[order]
        distances = np.take_along_axis(d, order, axis=1)

        weights = 1.0 / ((distances + 0.05) ** 4)
        weights /= weights.sum(axis=1, keepdims=True)

        chromatic_correction = np.sum(
            corrections[chosen] * weights[:, :, None],
            axis=1
        )

        nd = np.abs(
            L[:, None] - scanned[neutral, 0][None, :]
        ) / 20.0

        norder = np.argsort(nd, axis=1)[:, :3]
        nchosen = neutral[norder]
        ndistances = np.take_along_axis(nd, norder, axis=1)

        nweights = 1.0 / ((ndistances + 0.1) ** 2)
        nweights /= nweights.sum(axis=1, keepdims=True)

        neutral_correction = np.sum(
            corrections[nchosen] * nweights[:, :, None],
            axis=1
        )

        alpha = C / (C + 4.0)

        correction = (
            alpha[:, None] * chromatic_correction
            + (1.0 - alpha[:, None]) * neutral_correction
        )

        results.append(lab + correction)

    return np.vstack(results)

root = Tk()
root.withdraw()
root.attributes("-topmost", True)

filename = filedialog.askopenfilename(
    parent=root,
    title="Select original full-resolution PNG"
)
root.destroy()

if not filename:
    raise SystemExit("No image selected.")

with Image.open(filename) as source:
    image = source.convert("RGB")

pixels = np.asarray(image)
height, width, _ = pixels.shape

print(f"Image dimensions: {width} x {height}", flush=True)

start = time.perf_counter()

unique_rgb, inverse = np.unique(
    pixels.reshape(-1, 3),
    axis=0,
    return_inverse=True
)

print(f"Unique RGB colors: {len(unique_rgb)}", flush=True)

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")

    calibrated_lab = vectorized_cr30(unique_rgb)

    display_rgb = np.empty(
        (len(calibrated_lab), 3),
        dtype=np.uint8
    )

    for i in range(0, len(calibrated_lab), 256):
        batch = calibrated_lab[i:i + 256]
        rgb = lab2rgb(batch.reshape(1, -1, 3))
        display_rgb[i:i + len(batch)] = np.clip(
            np.rint(rgb.reshape(-1, 3) * 255),
            0, 255
        ).astype(np.uint8)

elapsed = time.perf_counter() - start

print(f"Total processing time: {elapsed:.3f} seconds")
print(f"Numerical warnings: {len(caught)}")
print(f"Finite calibrated Lab: {np.isfinite(calibrated_lab).all()}")

# Verify representative colors against original CR30
indices = np.linspace(
    0, len(unique_rgb) - 1, 100,
    dtype=int
)

reference = np.array([
    calibration.apply_to_lab(
        tuple(map(float, unique_rgb[i]))
    )
    for i in indices
])

optimized = calibrated_lab[indices]

delta_e = deltaE_ciede2000(
    reference.reshape(1, -1, 3),
    optimized.reshape(1, -1, 3)
)

print(f"Maximum verification Delta E00: {delta_e.max():.12f}")

# Reconstruct full-resolution calibrated image
result = display_rgb[inverse].reshape(height, width, 3)
output = Image.fromarray(result, mode="RGB")

print("Calibrated image constructed successfully.")
print("No files saved.")

print("\nFinal benchmark complete.")