import time
import warnings
import numpy as np
from pathlib import Path
from tkinter import Tk, filedialog
from PIL import Image
from skimage.color import lab2rgb

from utils.scanner_calibration import ScannerCalibration

# Load CR30 profile
calibration = ScannerCalibration()
assert calibration.load_profile(
    "data/calibration/profiles/10012026.json"
)

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

image = Image.open(filename).convert("RGB")
image.thumbnail((300, 300), Image.Resampling.LANCZOS)

pixels = np.asarray(image)
unique_rgb = np.unique(
    pixels.reshape(-1, 3), axis=0
)

print("Unique RGB colors:", len(unique_rgb))

# Apply CR30 calibration once
lab_values = np.array([
    calibration.apply_to_lab(tuple(map(float, rgb)))
    for rgb in unique_rgb
], dtype=np.float64)

def convert_batches(batch_size):
    results = []
    start = time.perf_counter()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        for i in range(0, len(lab_values), batch_size):
            batch = lab_values[i:i + batch_size]
            rgb = lab2rgb(batch.reshape(1, -1, 3))
            results.append(rgb.reshape(-1, 3))

    elapsed = time.perf_counter() - start
    result = np.vstack(results)

    return result, caught, elapsed


# Original full-batch conversion
baseline, baseline_warnings, baseline_time = convert_batches(
    len(lab_values)
)

print("\nFull batch:")
print("Warnings:", len(baseline_warnings))
print("Time:", round(baseline_time, 4), "seconds")

# Smaller batches
for batch_size in (4096, 1024, 256, 64):
    result, caught, elapsed = convert_batches(batch_size)

    difference = np.max(
        np.abs(result - baseline)
    )

    print(
        f"Batch {batch_size:4d} | "
        f"Warnings: {len(caught):2d} | "
        f"Time: {elapsed:.4f}s | "
        f"Maximum RGB difference: {difference:.12f}"
    )

print("\nBatch testing complete.")