"""Health, mission facts, camera catalog and sol index."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from sqlalchemy import func
from sqlmodel import select

from mars_explorer import __version__
from mars_explorer.api import schemas
from mars_explorer.api.deps import SessionDep
from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import ImageRecord
from mars_explorer.ingest.cameras import CATALOG, GROUP_ORDER, CameraGroup, camera_info

router = APIRouter(tags=["meta"])

MISSION = schemas.MissionInfo(
    mission="Mars 2020",
    rover="Perseverance",
    launch_date=date(2020, 7, 30),
    landing_date=date(2021, 2, 18),
    landing_site=schemas.LandingSite(
        name="Octavia E. Butler Landing", region="Jezero crater", lat=18.4447, lon=77.4508
    ),
    summary=(
        "Perseverance explores Jezero crater, an ancient lake basin with a river delta, "
        "seeking signs of past microbial life and collecting rock and regolith samples."
    ),
    provenance=Provenance.REAL_OBSERVATION,
    sources=[
        schemas.SourceRef(
            name="NASA Science — Mars 2020 Perseverance",
            url="https://science.nasa.gov/mission/mars-2020-perseverance/",
            credit="NASA/JPL-Caltech",
        )
    ],
)


@router.get("/health", response_model=schemas.Health)
def health() -> schemas.Health:
    return schemas.Health(version=__version__)


@router.get("/mission", response_model=schemas.MissionInfo)
def mission() -> schemas.MissionInfo:
    return MISSION


@router.get("/cameras", response_model=list[schemas.CameraWithCount])
def cameras(session: SessionDep) -> list[schemas.CameraWithCount]:
    rows = session.exec(
        select(ImageRecord.instrument, func.count()).group_by(ImageRecord.instrument)
    ).all()
    counts = dict(rows)
    instruments = set(CATALOG) | set(counts)  # unknown-but-ingested instruments are kept
    infos = sorted(
        (camera_info(i) for i in instruments),
        key=lambda c: (GROUP_ORDER.index(CameraGroup(c.group)), c.instrument),
    )
    return [
        schemas.CameraWithCount(
            instrument=c.instrument,
            group=c.group.value,
            label=c.label,
            image_count=counts.get(c.instrument, 0),
        )
        for c in infos
    ]


@router.get("/sols", response_model=list[schemas.SolSummary])
def sols(session: SessionDep) -> list[schemas.SolSummary]:
    rows = session.exec(
        select(
            ImageRecord.sol,
            func.count(),
            func.group_concat(func.distinct(ImageRecord.instrument)),
            func.min(ImageRecord.date_taken_utc),
            func.max(ImageRecord.date_taken_utc),
        )
        .group_by(ImageRecord.sol)
        .order_by(ImageRecord.sol.desc())  # type: ignore[attr-defined]
    ).all()
    return [
        schemas.SolSummary(
            sol=sol,
            image_count=count,
            instruments=sorted((instruments or "").split(",")) if instruments else [],
            earliest_utc=earliest,
            latest_utc=latest,
        )
        for sol, count, instruments, earliest, latest in rows
    ]
