"""Compare detector candidates with human annotations or with another detector.

Matching is one-to-one: candidate/point pairs are accepted greedily from the closest, and a pair
counts only if the distance is within the tolerance. Precision and recall are only meaningful
if the annotator marked *every* object of interest in the evaluated region.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

TOLERANCE_FRACTION = 0.015
"""Minimum match tolerance as a fraction of image width (≈18 px on a 1200 px image)."""


@dataclass(frozen=True, slots=True)
class Point:
    x: float  # image px
    y: float
    r: float = 0.0  # candidate radius (0 for annotation points)


@dataclass(frozen=True, slots=True)
class MatchCounts:
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float | None:
        found = self.true_positives + self.false_positives
        return self.true_positives / found if found else None

    @property
    def recall(self) -> float | None:
        expected = self.true_positives + self.false_negatives
        return self.true_positives / expected if expected else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)


def match_points(
    detections: Sequence[Point], truth: Sequence[Point], image_width: int
) -> MatchCounts:
    """One-to-one greedy matching. A detection matches a truth point if their distance is within
    max(detection radius, TOLERANCE_FRACTION × image width)."""
    floor = TOLERANCE_FRACTION * image_width
    pairs = []
    for i, d in enumerate(detections):
        for j, t in enumerate(truth):
            distance = math.hypot(d.x - t.x, d.y - t.y)
            if distance <= max(d.r, floor):
                pairs.append((distance, i, j))
    used_d: set[int] = set()
    used_t: set[int] = set()
    for _, i, j in sorted(pairs):
        if i not in used_d and j not in used_t:
            used_d.add(i)
            used_t.add(j)
    tp = len(used_d)
    return MatchCounts(tp, len(detections) - tp, len(truth) - tp)


def agreement(a: Sequence[Point], b: Sequence[Point], image_width: int) -> float | None:
    """Symmetric agreement between two detectors (F1 with B treated as reference)."""
    if not a and not b:
        return None
    return match_points(a, b, image_width).f1 or 0.0
