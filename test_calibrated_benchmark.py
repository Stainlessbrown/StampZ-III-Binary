import time
from tkinter import Tk, filedialog
from PIL import Image

from utils.scanner_calibration import ScannerCalibration
from utils.calibrated_image_display import render_calibrated_preview

# Load the existing CR30 calibration profile
calibration = ScannerCalibration()
assert calibration.load_profile(
    "data/calibration/profiles/10012026.json"
)

# Select the original test image
root = Tk()
root.withdraw()
root.lift()
root.attributes("-topmost", True)

filename = filedialog.askopenfilename(
    parent=root,
    title="Select original three-stamp PNG",
    filetypes=[
        ("Images", "*.png *.tif *.tiff"),
        ("All files", "*.*"),
    ],
)

root.destroy()

if not filename:
    raise SystemExit("No image selected.")

# Load image without modifying the original file
with Image.open(filename) as source:
    original = source.convert("RGB")

print(f"\nOriginal dimensions: {original.size}", flush=True)

# Benchmark several display sizes
for size in (300, 600, 1000, 1500, None):
    print(f"Testing {size}px...", flush=True)

    start = time.perf_counter()

    preview = render_calibrated_preview(
        original,
        calibration,
        max_size=(size, size) if size is not None else None
    )

    elapsed = time.perf_counter() - start

    print(
        f"{size}px limit | {preview.size} | "
        f"{elapsed:.2f} seconds",
        flush=True
    )

print("\nBenchmark complete.", flush=True)