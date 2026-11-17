"""Database queries behind Mission Replay (sequences, sol timelines, mission overview)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from mars_explorer.db.models import ImageRecord, TraverseSegment, Waypoint
from mars_explorer.replay.sequences import (
    FrameMeta,
    FrameSequence,
    build_sequence,
    group_sequences,
    parse_sequence_key,
)
from mars_explorer.replay.timeline import LmstCalibration, calibrate, lmst_hours

TIMELINE_MIN_FRAMES = 2


def frame_meta(image: ImageRecord) -> FrameMeta:
    return FrameMeta(
        image_id=image.image_id,
        sol=image.sol,
        instrument=image.instrument,
        sequence_id=image.sequence_id,
        sclk=image.sclk,
        date_taken_utc=image.date_taken_utc,
        lmst=image.lmst,
        mast_az=image.mast_az,
        mast_el=image.mast_el,
        width=image.width,
        height=image.height,
    )


def _images(session: Session, sol: int | None = None) -> list[ImageRecord]:
    query = select(ImageRecord)
    if sol is not None:
        query = query.where(ImageRecord.sol == sol)
    return list(session.exec(query).all())


def list_sequences(
    session: Session, sol: int | None = None, min_frames: int = 3
) -> list[FrameSequence]:
    return group_sequences((frame_meta(i) for i in _images(session, sol)), min_frames=min_frames)


def get_sequence(session: Session, key: str) -> tuple[FrameSequence, dict[str, ImageRecord]] | None:
    parsed = parse_sequence_key(key)
    if parsed is None:
        return None
    sol, instrument, sequence_id = parsed
    query = select(ImageRecord).where(ImageRecord.sol == sol, ImageRecord.instrument == instrument)
    query = query.where(
        ImageRecord.sequence_id == sequence_id
        if sequence_id is not None
        else ImageRecord.sequence_id.is_(None)  # type: ignore[union-attr]
    )
    rows = list(session.exec(query).all())
    if not rows:
        return None
    return build_sequence(frame_meta(r) for r in rows), {r.image_id: r for r in rows}


# ---- mission overview ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SolActivity:
    sol: int
    images: int
    sequences: int
    drives: int
    drive_m: float


def mission_activity(session: Session) -> list[SolActivity]:
    """Every sol with locally stored images or a real drive, ascending."""
    image_counts: dict[int, int] = dict(
        session.exec(select(ImageRecord.sol, func.count()).group_by(ImageRecord.sol)).all()
    )
    sequence_counts = Counter(s.sol for s in list_sequences(session, min_frames=3))
    drives: dict[int, list[float]] = defaultdict(list)
    for sol, length in session.exec(select(TraverseSegment.sol, TraverseSegment.length_m)).all():
        drives[sol].append(length or 0.0)
    sols = sorted(set(image_counts) | set(drives))
    return [
        SolActivity(
            sol=sol,
            images=image_counts.get(sol, 0),
            sequences=sequence_counts.get(sol, 0),
            drives=len(drives.get(sol, [])),
            drive_m=round(sum(drives.get(sol, [])), 2),
        )
        for sol in sols
    ]


# ---- sol timeline --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimelineImage:
    image: ImageRecord
    lmst_h: float | None


@dataclass(frozen=True, slots=True)
class TimelineDrive:
    segment: TraverseSegment
    start_lmst_h: float | None
    end_lmst_h: float | None


@dataclass(frozen=True, slots=True)
class SolTimeline:
    sol: int
    images: list[TimelineImage]
    sequences: list[FrameSequence]
    drives: list[TimelineDrive]
    end_of_sol_waypoint: Waypoint | None
    calibration: LmstCalibration | None
    previous_sol: int | None
    next_sol: int | None


def sol_timeline(session: Session, sol: int) -> SolTimeline | None:
    images = sorted(
        _images(session, sol), key=lambda i: (i.sclk if i.sclk is not None else 0.0, i.image_id)
    )
    segments = list(
        session.exec(
            select(TraverseSegment)
            .where(TraverseSegment.sol == sol)
            .order_by(TraverseSegment.source_index)  # type: ignore[arg-type]
        ).all()
    )
    if not images and not segments:
        return None
    pairs = [
        (i.sclk, h) for i in images if i.sclk is not None and (h := lmst_hours(i.lmst)) is not None
    ]
    calibration = calibrate(pairs)

    def placed(sclk: float | None) -> float | None:
        if sclk is None or calibration is None:
            return None
        return round(calibration.to_lmst(sclk), 4)

    waypoint = session.exec(
        select(Waypoint).where(Waypoint.sol == sol).order_by(Waypoint.source_index.desc())  # type: ignore[attr-defined]
    ).first()
    activity = [a.sol for a in mission_activity(session)]
    earlier = [s for s in activity if s < sol]
    later = [s for s in activity if s > sol]
    return SolTimeline(
        sol=sol,
        images=[TimelineImage(i, lmst_hours(i.lmst)) for i in images],
        sequences=group_sequences((frame_meta(i) for i in images), min_frames=TIMELINE_MIN_FRAMES),
        drives=[TimelineDrive(s, placed(s.sclk_start), placed(s.sclk_end)) for s in segments],
        end_of_sol_waypoint=waypoint,
        calibration=calibration,
        previous_sol=earlier[-1] if earlier else None,
        next_sol=later[0] if later else None,
    )


# ---- featured sequences --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FeaturedSequence:
    """A published sequence worth replaying that the user can download through an ingest job.

    Frame counts and metadata verified live on 2026-11-17."""

    key: str
    title: str
    description: str
    sol: int
    instrument: str
    sequence_id: str
    published_frames: int
    job_limit: int


FEATURED: tuple[FeaturedSequence, ...] = (
    FeaturedSequence(
        key="landing-lcam",
        title="Landing day: Lander Vision System camera",
        description=(
            "87 frames from LCAM, the downward-looking camera used for terrain-relative "
            "navigation, over about three minutes of the final descent onto Jezero crater "
            "(sol 0). Mostly ~3.4 s apart, with a faster ~1.1 s burst mid-sequence."
        ),
        sol=0,
        instrument="LCAM",
        sequence_id="LVS",
        published_frames=87,
        job_limit=100,
    ),
    FeaturedSequence(
        key="sol2024-navcam-horizon",
        title="Sol 2024: Navcam horizon watch",
        description=(
            "21 Navcam subframes (1280×256, a strip along the horizon at azimuth 95°, "
            "elevation 0.7°) taken every ~4 s with constant pointing: a real time series from "
            "one viewpoint. The job downloads all 29 left Navcam frames of the sol (two "
            "command sequences)."
        ),
        sol=2024,
        instrument="NAVCAM_LEFT",
        sequence_id="NCAM00520",
        published_frames=21,
        job_limit=50,
    ),
)


def featured_local_frames(session: Session, featured: FeaturedSequence) -> int:
    return int(
        session.exec(
            select(func.count()).where(
                ImageRecord.sol == featured.sol,
                ImageRecord.instrument == featured.instrument,
                ImageRecord.sequence_id == featured.sequence_id,
            )
        ).one()
    )
