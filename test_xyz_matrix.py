import time
import warnings
import numpy as np
from PIL import Image
from tkinter import Tk, filedialog

from utils.scanner_calibration import _srgb_to_linear


M = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
], dtype=np.float64)


def run_test(name, function):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        start = time.perf_counter()
        result = function()
        elapsed = time.perf_counter() - start

    print(f"\n{name}")
    print(f"  Time: {elapsed:.4f} seconds")
    print(f"  Warnings: {len(caught)}")
    print(f"  All finite: {np.isfinite(result).all()}")

    for warning in caught[:6]:
        print(f"  Warning: {warning.message}")

    return result


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
    image = np.asarray(source.convert("RGB"))

unique_rgb = np.unique(image.reshape(-1, 3), axis=0)

print(f"Unique RGB colors: {len(unique_rgb)}")

rgb01 = unique_rgb.astype(np.float64) / 255.0
linear = _srgb_to_linear(rgb01)

print(f"Linear RGB range: {linear.min():.12f} to {linear.max():.12f}")
print(f"Linear RGB finite: {np.isfinite(linear).all()}")


# Test 1: Original matrix multiplication
original = run_test(
    "Original NumPy matrix multiplication",
    lambda: linear @ M.T
)


# Test 2: Explicit channel arithmetic
def explicit_calculation():
    xyz = np.empty_like(linear)

    for channel in range(3):
        xyz[:, channel] = (
            linear[:, 0] * M[channel, 0]
            + linear[:, 1] * M[channel, 1]
            + linear[:, 2] * M[channel, 2]
        )

    return xyz


explicit = run_test(
    "Explicit RGB channel arithmetic",
    explicit_calculation
)


# Test 3: Matrix multiplication in batches
def batched_calculation(batch_size):
    xyz = np.empty_like(linear)

    for start in range(0, len(linear), batch_size):
        end = start + batch_size
        xyz[start:end] = linear[start:end] @ M.T

    return xyz


for batch_size in [4096, 1024, 256, 64]:
    result = run_test(
        f"NumPy matrix multiplication, batch {batch_size}",
        lambda size=batch_size: batched_calculation(size)
    )

    difference = np.max(np.abs(original - result))
    print(f"  Maximum difference from original: {difference:.15f}")


difference = np.max(np.abs(original - explicit))

print("\n--- FINAL COMPARISON ---")
print(f"Maximum explicit-vs-NumPy difference: {difference:.15f}")
print(f"Original XYZ range: {original.min():.12f} to {original.max():.12f}")
print("\nDiagnostic complete. No files modified.")