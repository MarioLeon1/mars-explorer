"""Upstream availability checks and background ingestion jobs (started from the UI)."""

from __future__ import annotations

import threading
import time
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import func
from sqlmodel import select

from mars_explorer.api import schemas
from mars_explorer.api.deps import SessionDep, SettingsDep
from mars_explorer.core.errors import InvalidRequestError, NotFoundError
from mars_explorer.db.models import ImageRecord, utcnow
from mars_explorer.ingest.cameras import CATALOG
from mars_explorer.ingest.jobs import Job, JobManager, JobRequest
from mars_explorer.ingest.raw_feed import FeedQuery, RawImagesClient

router = APIRouter(tags=["ingest"])

AVAILABILITY_TTL_S = 600
_cache: dict[tuple[int, int, tuple[str, ...]], tuple[float, int | None, object]] = {}
_cache_lock = threading.Lock()


def _validate_cameras(cameras: list[str]) -> tuple[str, ...]:
    unknown = sorted(set(cameras) - set(CATALOG))
    if unknown:
        raise InvalidRequestError(f"Unknown instrument(s): {', '.join(unknown)}")
    return tuple(sorted(set(cameras)))


def _job_out(job: Job) -> schemas.IngestJob:
    r = job.request
    return schemas.IngestJob(
        id=job.id,
        status=job.status,
        sol_min=r.sol_min,
        sol_max=r.sol_max,
        cameras=list(r.cameras),
        limit=r.limit,
        full_res=r.full_res,
        progress=schemas.JobProgress(
            seen=job.seen,
            added=job.added,
            skipped=job.skipped,
            failed=job.failed,
            downloaded=job.downloaded,
        ),
        run_id=job.run_id,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _jobs(request: Request) -> JobManager:
    return request.app.state.jobs


@router.get("/feed/availability", response_model=schemas.FeedAvailability)
def feed_availability(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    sol_min: Annotated[int, Query(ge=0)],
    sol_max: Annotated[int | None, Query(ge=0)] = None,
    camera: Annotated[list[str] | None, Query()] = None,
) -> schemas.FeedAvailability:
    """How many images NASA publishes for a sol range/cameras, vs. how many are stored."""
    high = sol_max if sol_max is not None else sol_min
    if high < sol_min:
        raise InvalidRequestError("sol_max must be >= sol_min")
    cameras = _validate_cameras(camera or [])
    key = (sol_min, high, cameras)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
    if cached and now - cached[0] < AVAILABILITY_TTL_S:
        published, checked_at = cached[1], cached[2]
    else:
        feed = RawImagesClient(request.app.state.http, settings)
        published = feed.count(FeedQuery(sol_min, high, cameras))
        checked_at = utcnow()
        with _cache_lock:
            _cache[key] = (now, published, checked_at)

    conditions = [ImageRecord.sol >= sol_min, ImageRecord.sol <= high]
    if cameras:
        conditions.append(ImageRecord.instrument.in_(cameras))  # type: ignore[attr-defined]
    stored = session.exec(select(func.count()).select_from(ImageRecord).where(*conditions)).one()
    return schemas.FeedAvailability.model_validate(
        {
            "sol_min": sol_min,
            "sol_max": high,
            "cameras": list(cameras),
            "published": published,
            "stored": stored,
            "checked_at": checked_at,
            "source": {
                "name": "NASA Mars 2020 raw images feed",
                "url": settings.raw_feed_url,
                "credit": "NASA/JPL-Caltech",
                "retrieved_at": checked_at,
            },
        }
    )


@router.post("/ingest/jobs", response_model=schemas.IngestJob, status_code=202)
def create_job(request: Request, body: schemas.IngestJobRequest) -> schemas.IngestJob:
    job = _jobs(request).submit(
        JobRequest(
            sol_min=body.sol_min,
            sol_max=body.sol_max if body.sol_max is not None else body.sol_min,
            cameras=_validate_cameras(body.cameras),
            limit=body.limit,
            full_res=body.full_res,
        )
    )
    return _job_out(job)


@router.get("/ingest/jobs", response_model=list[schemas.IngestJob])
def list_jobs(request: Request) -> list[schemas.IngestJob]:
    return [_job_out(job) for job in _jobs(request).list()]


@router.get("/ingest/jobs/{job_id}", response_model=schemas.IngestJob)
def get_job(request: Request, job_id: str) -> schemas.IngestJob:
    job = _jobs(request).get(job_id)
    if job is None:
        raise NotFoundError(f"No ingestion job {job_id!r}", code="job_not_found")
    return _job_out(job)
