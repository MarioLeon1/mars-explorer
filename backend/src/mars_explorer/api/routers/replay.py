"""Mission Replay: reconstructed frame sequences, sol timelines and official NASA videos."""

from __future__ import annotations

from fastapi import APIRouter, Query

from mars_explorer.api import schemas
from mars_explorer.api.deps import SessionDep, SettingsDep
from mars_explorer.api.mappers import camera
from mars_explorer.core.errors import NotFoundError
from mars_explorer.core.provenance import Provenance
from mars_explorer.replay.sequences import KIND_NOTES, FrameSequence, sequence_key
from mars_explorer.replay.service import (
    FEATURED,
    featured_local_frames,
    get_sequence,
    list_sequences,
    mission_activity,
    sol_timeline,
)
from mars_explorer.replay.videos import OFFICIAL_VIDEOS

router = APIRouter(prefix="/replay", tags=["replay"])

RECONSTRUCTED_NOTE = (
    "Reconstructed from individual raw images in spacecraft-clock order. This is not a NASA "
    "video: frames are uncalibrated browse products and gaps between them are real."
)


def _file_url(image_id: str, size: str) -> str:
    return f"/api/images/{image_id}/file/{size}"


def _summary(sequence: FrameSequence) -> schemas.SequenceSummary:
    first = sequence.frames[0].meta
    return schemas.SequenceSummary(
        id=sequence.id,
        sol=sequence.sol,
        camera=camera(sequence.instrument),
        sequence_id=sequence.sequence_id,
        kind=sequence.kind,
        kind_note=KIND_NOTES[sequence.kind],
        frame_count=sequence.frame_count,
        duration_s=sequence.duration_s,
        median_interval_s=sequence.median_interval_s,
        distinct_pointings=sequence.distinct_pointings,
        start_lmst=first.lmst,
        thumb_url=_file_url(first.image_id, "small"),
        provenance=Provenance.DERIVED,
    )


@router.get("/mission", response_model=schemas.MissionTimeline)
def mission(session: SessionDep, settings: SettingsDep) -> schemas.MissionTimeline:
    activity = mission_activity(session)
    return schemas.MissionTimeline(
        sols=[
            schemas.SolActivityOut(
                sol=a.sol,
                images=a.images,
                sequences=a.sequences,
                drives=a.drives,
                drive_m=a.drive_m,
            )
            for a in activity
        ],
        total_drive_m=round(sum(a.drive_m for a in activity), 1),
        drive_sols=sum(1 for a in activity if a.drives),
        image_sols=sum(1 for a in activity if a.images),
        provenance=Provenance.REAL_OBSERVATION,
        sources=[
            schemas.SourceRef(
                name="JPL MMGIS — Perseverance traverse (M20_traverse.json)",
                url=settings.mmgis_traverse_url,
                credit="NASA/JPL-Caltech",
            ),
            schemas.SourceRef(
                name="NASA Mars 2020 raw images feed (images stored locally)",
                url="https://mars.nasa.gov/mars2020/multimedia/raw-images/",
                credit="NASA/JPL-Caltech",
            ),
        ],
        notes=[
            "Drive distances are the lengths of the real drive paths published by JPL.",
            "Image counts are what is stored in this app, not everything NASA has published.",
        ],
    )


