"""Group raw images into frame sequences and classify them (pure functions, no database).

A *sequence* is the set of images one camera returned for one command sequence on one sol
(``sol, instrument, sequence_id``). Frames are ordered by spacecraft clock (SCLK), not by the
UTC date: SCLK is the instrument's own time stamp and the feed's UTC dates are known to be wrong
around landing (sol 0).

Classification is a heuristic over metadata only (pointing and timing), never over pixels:

* ``fixed_pointing``  — the camera stayed pointed at one place: playing the frames shows change
  over time (e.g. a dust devil, a helicopter flight, a descent).
* ``pointing_sweep``  — the pointing changed between frames: playing them is a pan across a
  mosaic, *not* motion in the scene.
* ``vehicle_fixed``   — a camera bolted to the rover, lander or helicopter body (Hazcams, EDL
  cameras, LCAM, SkyCam, CacheCam): the mast pointing in the metadata does not apply to it, so
  playback shows change over time *from the vehicle's viewpoint* (the vehicle may be moving).
* ``single_exposure`` — every frame has the same SCLK: tiles or alternative products of one
  exposure, not a time series.
* ``unclassified``    — not enough metadata to tell.
"""

from __future__ import annotations

import itertools
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from mars_explorer.ingest.cameras import CameraGroup, camera_info

SequenceKind = Literal[
    "fixed_pointing", "pointing_sweep", "vehicle_fixed", "single_exposure", "unclassified"
]

MAST_GROUPS = frozenset({CameraGroup.NAVCAM, CameraGroup.MASTCAMZ, CameraGroup.SUPERCAM})
"""Cameras on the remote-sensing mast: ``mast_az``/``mast_el`` describe their pointing."""
VEHICLE_FIXED_GROUPS = frozenset(
    {
        CameraGroup.HAZCAM_FRONT,
        CameraGroup.HAZCAM_REAR,
        CameraGroup.SKYCAM,
        CameraGroup.CACHECAM,
        CameraGroup.EDL,
        CameraGroup.HELICOPTER,
    }
)
"""Cameras fixed to a vehicle body. (Arm cameras — SHERLOC, PIXL — have no pointing metadata.)"""

POINTING_TOLERANCE_DEG = 0.5
"""Mast az/el differences below this are treated as the same pointing (metadata rounding)."""

MIN_FRAMES = 2

KIND_NOTES: dict[SequenceKind, str] = {
    "fixed_pointing": (
        "The camera kept the same pointing: playback shows real change over time between exposures."
    ),
    "pointing_sweep": (
        "The camera pointing changed between frames: playback is a pan across mosaic tiles, "
        "not motion in the scene."
    ),
    "vehicle_fixed": (
        "Camera fixed to the vehicle body: playback shows change over time from the "
        "vehicle's viewpoint (the vehicle itself may be moving)."
    ),
    "single_exposure": (
        "All frames share one exposure time (tiles or alternative products of a single "
        "exposure): this is not a time series."
    ),
    "unclassified": (
        "Pointing metadata is missing, so the app cannot tell a time series from a pan."
    ),
}


@dataclass(frozen=True, slots=True)
class FrameMeta:
    """The subset of an image record the sequence logic needs."""

    image_id: str
    sol: int
    instrument: str
    sequence_id: str | None
    sclk: float | None
    date_taken_utc: datetime | None = None
    lmst: str | None = None
    mast_az: float | None = None
    mast_el: float | None = None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True)
class Frame:
    meta: FrameMeta
    t_offset_s: float | None
    """Seconds since the first frame, from SCLK (None if the frame has no SCLK)."""


@dataclass(slots=True)
class FrameSequence:
    id: str
    sol: int
    instrument: str
    sequence_id: str | None
    frames: list[Frame]
    kind: SequenceKind
    duration_s: float | None
    median_interval_s: float | None
    distinct_pointings: int | None
    notes: list[str] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        return len(self.frames)


def sequence_key(sol: int, instrument: str, sequence_id: str | None) -> str:
    """Stable, URL-safe identifier: ``<sol>-<instrument>-<sequence_id|NOSEQ>``."""
    return f"{sol}-{instrument}-{sequence_id or 'NOSEQ'}"


