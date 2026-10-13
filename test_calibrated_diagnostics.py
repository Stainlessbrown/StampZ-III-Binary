import warnings
import numpy as np
from tkinter import Tk, filedialog
from PIL import Image
from skimage.color import lab2rgb

from utils.scanner_calibration import ScannerCalibration

calibration = ScannerCalibration()
assert calibration.load_profile(
    "data/calibration/profiles/10012026.json"
)

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

with Image.open(filename) as source:
    image = source.convert("RGB")

image.thumbnail((300, 300), Image.Resampling.LANCZOS)

pixels = np.asarray(image)
unique_rgb = np.unique(pixels.reshape(-1, 3), axis=0)

print("Unique RGB colors:", len(unique_rgb), flush=True)

calibrated_lab = np.array([
    calibration.apply_to_lab(tuple(map(float, rgb)))
    for rgb in unique_rgb
], dtype=np.float64)

print("\nCalibrated Lab ranges:")
for i, name in enumerate(("L*", "a*", "b*")):
    values = calibrated_lab[:, i]
    print(
        f"{name}: min={values.min():.3f}, "
        f"max={values.max():.3f}"
    )

finite = np.isfinite(calibrated_lab).all(axis=1)

print("\nFinite Lab colors:", int(finite.sum()))
print("Invalid Lab colors:", int((~finite).sum()))

if not finite.all():
    print("\nFirst invalid RGB inputs:")
    for rgb in unique_rgb[~finite][:10]:
        print(tuple(rgb))

print("\nTesting Lab-to-sRGB conversion...", flush=True)

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")

    display_rgb = lab2rgb(
        calibrated_lab.reshape(1, -1, 3)
    )

print("Conversion warnings:", len(caught))

for warning in caught[:10]:
    print(type(warning.message).__name__, str(warning.message))

print("Finite output values:", bool(np.isfinite(display_rgb).all()))
print("Output RGB range:",
      float(np.nanmin(display_rgb)),
      float(np.nanmax(display_rgb)))

print("\nDiagnostics complete.")