@router.get("/sols/{sol}", response_model=schemas.SolTimelineOut)
def sol_detail(session: SessionDep, sol: int) -> schemas.SolTimelineOut:
    timeline = sol_timeline(session, sol)
    if timeline is None:
        raise NotFoundError(f"No stored images or real drives for sol {sol}.")
    waypoint = timeline.end_of_sol_waypoint
    calibration = timeline.calibration
    notes = [
        "Image times are each image's Local Mean Solar Time (LMST) as published by NASA.",
    ]
    if timeline.drives:
        notes.append(
            "Drive times come from the drive's spacecraft clock, placed on LMST with a linear "
            "mapping calibrated on this sol's images (derived)."
            if calibration
            else "Drive times cannot be placed: no image of this sol has both LMST and SCLK."
        )
    return schemas.SolTimelineOut(
        sol=timeline.sol,
        images=[
            schemas.TimelineImageOut(
                image_id=t.image.image_id,
                camera=camera(t.image.instrument),
                lmst=t.image.lmst,
                lmst_h=t.lmst_h,
                sclk=t.image.sclk,
                sequence_id=t.image.sequence_id,
                thumb_url=_file_url(t.image.image_id, "small"),
            )
            for t in timeline.images
        ],
        sequences=[_summary(s) for s in timeline.sequences],
        drives=[
            schemas.TimelineDriveOut(
                index=d.segment.source_index,
                from_rmc=d.segment.from_rmc,
                to_rmc=d.segment.to_rmc,
                length_m=d.segment.length_m,
                start_lmst_h=d.start_lmst_h,
                end_lmst_h=d.end_lmst_h,
                provenance=Provenance.REAL_OBSERVATION,
            )
            for d in timeline.drives
        ],
        end_of_sol_position=(
            schemas.WaypointPoint(
                sol=waypoint.sol,
                site=waypoint.site,
                drive=waypoint.drive,
                lat=waypoint.lat,
                lon=waypoint.lon,
                elevation_m=waypoint.elevation_m,
                odometry_total_m=waypoint.odometry_total_m,
            )
            if waypoint
            else None
        ),
        lmst_calibration=(
            schemas.LmstCalibrationOut(
                samples=calibration.samples,
                max_residual_s=round(calibration.max_residual_s, 2),
                method=(
                    "lmst_h = sclk / 3698.97 s + offset (one Mars solar day = 88 775.244 s); "
                    f"offset = median over {calibration.samples} images of this sol"
                ),
            )
            if calibration
            else None
        ),
        previous_sol=timeline.previous_sol,
        next_sol=timeline.next_sol,
        notes=notes,
    )


@router.get("/sequences", response_model=list[schemas.SequenceSummary])
def sequences(
    session: SessionDep,
    sol: int | None = Query(default=None, ge=0),
    min_frames: int = Query(default=3, ge=2, le=100),
) -> list[schemas.SequenceSummary]:
    return [_summary(s) for s in list_sequences(session, sol, min_frames)]


@router.get("/sequences/{sequence_id}", response_model=schemas.SequenceDetail)
def sequence_detail(session: SessionDep, sequence_id: str) -> schemas.SequenceDetail:
    found = get_sequence(session, sequence_id)
    if found is None:
        raise NotFoundError(f"Sequence {sequence_id!r} not found in the local archive.")
    sequence, records = found
    credits = sorted({r.credit for r in records.values() if r.credit})
    return schemas.SequenceDetail(
        **_summary(sequence).model_dump(),
        frames=[
            schemas.SequenceFrame(
                image_id=f.meta.image_id,
                t_offset_s=f.t_offset_s,
                sclk=f.meta.sclk,
                lmst=f.meta.lmst,
                width=f.meta.width,
                height=f.meta.height,
                thumb_url=_file_url(f.meta.image_id, "small"),
                preview_url=_file_url(f.meta.image_id, "large"),
                provenance=Provenance.REAL_OBSERVATION,
            )
            for f in sequence.frames
        ],
        notes=[RECONSTRUCTED_NOTE, *sequence.notes],
        credits=credits,
        real_time_available=all(f.t_offset_s is not None for f in sequence.frames)
        and (sequence.duration_s or 0) > 0,
    )


@router.get("/featured", response_model=list[schemas.FeaturedSequenceOut])
def featured(session: SessionDep) -> list[schemas.FeaturedSequenceOut]:
    out = []
    for item in FEATURED:
        local = featured_local_frames(session, item)
        out.append(
            schemas.FeaturedSequenceOut(
                key=item.key,
                title=item.title,
                description=item.description,
                sol=item.sol,
                camera=camera(item.instrument),
                sequence_id=item.sequence_id,
                published_frames=item.published_frames,
                local_frames=local,
                sequence_url=(
                    f"/api/replay/sequences/"
                    f"{sequence_key(item.sol, item.instrument, item.sequence_id)}"
                    if local >= 2
                    else None
                ),
                job_request=schemas.IngestJobRequest(
                    sol_min=item.sol,
                    sol_max=item.sol,
                    cameras=[item.instrument],
                    limit=item.job_limit,
                ),
                provenance=Provenance.REAL_OBSERVATION,
            )
        )
    return out


@router.get("/videos", response_model=list[schemas.OfficialVideoOut])
def videos() -> list[schemas.OfficialVideoOut]:
    return [
        schemas.OfficialVideoOut(
            nasa_id=v.nasa_id,
            title=v.title,
            date=v.date,
            sol=v.sol,
            description=v.description,
            credit=v.credit,
            video_url=v.video_url,
            poster_url=v.poster_url,
            page_url=v.page_url,
            provenance=Provenance.REAL_OBSERVATION,
        )
        for v in OFFICIAL_VIDEOS
    ]