def parse_sequence_key(key: str) -> tuple[int, str, str | None] | None:
    sol_text, sep, rest = key.partition("-")
    instrument, sep2, sequence = rest.rpartition("-")
    if not (sep and sep2 and sol_text.isdigit() and instrument):
        return None
    return int(sol_text), instrument, None if sequence == "NOSEQ" else sequence


def _order_key(meta: FrameMeta) -> tuple[float, float, str]:
    sclk = meta.sclk if meta.sclk is not None else float("inf")
    stamp = meta.date_taken_utc.timestamp() if meta.date_taken_utc else float("inf")
    return sclk, stamp, meta.image_id


def _distinct_pointings(frames: Sequence[FrameMeta]) -> int | None:
    pointings = [(f.mast_az, f.mast_el) for f in frames]
    if any(az is None or el is None for az, el in pointings):
        return None
    clusters: list[tuple[float, float]] = []
    for az, el in pointings:
        assert az is not None and el is not None
        if not any(
            abs(az - caz) <= POINTING_TOLERANCE_DEG and abs(el - cel) <= POINTING_TOLERANCE_DEG
            for caz, cel in clusters
        ):
            clusters.append((az, el))
    return len(clusters)


def classify(
    frames: Sequence[FrameMeta],
    instrument: str | None = None,
) -> tuple[SequenceKind, float | None, float | None, int | None]:
    """Return ``(kind, duration_s, median_interval_s, distinct_pointings)``."""
    sclks = [f.sclk for f in frames if f.sclk is not None]
    duration = (max(sclks) - min(sclks)) if len(sclks) >= 2 else None
    distinct_times = sorted(set(sclks))
    intervals = [b - a for a, b in itertools.pairwise(distinct_times)]
    median_interval = statistics.median(intervals) if intervals else None
    group = camera_info(instrument or frames[0].instrument).group if frames else None
    pointings = _distinct_pointings(frames) if group in MAST_GROUPS else None

    if len(sclks) == len(frames) and len(frames) >= 2 and duration == 0:
        return "single_exposure", 0.0, None, pointings
    if group in VEHICLE_FIXED_GROUPS and duration is not None:
        return "vehicle_fixed", duration, median_interval, None
    if pointings is None or duration is None:
        return "unclassified", duration, median_interval, pointings
    if pointings == 1:
        return "fixed_pointing", duration, median_interval, pointings
    return "pointing_sweep", duration, median_interval, pointings


def build_sequence(frames: Iterable[FrameMeta]) -> FrameSequence:
    ordered = sorted(frames, key=_order_key)
    if not ordered:
        raise ValueError("a sequence needs at least one frame")
    first = ordered[0]
    kind, duration, median_interval, pointings = classify(ordered)
    t0 = first.sclk
    built = [
        Frame(meta=f, t_offset_s=(f.sclk - t0) if (f.sclk is not None and t0 is not None) else None)
        for f in ordered
    ]
    notes = [KIND_NOTES[kind]]
    sizes = {(f.width, f.height) for f in ordered}
    if len(sizes) > 1:
        notes.append("Frames have different sizes (subframes or downsampling); playback rescales.")
    if any(f.sclk is None for f in ordered):
        notes.append("Some frames have no SCLK; they are placed last and real-time playback skips.")
    return FrameSequence(
        id=sequence_key(first.sol, first.instrument, first.sequence_id),
        sol=first.sol,
        instrument=first.instrument,
        sequence_id=first.sequence_id,
        frames=built,
        kind=kind,
        duration_s=duration,
        median_interval_s=median_interval,
        distinct_pointings=pointings,
        notes=notes,
    )


def group_sequences(
    frames: Iterable[FrameMeta], min_frames: int = MIN_FRAMES
) -> list[FrameSequence]:
    """Group frames by ``(sol, instrument, sequence_id)``; keep groups of ``min_frames`` or more.

    Result order: sol, then start SCLK, then instrument."""
    groups: dict[tuple[int, str, str | None], list[FrameMeta]] = defaultdict(list)
    for frame in frames:
        groups[(frame.sol, frame.instrument, frame.sequence_id)].append(frame)
    sequences = [build_sequence(g) for g in groups.values() if len(g) >= max(1, min_frames)]
    sequences.sort(
        key=lambda s: (
            s.sol,
            s.frames[0].meta.sclk if s.frames[0].meta.sclk is not None else float("inf"),
            s.instrument,
        )
    )
    return sequences
