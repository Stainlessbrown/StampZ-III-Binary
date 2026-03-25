#!/usr/bin/env python3
"""
Quick IR channel test - run this on a 64-bit RGBI scan to see if
cancellation ink is transparent in infrared.

Usage:
    python3 test_ir_channel.py /path/to/your/scan.tif
"""

import sys
import numpy as np
import matplotlib.pyplot as plt

try:
    import tifffile
except ImportError:
    print("ERROR: tifffile not installed. Run:  pip install tifffile")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python3 test_ir_channel.py /path/to/scan.tif")
    sys.exit(1)

filepath = sys.argv[1]
print(f"Loading: {filepath}")

img = tifffile.imread(filepath)
print(f"  Shape: {img.shape}")
print(f"  Dtype: {img.dtype}")

if img.ndim != 3:
    print("ERROR: Expected a multi-channel image (height x width x channels)")
    sys.exit(1)

channels = img.shape[2]
print(f"  Channels: {channels}")

if channels < 4:
    print("This is an RGB image — no IR channel present.")
    print("You need to scan with RGBI (64-bit) mode enabled in VueScan.")
    sys.exit(0)

# Split channels
rgb = img[:, :, :3]
ir  = img[:, :,  3]

# Normalise to 0-1 for display (handles both 8-bit and 16-bit)
max_val = float(np.iinfo(img.dtype).max) if np.issubdtype(img.dtype, np.integer) else 1.0
rgb_norm = (rgb / max_val)
ir_norm  = (ir  / max_val)

# Build a simple cancellation candidate mask:
#   dark in RGB  (likely ink of any kind)  AND  bright in IR  (not absorbing IR = cancellation ink)
rgb_luminance = np.mean(rgb_norm, axis=2)
rgb_dark  = rgb_luminance < 0.35
ir_bright = ir_norm       > 0.50
cancel_mask = rgb_dark & ir_bright

# Display (convert rgb to uint8 for imshow)
rgb_display = np.clip(rgb_norm * 255, 0, 255).astype(np.uint8)

fig, axes = plt.subplots(1, 4, figsize=(20, 6))
fig.suptitle("IR Channel Cancellation Test", fontsize=14)

axes[0].imshow(rgb_display)
axes[0].set_title("RGB (visible light)")
axes[0].axis("off")

axes[1].imshow(ir_norm, cmap="gray")
axes[1].set_title("IR Channel\n(bright = IR-transparent = cancellation?)")
axes[1].axis("off")

axes[2].imshow(rgb_luminance, cmap="gray")
axes[2].set_title("RGB Luminance\n(dark = ink of any kind)")
axes[2].axis("off")

axes[3].imshow(cancel_mask, cmap="gray")
axes[3].set_title("Candidate cancellation mask\n(dark RGB + bright IR)")
axes[3].axis("off")

plt.tight_layout()
plt.show()

print("\nWhat to look for:")
print("  Panel 2 (IR): cancellation ink should appear BRIGHT, stamp design DARK")
print("  Panel 4 (Mask): should highlight cancellation strokes, not stamp design")
print("  If panel 2 looks like panel 3 — the inks don't separate in IR.")
