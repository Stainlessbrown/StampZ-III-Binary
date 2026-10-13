import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from PIL import Image, ImageTk

from utils.scanner_calibration import ScannerCalibration
from utils.calibrated_image_display import render_calibrated_preview

profile = Path("data/calibration/profiles/10012026.json")

calibration = ScannerCalibration()

if not calibration.load_profile(str(profile)):
    raise RuntimeError(f"Could not load calibration profile: {profile}")

print(f"Calibration loaded: {calibration.profile_name}")
print(f"Reference patches: {len(calibration.patch_results)}")

root = tk.Tk()
root.withdraw()

filename = filedialog.askopenfilename(
    title="Choose an image for calibrated display testing",
    filetypes=[
        ("Images", "*.tif *.tiff *.png *.jpg *.jpeg"),
        ("All files", "*.*"),
    ],
)

if not filename:
    root.destroy()
    raise SystemExit

with Image.open(filename) as source:
    original = source.copy()

original.thumbnail((600, 600), Image.Resampling.LANCZOS)
original = original.convert("RGB")

print("Rendering calibrated preview...")
calibrated = render_calibrated_preview(
    original, calibration, max_size=(600, 600)
)

output = Path(filename).with_name(
    Path(filename).stem + "_CR30_calibrated.png"
)
calibrated.save(output)
print(f"Calibrated image saved: {output}")

root.deiconify()
root.title("StampZ — Experimental Calibrated Image Display")

frame = tk.Frame(root)
frame.pack(padx=12, pady=12)

original_photo = ImageTk.PhotoImage(original)
calibrated_photo = ImageTk.PhotoImage(calibrated)

for column, (title, photo) in enumerate([
    ("Original RGB", original_photo),
    ("CR30 Calibrated", calibrated_photo),
]):
    tk.Label(
        frame, text=title, font=("Arial", 13, "bold")
    ).grid(row=0, column=column, pady=8)

    tk.Label(
        frame, image=photo
    ).grid(row=1, column=column, padx=8)

root.mainloop()
