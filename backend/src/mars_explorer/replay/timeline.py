"""Sol timelines: place images and drives on Local Mean Solar Time (pure functions).

Images carry their own LMST (published by NASA). Drives from the MMGIS traverse only carry SCLK,
so they are placed with a *derived* SCLK -> LMST mapping calibrated on that sol's images:

    lmst_hours = lmst_ref + (sclk - sclk_ref) / SECONDS_PER_LMST_HOUR

where one Mars solar day is 88 775.244 s, so an LMST hour lasts 3 698.97 SI seconds. The
reference offset is the median over all images of the sol that have both LMST and SCLK, and the
spread of the residuals is reported so the UI can say how good the placement is.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

MARS_SOLAR_DAY_S = 88_775.244
SECONDS_PER_LMST_HOUR = MARS_SOLAR_DAY_S / 24.0


def lmst_hours(lmst: str | None) -> float | None:
    """Parse ``HH:MM:SS(.fff)`` (optionally prefixed, e.g. ``Sol-02022M16:20:47``) to hours."""
    if not lmst:
        return None
    text = lmst.rsplit("M", 1)[-1] if "M" in lmst else lmst
    parts = text.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
    except ValueError:
        return None
    if not (0 <= hours < 25 and 0 <= minutes < 60 and 0 <= seconds < 61):
        return None
    return hours + minutes / 60 + seconds / 3600


@dataclass(frozen=True, slots=True)
class LmstCalibration:
    """Linear SCLK -> LMST mapping for one sol (derived)."""

    offset_h: float
    """``lmst_hours - sclk / SECONDS_PER_LMST_HOUR`` (median over the samples)."""
    samples: int
    max_residual_s: float

    def to_lmst(self, sclk: float) -> float:
        return sclk / SECONDS_PER_LMST_HOUR + self.offset_h


def calibrate(pairs: Sequence[tuple[float, float]]) -> LmstCalibration | None:
    """Fit from ``(sclk, lmst_hours)`` pairs; None without samples."""
    if not pairs:
        return None
    offsets = [lmst - sclk / SECONDS_PER_LMST_HOUR for sclk, lmst in pairs]
    offset = statistics.median(offsets)
    residual_h = max(abs(o - offset) for o in offsets)
    return LmstCalibration(
        offset_h=offset, samples=len(pairs), max_residual_s=residual_h * SECONDS_PER_LMST_HOUR
    )
