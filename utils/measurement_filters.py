"""Shared helpers for filtering colour measurements by role (ink vs paper).

Paper measurements live in a separate measurement set inside each
StampZ analysis DB, with the set's ``image_name`` suffixed ``-p`` (see
``gui/sample_results_manager.py::_save_one_group_to_db``). Plotting
code should normally hide paper rows from K-means clusters and ΔE
calculations because paper colour and ink colour cluster in different
places, but they need to remain available for ad-hoc paper-only
analyses (e.g. a tinted-paper survey).

Use ``is_paper_image_name`` to test a single name, or
``partition_measurements_by_role`` to split a list of measurement
dicts into ``(ink, paper)``.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

PAPER_SUFFIX = "-p"


def is_paper_image_name(image_name) -> bool:
    """Return True if ``image_name`` is a paper-tagged measurement set.

    Image names are stored on each measurement (see
    ``ColorAnalysisDB.get_all_measurements``). The convention is to
    suffix the base image name with ``-p`` for paper samples;
    everything else is treated as ink. Tolerant of trailing whitespace
    and ``None``.
    """
    if not image_name:
        return False
    return str(image_name).strip().endswith(PAPER_SUFFIX)


def partition_measurements_by_role(
    measurements: Iterable[dict],
) -> Tuple[List[dict], List[dict]]:
    """Split measurement dicts into ``(ink, paper)`` lists.

    Each measurement is expected to carry an ``image_name`` field (the
    format ``ColorAnalysisDB.get_all_measurements`` returns). Rows
    whose ``image_name`` ends in ``-p`` go to ``paper``; everything
    else goes to ``ink``.
    """
    ink: List[dict] = []
    paper: List[dict] = []
    for m in measurements:
        if is_paper_image_name(m.get("image_name")):
            paper.append(m)
        else:
            ink.append(m)
    return ink, paper
