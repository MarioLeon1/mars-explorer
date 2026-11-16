"""Image listing, detail and file serving (local cache, filled on demand from NASA)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlmodel import select

from mars_explorer.api import mappers, schemas
from mars_explorer.api.deps import DownloaderDep, SessionDep
from mars_explorer.core.errors import NotFoundError, UpstreamError
from mars_explorer.db.models import ImageFile, ImageRecord

router = APIRouter(tags=["images"])


def _get_image(session: SessionDep, image_id: str) -> ImageRecord:
    image = session.get(ImageRecord, image_id)
    if image is None:
        raise NotFoundError(f"No ingested image with id {image_id!r}", code="image_not_found")
    return image


@router.get("/images", response_model=schemas.ImagePage)
def list_images(
    session: SessionDep,
    sol: int | None = None,
    sol_min: int | None = None,
    sol_max: int | None = None,
    camera: Annotated[list[str] | None, Query()] = None,
    group: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    order: Literal["desc", "asc"] = "desc",
) -> schemas.ImagePage:
    conditions = []
    if sol is not None:
        conditions.append(ImageRecord.sol == sol)
    if sol_min is not None:
        conditions.append(ImageRecord.sol >= sol_min)
    if sol_max is not None:
        conditions.append(ImageRecord.sol <= sol_max)
    if camera:
        conditions.append(ImageRecord.instrument.in_(camera))  # type: ignore[attr-defined]
    if group:
        conditions.append(ImageRecord.camera_group.in_(group))  # type: ignore[attr-defined]

    total = session.exec(select(func.count()).select_from(ImageRecord).where(*conditions)).one()
    direction = (lambda c: c.desc()) if order == "desc" else (lambda c: c.asc())
    rows = session.exec(
        select(ImageRecord)
        .where(*conditions)
        .order_by(
            direction(ImageRecord.sol),
            direction(ImageRecord.date_taken_utc),
            ImageRecord.image_id,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return schemas.ImagePage(
        items=[mappers.image_summary(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/images/{image_id}", response_model=schemas.ImageDetail)
def image_detail(
    session: SessionDep, downloader: DownloaderDep, image_id: str
) -> schemas.ImageDetail:
    image = _get_image(session, image_id)
    cached = {
        size
        for size in ("small", "large", "full_res")
        if downloader.cached(session, image_id, size) is not None
    }
    return mappers.image_detail(image, cached)


@router.get(
    "/images/{image_id}/file/{size}",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
def image_file(
    session: SessionDep,
    downloader: DownloaderDep,
    image_id: str,
    size: Annotated[schemas.ImageSize, Path()],
) -> FileResponse:
    image = _get_image(session, image_id)
    file: ImageFile | None = downloader.cached(session, image_id, size)
    if file is None:
        result = downloader.ensure(session, image, size)
        if result.file is None:
            raise UpstreamError(
                f"Could not fetch {size} rendition of {image_id} from NASA: {result.error}"
            )
        file = result.file
    return FileResponse(
        downloader.absolute(file),
        media_type=file.content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
