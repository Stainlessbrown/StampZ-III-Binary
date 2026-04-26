#!/usr/bin/env python3
"""Live sample model for StampZ.

Owns the current PIL image plus a dict of sample markers keyed by their
1-based index. Each sample entry caches the sampled RGB/Lab so the group
average and each marker's delta_e can be recomputed incrementally as
markers are dragged, arrow-nudged, or optimised.

This module deliberately stays UI-agnostic (no Tk) so it can be unit-tested
and reused by both the canvas HUD and the Results/Compare panel.

Usage:
    model = LiveSampleModel()
    model.set_image(pil_image)
    model.on_change(lambda changed_indices, model: ...)
    model.upsert_sample(1, marker_dict)  # marker_dict from gui/canvas.py
    best_xy = model.optimize_position(1)
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _make_temp_coord(marker: dict):
    """Build a duck-typed CoordinatePoint-like object for _sample_area_color.

    Mirrors the TempCoord pattern already used in
    `ColorAnalyzer.extract_sample_colors_from_coordinates` so we reuse
    the exact same sampling path (and therefore scanner-calibration,
    circle masking, stddev, etc.).
    """
    # Local imports to avoid importing Tk or heavy modules at module load
    from utils.coordinate_db import SampleAreaType

    class _TempCoord:
        def __init__(self, x, y, sample_type, width, height, anchor):
            self.x = x
            self.y = y
            self.sample_type = (
                SampleAreaType.CIRCLE if str(sample_type).lower() == "circle"
                else SampleAreaType.RECTANGLE
            )
            self.sample_size = (float(width), float(height))
            self.anchor_position = anchor

    x, y = marker["image_pos"]
    return _TempCoord(
        x=x,
        y=y,
        sample_type=marker.get("sample_type", "rectangle"),
        width=marker.get("sample_width", 10),
        height=marker.get("sample_height", 10),
        anchor=marker.get("anchor", "center"),
    )


# --------------------------------------------------------------------------- #
# LiveSampleModel
# --------------------------------------------------------------------------- #

class LiveSampleModel:
    """Maintains live RGB/Lab/ΔE state for a handful of sample markers."""

    def __init__(self):
        self._image: Optional[Image.Image] = None
        # index (1-based marker id) -> dict with pos, size, rgb, lab,
        # delta_e, enabled, is_paper
        self._samples: Dict[int, dict] = {}
        # Cached per-role means (over *enabled* samples in that role).
        # ``False`` = ink, ``True`` = paper. Each entry is the QC mean
        # (with the same outlier rule the Results panel uses), or None
        # when that role has fewer than 2 enabled samples.
        self._avg_lab_by_role: Dict[bool, Optional[Tuple[float, float, float]]] = {
            False: None, True: None,
        }
        self._avg_rgb_by_role: Dict[bool, Optional[Tuple[float, float, float]]] = {
            False: None, True: None,
        }
        self._listeners: List[Callable[[List[int], "LiveSampleModel"], None]] = []

        # Cached analyzer; created lazily so importing this module doesn't
        # drag in color_analyzer's optional deps up front.
        self._analyzer = None

    # ----- lifecycle ----- #

    def set_image(self, image: Optional[Image.Image]) -> None:
        """Swap the PIL image. Samples are kept (caller may clear)."""
        self._image = image
        # Existing samples are stale against the new image; re-sample each.
        reindexed = list(self._samples.keys())
        for i in reindexed:
            self._resample_one(i)
        self._recompute_average_and_delta_e()
        if reindexed:
            self._notify(reindexed)

    def clear_samples(self) -> None:
        if not self._samples:
            return
        removed = list(self._samples.keys())
        self._samples.clear()
        self._avg_lab_by_role = {False: None, True: None}
        self._avg_rgb_by_role = {False: None, True: None}
        self._notify(removed)

    def has_image(self) -> bool:
        return self._image is not None

    # ----- listeners ----- #

    def on_change(
        self,
        callback: Callable[[List[int], "LiveSampleModel"], None],
    ) -> Callable[[], None]:
        """Register a listener. Returns an unsubscribe function."""
        self._listeners.append(callback)

        def _unsub():
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass
        return _unsub

    def _notify(self, changed: List[int]) -> None:
        # Defensive copy so listeners can't mutate during iteration
        for cb in list(self._listeners):
            try:
                cb(changed, self)
            except Exception as e:
                # Listeners must not break the model loop
                print(f"LiveSampleModel listener error: {e}")

    # ----- sample CRUD ----- #

    def upsert_sample(self, index: int, marker: dict) -> None:
        """Add or update a sample at the given 1-based index.

        `marker` is the canvas marker dict with keys: image_pos, sample_type,
        sample_width, sample_height, anchor.
        
        Existing ``enabled`` and ``is_paper`` flags are preserved across
        updates so dragging / nudging a marker doesn't reset its role.
        """
        prev = self._samples.get(index)
        enabled = prev.get("enabled", True) if prev else True
        is_paper = bool(prev.get("is_paper", False)) if prev else False

        self._samples[index] = {
            "index": index,
            "image_pos": tuple(marker["image_pos"]),
            "sample_type": marker.get("sample_type", "rectangle"),
            "sample_width": marker.get("sample_width", 10),
            "sample_height": marker.get("sample_height", 10),
            "anchor": marker.get("anchor", "center"),
            "enabled": enabled,
            "is_paper": is_paper,
            "rgb": None,
            "lab": None,
            "delta_e": None,
        }
        self._resample_one(index)
        self._recompute_average_and_delta_e()
        # All samples' delta_e may shift when the group average shifts, so
        # signal all indices as changed — cheap for N ≤ 6.
        self._notify(list(self._samples.keys()))

    def remove_sample(self, index: int) -> None:
        if index in self._samples:
            del self._samples[index]
            self._recompute_average_and_delta_e()
            self._notify(list(self._samples.keys()) + [index])

    def set_enabled(self, index: int, enabled: bool) -> None:
        s = self._samples.get(index)
        if not s or s.get("enabled") == enabled:
            return
        s["enabled"] = enabled
        self._recompute_average_and_delta_e()
        self._notify(list(self._samples.keys()))

    def set_paper(self, index: int, is_paper: bool) -> None:
        """Tag a sample as paper (True) or ink (False).
        
        Drives the same ink/paper grouping the Results panel uses, so
        the on-canvas ΔE HUD computes each marker's distance against
        its own group's QC mean and ink samples don't pollute paper
        readings (or vice-versa).
        """
        s = self._samples.get(index)
        if not s:
            return
        new_val = bool(is_paper)
        if bool(s.get("is_paper", False)) == new_val:
            return
        s["is_paper"] = new_val
        self._recompute_average_and_delta_e()
        self._notify(list(self._samples.keys()))

    # ----- accessors ----- #

    @property
    def samples(self) -> Dict[int, dict]:
        """Read-only view of the sample dict (do not mutate)."""
        return self._samples

    def get_sample(self, index: int) -> Optional[dict]:
        return self._samples.get(index)

    def get_delta_e(self, index: int) -> Optional[float]:
        s = self._samples.get(index)
        return s["delta_e"] if s else None

    def get_delta_components(self, index: int) -> Optional[Dict[str, float]]:
        """Return the ΔL/ΔC/ΔH breakdown for a sample, or None.
        
        Same shape as ``utils.lab_difference.lab_difference_components``.
        Useful for the canvas HUD and any UI that wants to show *which
        axis* the difference is on (lightness, chroma, or hue) rather
        than just the scalar ΔE.
        """
        s = self._samples.get(index)
        if not s:
            return None
        return s.get("delta_components")

    def get_average_lab(
        self, is_paper: Optional[bool] = None,
    ) -> Optional[Tuple[float, float, float]]:
        """Return the cached QC mean for one role (or, by default, ink).
        
        ``is_paper=False`` -> ink mean, ``is_paper=True`` -> paper mean,
        ``None`` (the default) -> ink mean if available, else paper.
        """
        if is_paper is None:
            return (
                self._avg_lab_by_role.get(False)
                or self._avg_lab_by_role.get(True)
            )
        return self._avg_lab_by_role.get(bool(is_paper))

    # ----- optimisation ----- #

    def optimize_position(
        self,
        index: int,
        radius_px: int = 5,
        step_px: int = 1,
    ) -> Optional[Tuple[float, float]]:
        """Local grid search minimising ΔE-to-average-of-other-enabled-samples.

        Effective radius is clamped to
        `min(user_radius, max(3, max(sample_width, sample_height)))`
        so the search never drifts farther than roughly the marker's own
        footprint. Returns the best (x, y) or None if search can't run
        (no image / fewer than 2 enabled samples).
        """
        if self._image is None:
            return None
        sample = self._samples.get(index)
        if not sample:
            return None

        # Need at least one *other* enabled sample IN THE SAME ROLE to
        # define a target. Optimising a paper marker should pull it
        # toward the paper-group mean, never toward ink (and vice-versa)
        # — same grouping rule the canvas HUD and Results panel use.
        sample_role = bool(sample.get("is_paper", False))
        other_labs = [
            s["lab"] for i, s in self._samples.items()
            if i != index
            and bool(s.get("is_paper", False)) == sample_role
            and s.get("enabled")
            and s.get("lab") is not None
        ]
        if not other_labs:
            return None

        target_lab = (
            sum(l[0] for l in other_labs) / len(other_labs),
            sum(l[1] for l in other_labs) / len(other_labs),
            sum(l[2] for l in other_labs) / len(other_labs),
        )

        sample_dim = max(int(sample["sample_width"]), int(sample["sample_height"]))
        effective_radius = min(max(1, int(radius_px)), max(3, sample_dim))
        step = max(1, int(step_px))

        x0, y0 = sample["image_pos"]
        best_xy = (x0, y0)
        best_de = float("inf")
        analyzer = self._get_analyzer()

        # Build a mutable copy of the marker dict we can re-point each iter
        probe_marker = dict(sample)

        for dy in range(-effective_radius, effective_radius + 1, step):
            for dx in range(-effective_radius, effective_radius + 1, step):
                probe_marker["image_pos"] = (x0 + dx, y0 + dy)
                rgb_lab = self._sample_marker_rgb_lab(probe_marker, analyzer)
                if rgb_lab is None:
                    continue
                _, lab = rgb_lab
                de = self._delta_e(lab, target_lab, analyzer)
                if de < best_de:
                    best_de = de
                    best_xy = (x0 + dx, y0 + dy)

        # Commit the best position
        if best_xy != (x0, y0):
            sample["image_pos"] = best_xy
            self._resample_one(index)
            self._recompute_average_and_delta_e()
            self._notify(list(self._samples.keys()))
        return best_xy

    # ----- internals ----- #

    def _get_analyzer(self):
        if self._analyzer is None:
            from utils.color_analyzer import ColorAnalyzer
            self._analyzer = ColorAnalyzer()
        return self._analyzer

    def _sample_marker_rgb_lab(self, marker: dict, analyzer):
        """Run `_sample_area_color` for a marker, return (rgb, lab) or None."""
        if self._image is None:
            return None
        try:
            temp_coord = _make_temp_coord(marker)
            rgb_pixels, _rgb_sd, _lab_sd = analyzer._sample_area_color(
                self._image, temp_coord
            )
            if not rgb_pixels:
                return None
            avg_rgb = analyzer._calculate_average_color(rgb_pixels)
            lab = analyzer.rgb_to_lab(avg_rgb)
            return avg_rgb, lab
        except Exception as e:
            print(f"LiveSampleModel._sample_marker_rgb_lab failed: {e}")
            return None

    def _resample_one(self, index: int) -> None:
        s = self._samples.get(index)
        if not s or self._image is None:
            return
        analyzer = self._get_analyzer()
        rgb_lab = self._sample_marker_rgb_lab(s, analyzer)
        if rgb_lab is None:
            s["rgb"] = None
            s["lab"] = None
            return
        s["rgb"], s["lab"] = rgb_lab

    def _recompute_average_and_delta_e(self) -> None:
        """Recompute per-role QC means and per-sample ΔE.
        
        Splits enabled samples into ink (``is_paper=False``) and paper
        (``is_paper=True``) groups, then — for each group with at
        least 2 enabled samples — runs the analyzer's
        ``_calculate_quality_controlled_average`` (the same outlier
        rule the Results panel uses) to get the group mean. Each
        sample's ΔE is its distance from *its own* group's QC mean.
        Groups with <2 enabled samples produce ``delta_e=None`` for
        their members (ΔE isn't meaningful with one or zero peers).
        
        This guarantees the canvas HUD and the Results panel agree
        sample-for-sample, and that ink samples don't pollute the
        paper group's mean (or vice-versa).
        """
        # Bucket enabled samples by role.
        by_role: Dict[bool, List[dict]] = {False: [], True: []}
        for s in self._samples.values():
            if not s.get("enabled") or s.get("lab") is None:
                continue
            by_role[bool(s.get("is_paper", False))].append(s)
        
        analyzer = self._get_analyzer()
        # Reset role caches; populate per group below.
        self._avg_lab_by_role = {False: None, True: None}
        self._avg_rgb_by_role = {False: None, True: None}
        
        for role, group_samples in by_role.items():
            if len(group_samples) < 2:
                continue
            labs = [s["lab"] for s in group_samples]
            rgbs = [
                s["rgb"] for s in group_samples if s.get("rgb") is not None
            ]
            # Need matching length pairs for the QC helper. If RGB is
            # missing for any sample (shouldn't happen in practice but
            # defensive), fall back to a plain mean of the labs.
            if len(rgbs) == len(labs):
                try:
                    qc = analyzer._calculate_quality_controlled_average(
                        labs, rgbs,
                    )
                    self._avg_lab_by_role[role] = qc["avg_lab"]
                    self._avg_rgb_by_role[role] = qc["avg_rgb"]
                    continue
                except Exception as e:
                    print(
                        f"LiveSampleModel: QC averaging failed for "
                        f"role={'paper' if role else 'ink'}: {e}"
                    )
            n = len(labs)
            self._avg_lab_by_role[role] = (
                sum(l[0] for l in labs) / n,
                sum(l[1] for l in labs) / n,
                sum(l[2] for l in labs) / n,
            )
            if rgbs:
                m = len(rgbs)
                self._avg_rgb_by_role[role] = (
                    sum(r[0] for r in rgbs) / m,
                    sum(r[1] for r in rgbs) / m,
                    sum(r[2] for r in rgbs) / m,
                )
        
        # Per-sample ΔE vs. its own group's QC mean. We also stash the
        # ΔL/ΔC/ΔH decomposition so the canvas HUD and Results panel
        # can show *which axis* the disagreement is on — essential for
        # interpreting near-neutral blues where a single ΔE scalar is
        # often misleading.
        from utils.lab_difference import lab_difference_components
        for s in self._samples.values():
            if s.get("lab") is None or not s.get("enabled"):
                s["delta_e"] = None
                s["delta_components"] = None
                continue
            role = bool(s.get("is_paper", False))
            group_mean = self._avg_lab_by_role.get(role)
            if group_mean is None:
                s["delta_e"] = None
                s["delta_components"] = None
            else:
                s["delta_e"] = self._delta_e(s["lab"], group_mean, analyzer)
                try:
                    s["delta_components"] = lab_difference_components(
                        s["lab"], group_mean,
                    )
                except Exception as e:
                    print(
                        f"LiveSampleModel: Δ components failed "
                        f"for sample {s.get('index')}: {e}"
                    )
                    s["delta_components"] = None

    @staticmethod
    def _delta_e(lab1, lab2, analyzer) -> float:
        try:
            return float(analyzer.calculate_delta_e(lab1, lab2))
        except Exception:
            # Fallback to CIE76 if the analyzer's path fails for any reason
            dl = lab1[0] - lab2[0]
            da = lab1[1] - lab2[1]
            db = lab1[2] - lab2[2]
            return math.sqrt(dl * dl + da * da + db * db)
