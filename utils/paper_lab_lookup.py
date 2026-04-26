"""Look up a saved paper Lab from existing ``-p`` measurement sets.

This is the bridge between the cropped-image coverage workflow and
the paper data the user has already saved. Two ways in:

* ``find_saved_paper_lab(image_path)`` — auto-detect by filename.
  Strips a trailing ``-crp`` from the current image's basename and
  looks in ``Results_<base>.db`` (and ``Results_<base>-crp.db`` as a
  fallback) for the most-recent measurement set whose name ends in
  ``-p``. Returns the mean Lab plus a human-readable ``source``
  description, or ``None`` if nothing matches.

* ``list_all_paper_sets()`` — enumerate every ``-p`` measurement set
  across every analysis DB, newest-first. Used to populate the
  manual-picker dialog.

* ``compute_paper_lab(db_name, set_name)`` — fetch one specific set's
  individual samples and return the simple per-channel mean Lab.

Why mean instead of the existing quality-controlled average? We're
already pulling persisted samples that survived the user's earlier
review; the simple mean is fine and keeps this module free of GUI
dependencies. The Results panel will still apply the QC average when
the user has live in-image samples.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .measurement_filters import is_paper_image_name


@dataclass
class PaperLabSource:
    """A resolved paper Lab plus the metadata needed to describe it."""

    lab: Tuple[float, float, float]
    sample_count: int
    db_name: str          # without .db extension
    set_name: str         # the measurement set's image_name (ends in -p)
    measurement_date: str  # ISO-ish string from the DB; for sorting / display
    
    def describe(self) -> str:
        """One-line human-readable description for dialogs / banners."""
        return (
            f"set '{self.set_name}' in '{self.db_name}.db' "
            f"({self.sample_count} sample{'s' if self.sample_count != 1 else ''})"
        )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

# Suffixes we strip from the current image's basename to get the
# "original" base, in priority order. ``-crp`` is the canonical StampZ
# convention; the others are tolerated for users with looser naming.
_CROP_SUFFIXES = ("-crp", "-cropped", "_cropped")


def _candidate_base_names(image_path: str) -> List[str]:
    """Return the candidate base names to try, in priority order.
    
    For ``27-13-crp.tif`` this yields ``['27-13', '27-13-crp']`` so we
    look for the original DB first, then the crop-specific DB as a
    fallback.
    """
    base = os.path.splitext(os.path.basename(image_path))[0]
    
    candidates: List[str] = []
    seen = set()
    
    # First try: with crop suffix stripped (the common case).
    stripped = base
    for suffix in _CROP_SUFFIXES:
        if base.endswith(suffix):
            stripped = base[: -len(suffix)]
            break
    if stripped and stripped not in seen:
        candidates.append(stripped)
        seen.add(stripped)
    
    # Second try: the basename as-is (covers DBs saved while a cropped
    # image was the loaded one).
    if base and base not in seen:
        candidates.append(base)
        seen.add(base)
    
    return candidates


def _color_analysis_dir() -> str:
    """Resolve the colour-analysis directory the same way ColorAnalysisDB does."""
    stampz_data_dir = os.getenv("STAMPZ_DATA_DIR")
    if stampz_data_dir:
        return os.path.join(stampz_data_dir, "data", "color_analysis")
    # Running from source
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    return os.path.join(project_root, "data", "color_analysis")


def _is_user_facing_db(db_name: str) -> bool:
    """Skip system / averaged / library DBs when scanning for paper sets."""
    return not (
        db_name.endswith("_AVG")
        or db_name.endswith("_averages")
        or db_name.endswith("_library")
        or db_name.startswith("system_")
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def compute_paper_lab(db_name: str, set_name: str) -> Optional[PaperLabSource]:
    """Compute the mean Lab of the named ``-p`` set inside ``db_name``.
    
    Returns ``None`` if the set doesn't exist or has no individual samples.
    Filters out averaged rows (``is_averaged=True``) so we only mean over
    the original samples; otherwise an existing per-set average would
    skew the count.
    """
    if not is_paper_image_name(set_name):
        # Defensive guard; helpers shouldn't be called with non-paper sets,
        # but if they are, we silently return None so the UI logic stays clean.
        return None
    
    try:
        from .color_analysis_db import ColorAnalysisDB
    except Exception:
        return None
    
    try:
        db = ColorAnalysisDB(db_name)
        rows = db.get_measurements_for_image(set_name)
    except Exception:
        return None
    
    if not rows:
        return None
    
    # Filter to non-averaged samples. ``get_measurements_for_image``
    # doesn't always populate ``is_averaged`` for older rows, so treat
    # missing as False (= individual sample).
    samples = [r for r in rows if not r.get("is_averaged", False)]
    if not samples:
        # No individual rows; fall back to whatever's there (likely the
        # row from a paper-tagged averaged DB).
        samples = rows
    
    n = len(samples)
    if n == 0:
        return None
    
    mean_l = sum(r["l_value"] for r in samples) / n
    mean_a = sum(r["a_value"] for r in samples) / n
    mean_b = sum(r["b_value"] for r in samples) / n
    
    # Pick the most recent measurement_date as the set's date for sorting.
    dates = [r.get("measurement_date") or "" for r in samples]
    latest_date = max(dates) if dates else ""
    
    return PaperLabSource(
        lab=(float(mean_l), float(mean_a), float(mean_b)),
        sample_count=n,
        db_name=db_name,
        set_name=set_name,
        measurement_date=str(latest_date),
    )


def find_saved_paper_lab(image_path: str) -> Optional[PaperLabSource]:
    """Auto-detect a saved paper Lab for ``image_path`` by filename.
    
    Strips a trailing ``-crp`` (or ``-cropped`` / ``_cropped``) from the
    image basename to get the "original" stamp name, then searches
    ``Results_<base>.db`` and a few sensible fallbacks for the
    most-recent ``-p`` measurement set inside.
    """
    if not image_path:
        return None
    
    bases = _candidate_base_names(image_path)
    if not bases:
        return None
    
    analysis_dir = _color_analysis_dir()
    if not os.path.isdir(analysis_dir):
        return None
    
    available_dbs = {
        f[:-3] for f in os.listdir(analysis_dir)
        if f.endswith(".db") and _is_user_facing_db(f[:-3])
    }
    
    # Try each candidate base name. ``Results_<base>`` is the StampZ
    # convention; ``<base>`` itself is also accepted for users who name
    # databases manually.
    for base in bases:
        for db_name in (f"Results_{base}", base):
            if db_name not in available_dbs:
                continue
            best = _most_recent_paper_set(db_name)
            if best is not None:
                return best
    
    return None


def _most_recent_paper_set(db_name: str) -> Optional[PaperLabSource]:
    """Within ``db_name``, return the newest ``-p`` set as a PaperLabSource.
    
    The DB-layer ``get_all_measurements`` returns *all* rows including
    paper-tagged sets; the per-export paper filter we added earlier
    lives in the export layer (``ods_exporter`` / ``direct_plot3d_exporter``)
    and doesn't reach down here, which is exactly what we want for this
    lookup — we explicitly want the ``-p`` rows.
    """
    try:
        from .color_analysis_db import ColorAnalysisDB
    except Exception:
        return None
    
    try:
        db = ColorAnalysisDB(db_name)
        all_rows = db.get_all_measurements()
    except Exception:
        return None
    
    if not all_rows:
        return None
    
    # Bucket by measurement-set name, retaining only paper sets.
    by_set: dict = {}
    for r in all_rows:
        name = r.get("image_name")
        if not is_paper_image_name(name):
            continue
        by_set.setdefault(name, []).append(r)
    
    if not by_set:
        return None
    
    # Pick the set with the most recent measurement_date.
    def _set_latest(rows):
        return max((r.get("measurement_date") or "") for r in rows)
    
    newest_set_name = max(by_set, key=lambda n: _set_latest(by_set[n]))
    return compute_paper_lab(db_name, newest_set_name)


def list_all_paper_sets() -> List[PaperLabSource]:
    """Enumerate every ``-p`` measurement set across every analysis DB.
    
    Returned newest-first so the manual-picker dialog can show the most
    recently saved paper data at the top.
    """
    analysis_dir = _color_analysis_dir()
    if not os.path.isdir(analysis_dir):
        return []
    
    try:
        from .color_analysis_db import ColorAnalysisDB
    except Exception:
        return []
    
    results: List[PaperLabSource] = []
    for filename in sorted(os.listdir(analysis_dir)):
        if not filename.endswith(".db"):
            continue
        db_name = filename[:-3]
        if not _is_user_facing_db(db_name):
            continue
        
        try:
            db = ColorAnalysisDB(db_name)
            rows = db.get_all_measurements()
        except Exception:
            continue
        
        # Group paper rows by set name within this DB.
        by_set: dict = {}
        for r in rows or []:
            name = r.get("image_name")
            if not is_paper_image_name(name):
                continue
            by_set.setdefault(name, []).append(r)
        
        for set_name in by_set:
            source = compute_paper_lab(db_name, set_name)
            if source is not None:
                results.append(source)
    
    # Newest-first — helps the user spot the set they just saved.
    results.sort(key=lambda s: s.measurement_date, reverse=True)
    return results
