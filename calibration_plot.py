#!/usr/bin/env python3
"""
Calibration Diagnostic Plot

Plots per-channel scanner response vs reference values.
Shows the ideal 45° line, actual patch measurements, the fitted
correction curve, and per-patch deviation arrows.

Usage:
    python3 calibration_plot.py [profile.json]

If no profile is given, uses the most recent profile in
data/calibration/profiles/.
"""

import json
import os
import sys
import glob
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt


def load_profile(path=None):
    """Load a calibration profile JSON. Auto-finds latest if path is None."""
    if path is None:
        profile_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data', 'calibration', 'profiles'
        )
        profiles = sorted(glob.glob(os.path.join(profile_dir, '*.json')))
        if not profiles:
            print("No calibration profiles found.")
            sys.exit(1)
        path = profiles[-1]
        print(f"Using profile: {os.path.basename(path)}")

    with open(path) as f:
        return json.load(f), path


def plot_calibration(profile, profile_path):
    """Generate the per-channel diagnostic plot."""
    patches = profile['patch_results']
    coeffs = profile.get('correction_coefficients', {})
    profile_name = profile.get('profile_name', os.path.basename(profile_path))

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    fig.suptitle(
        f"Scanner Calibration Diagnostic — {profile_name}",
        fontsize=13, fontweight='bold', y=0.98
    )

    channels = [('R', 0, 'red'), ('G', 1, 'green'), ('B', 2, 'blue')]

    for ax, (ch_name, ch_idx, ch_color) in zip(axes, channels):
        # Extract scanned vs reference for this channel
        scanned = [p['scanned_rgb'][ch_idx] for p in patches]
        reference = [p['digital_rgb'][ch_idx] for p in patches]
        names = [p['name'] for p in patches]
        corrected = [p['corrected_rgb'][ch_idx] for p in patches
                     if p.get('corrected_rgb')]

        # 45° ideal line
        ax.plot([0, 255], [0, 255], color='gray', linewidth=1,
                linestyle='--', alpha=0.6, label='Ideal (no error)')

        # Deviation arrows: scanned → reference
        for sx, ry, name in zip(scanned, reference, names):
            ax.annotate(
                '', xy=(sx, ry), xytext=(sx, sx),
                arrowprops=dict(arrowstyle='->', color=ch_color,
                                alpha=0.3, linewidth=1.2)
            )

        # Scatter: actual measurements
        ax.scatter(scanned, reference, c=ch_color, s=60, zorder=5,
                   edgecolors='black', linewidths=0.5, label='Patch measurements')

        # Patch name labels
        for sx, ry, name in zip(scanned, reference, names):
            # Offset label to avoid overlap with point
            ax.annotate(
                name, (sx, ry),
                textcoords='offset points', xytext=(5, 5),
                fontsize=6.5, alpha=0.8, color='#333'
            )

        # Smooth polynomial fit through data points showing scanner response
        if len(scanned) >= 3:
            order = np.argsort(scanned)
            xs = np.array(scanned)[order]
            yr = np.array(reference)[order]
            try:
                # 2nd-order polynomial fit through the data
                poly_coeffs = np.polyfit(xs, yr, 2)
                x_smooth = np.linspace(0, 255, 256)
                y_smooth = np.clip(np.polyval(poly_coeffs, x_smooth), 0, 255)
                ax.plot(x_smooth, y_smooth, color=ch_color, linewidth=2.5,
                        alpha=0.6, label='Scanner response (fit)')
            except Exception:
                pass

        # Fitted correction curve (if coefficients available)
        if ch_name in coeffs:
            c = coeffs[ch_name]
            x_fit = np.linspace(0, 255, 256)
            if len(c) == 3:
                y_fit = c[0] * x_fit**2 + c[1] * x_fit + c[2]
            else:
                y_fit = c[0] * x_fit + c[1]
            y_fit = np.clip(y_fit, 0, 255)
            ax.plot(x_fit, y_fit, color='black', linewidth=1.5,
                    alpha=0.5, linestyle=':', label='Correction curve')

        # Corrected points (after calibration)
        if corrected and len(corrected) == len(scanned):
            ax.scatter(scanned, corrected, c='none', s=40, zorder=4,
                       edgecolors=ch_color, linewidths=1.2,
                       linestyle='--', marker='D', alpha=0.6,
                       label='After correction')

        ax.set_xlim(-5, 260)
        ax.set_ylim(-5, 260)
        ax.set_xlabel(f'Scanned {ch_name} value', fontsize=10)
        ax.set_ylabel(f'Reference {ch_name} value', fontsize=10)
        ax.set_title(f'{ch_name} Channel', fontsize=11, fontweight='bold',
                     color=ch_color)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2)
        ax.legend(fontsize=7, loc='upper left')

    # Summary stats at bottom
    delta_e_before = [p.get('delta_e_before', 0) for p in patches]
    delta_e_after = [p.get('delta_e_after', 0) for p in patches]
    avg_before = sum(delta_e_before) / len(delta_e_before) if delta_e_before else 0
    avg_after = sum(delta_e_after) / len(delta_e_after) if delta_e_after else 0

    fig.text(
        0.5, 0.01,
        f"Avg ΔE: {avg_before:.1f} (before) → {avg_after:.1f} (after)  |  "
        f"Patches: {len(patches)}  |  "
        f"Correction: {'quadratic' if any(len(c) == 3 for c in coeffs.values()) else 'linear'}",
        ha='center', fontsize=9, color='gray'
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    plt.show()


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else None
    profile, profile_path = load_profile(path)
    plot_calibration(profile, profile_path)
