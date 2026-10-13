import time
import numpy as np
from tkinter import Tk, filedialog
from PIL import Image
from skimage.color import deltaE_ciede2000

from utils.scanner_calibration import ScannerCalibration, srgb_to_lab


PROFILE = "data/calibration/profiles/10012026.json"
BATCH_SIZE = 2048

calibration = ScannerCalibration()
assert calibration.load_profile(PROFILE)


def vectorized_cr30(rgb_values):
    """Apply the existing CR30 local correction to an RGB array."""
    rgb = np.asarray(rgb_values, dtype=np.float64)
    lab = srgb_to_lab(np.clip(rgb / 255.0, 0, 1))

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

    if len(chromatic) < 3 or len(neutral) < 3:
        raise ValueError("Insufficient CR30 anchor patches")

    results = []

    for start in range(0, len(lab), BATCH_SIZE):
        x = lab[start:start + BATCH_SIZE]

        L = x[:, 0]
        C = np.hypot(x[:, 1], x[:, 2])
        H = np.arctan2(x[:, 2], x[:, 1])

        # Chromatic anchor distances
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

        # Neutral anchor distances
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

        # Existing CR30 blending formula
        alpha = C / (C + 4.0)

        correction = (
            alpha[:, None] * chromatic_correction
            + (1.0 - alpha[:, None]) * neutral_correction
        )

        results.append(x + correction)

    return np.vstack(results)


# Select original image
root = Tk()
root.withdraw()
root.attributes("-topmost", True)

filename = filedialog.askopenfilename(
    parent=root,
    title="Select original three-stamp PNG"
)
root.destroy()

if not filename:
    raise SystemExit("No image selected.")

with Image.open(filename) as source:
    image = source.convert("RGB")

image.thumbnail((300, 300), Image.Resampling.LANCZOS)

unique_rgb = np.unique(
    np.asarray(image).reshape(-1, 3),
    axis=0
)

print("Unique RGB colors:", len(unique_rgb), flush=True)

# Existing calculation
start = time.perf_counter()

original = np.array([
    calibration.apply_to_lab(tuple(map(float, rgb)))
    for rgb in unique_rgb
], dtype=np.float64)

original_time = time.perf_counter() - start

# Vectorized calculation
start = time.perf_counter()
optimized = vectorized_cr30(unique_rgb)
optimized_time = time.perf_counter() - start

# Numerical comparison
difference = np.abs(original - optimized)
delta_e = deltaE_ciede2000(
    original.reshape(1, -1, 3),
    optimized.reshape(1, -1, 3)
).ravel()

print("\n--- CR30 BENCHMARK ---")
print(f"Original time:   {original_time:.4f} seconds")
print(f"Vectorized time: {optimized_time:.4f} seconds")
print(f"Speed improvement: {original_time / optimized_time:.1f}x")

print("\n--- ACCURACY ---")
print(f"Maximum Lab component difference: {difference.max():.12f}")
print(f"Maximum Delta E00: {delta_e.max():.12f}")
print(f"Mean Delta E00: {delta_e.mean():.12f}")
print(f"Colors with Delta E00 > 0.001: {np.sum(delta_e > 0.001)}")

print("\nBenchmark complete.")