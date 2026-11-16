"""System status: local data inventory and last known upstream feed state."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func
from sqlmodel import select

from mars_explorer.api import schemas
from mars_explorer.api.deps import SessionDep
from mars_explorer.db.models import FeedStatus, ImageFile, ImageRecord, IngestRun, Waypoint

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=schemas.SystemStatus)
def status(session: SessionDep) -> schemas.SystemStatus:
    images = session.exec(select(func.count()).select_from(ImageRecord)).one()
    sols = session.exec(select(func.count(func.distinct(ImageRecord.sol)))).one()
    waypoints = session.exec(select(func.count()).select_from(Waypoint)).one()
    files = session.exec(select(func.count()).select_from(ImageFile)).one()
    size = session.exec(select(func.coalesce(func.sum(ImageFile.bytes), 0))).one()
    last = session.exec(
        select(IngestRun)
        .where(IngestRun.finished_at.is_not(None))  # type: ignore[union-attr]
        .order_by(IngestRun.id.desc())  # type: ignore[union-attr]
    ).first()
    feed = session.get(FeedStatus, 1)
    return schemas.SystemStatus(
        database=schemas.DatabaseCounts(images=images, sols=sols, waypoints=waypoints),
        storage=schemas.StorageStats(image_files=files, bytes=size),
        last_ingest=schemas.LastIngest(
            kind=last.kind,
            status=last.status,
            finished_at=last.finished_at,
            items_added=last.items_added,
            items_skipped=last.items_skipped,
            items_failed=last.items_failed,
        )
        if last
        else None,
        feed=schemas.FeedState(
            latest_sol=feed.latest_sol, total_images=feed.total_images, checked_at=feed.checked_at
        )
        if feed
        else None,
    )
