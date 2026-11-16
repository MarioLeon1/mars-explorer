"""Image listing, navigation, relations, raw records and file serving."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlmodel import select

from mars_explorer.api import mappers, schemas
from mars_explorer.api.deps import DownloaderDep, SessionDep, SettingsDep
from mars_explorer.api.filters import CHRONOLOGICAL, FilterDep
from mars_explorer.core.errors import AppError, NotFoundError, UpstreamError
from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import ImageFile, ImageRecord
from mars_explorer.ingest.cameras import STEREO_PARTNER, stereo_candidate_id
from mars_explorer.ingest.service import IngestService

router = APIRouter(tags=["images"])

RELATED_LIMIT = 30
OTHER_CAMERAS_LIMIT = 8


def _get_image(session: SessionDep, image_id: str) -> ImageRecord:
    image = session.get(ImageRecord, image_id)
    if image is None:
        raise NotFoundError(f"No ingested image with id {image_id!r}", code="image_not_found")
    return image


@router.get("/images", response_model=schemas.ImagePage)
def list_images(
    session: SessionDep,
    filters: FilterDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    order: Literal["desc", "asc"] = "desc",
) -> schemas.ImagePage:
    conditions = filters.conditions()
    total = session.exec(select(func.count()).select_from(ImageRecord).where(*conditions)).one()
    key = [c.desc() if order == "desc" else c.asc() for c in CHRONOLOGICAL[:2]]
    rows = session.exec(
        select(ImageRecord)
        .where(*conditions)
        .order_by(*key, ImageRecord.image_id)
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


@router.get("/images/{image_id}/neighbors", response_model=schemas.Neighbors)
def image_neighbors(session: SessionDep, filters: FilterDep, image_id: str) -> schemas.Neighbors:
    """Previous/next image in chronological order (sol, time, id) within the same filters."""
    _get_image(session, image_id)
    ids = list(
        session.exec(
            select(ImageRecord.image_id).where(*filters.conditions()).order_by(*CHRONOLOGICAL)
        ).all()
    )
    if image_id not in ids:
        return schemas.Neighbors(previous=None, next=None, position=None, total=len(ids))
    index = ids.index(image_id)
    previous = session.get(ImageRecord, ids[index - 1]) if index > 0 else None
    following = session.get(ImageRecord, ids[index + 1]) if index + 1 < len(ids) else None
    return schemas.Neighbors(
        previous=mappers.image_summary(previous) if previous else None,
        next=mappers.image_summary(following) if following else None,
        position=index + 1,
        total=len(ids),
    )


@router.get("/images/{image_id}/related", response_model=schemas.RelatedImages)
def related_images(session: SessionDep, image_id: str) -> schemas.RelatedImages:
    image = _get_image(session, image_id)
    candidate = stereo_candidate_id(image.image_id, image.instrument)
    # The stereo partner is reported once, in `stereo`, never repeated in the other lists.
    excluded = {image.image_id, candidate} - {None}

    same_sequence: list[ImageRecord] = []
    if image.sequence_id:
        same_sequence = list(
            session.exec(
                select(ImageRecord)
                .where(
                    ImageRecord.sol == image.sol,
                    ImageRecord.sequence_id == image.sequence_id,
                    ImageRecord.image_id.not_in(excluded),  # type: ignore[attr-defined]
                )
                .order_by(*CHRONOLOGICAL)
                .limit(RELATED_LIMIT)
            ).all()
        )

    stereo: schemas.StereoInfo | None = None
    if candidate is not None:
        local = session.get(ImageRecord, candidate)
        stereo = schemas.StereoInfo(
            partner_instrument=STEREO_PARTNER[image.instrument],
            candidate_id=candidate,
            local=mappers.image_summary(local) if local else None,
        )

    others = session.exec(
        select(ImageRecord).where(
            ImageRecord.sol == image.sol,
            ImageRecord.instrument != image.instrument,
            ImageRecord.image_id.not_in(excluded),  # type: ignore[attr-defined]
        )
    ).all()
    if image.date_taken_utc is not None:
        taken = image.date_taken_utc
        others = sorted(
            (o for o in others if o.date_taken_utc is not None),
            key=lambda o: abs((o.date_taken_utc - taken).total_seconds()),  # type: ignore[operator]
        )
    return schemas.RelatedImages(
        same_sequence=[mappers.image_summary(r) for r in same_sequence],
        stereo=stereo,
        same_sol_other_cameras=[mappers.image_summary(r) for r in others[:OTHER_CAMERAS_LIMIT]],
    )


@router.get("/images/{image_id}/raw", response_model=schemas.RawRecord)
def raw_record(session: SessionDep, image_id: str) -> schemas.RawRecord:
    """The original NASA feed record, exactly as received."""
    image = _get_image(session, image_id)
    return schemas.RawRecord(
        image_id=image.image_id,
        provenance=Provenance(image.provenance),
        source_url=image.nasa_json_url,
        record=json.loads(image.raw_json),
    )


@router.post("/images/{image_id}/stereo-partner", response_model=schemas.ImageSummary)
def fetch_stereo_partner(
    request: Request, session: SessionDep, settings: SettingsDep, image_id: str
) -> schemas.ImageSummary:
    """Ingest the other eye of a stereo pair, only if NASA actually published it."""
    image = _get_image(session, image_id)
    candidate = stereo_candidate_id(image.image_id, image.instrument)
    if candidate is None:
        raise AppError(
            f"{image.instrument} is not a stereo camera", code="not_stereo", status_code=422
        )
    existing = session.get(ImageRecord, candidate)
    if existing is not None:
        return mappers.image_summary(existing)

    service = IngestService(request.app.state.engine, settings, request.app.state.http)
    _, totals = service.ingest_image_ids([candidate], kind="stereo_partner")
    if candidate not in totals.stored_ids:
        if any("not published" in error for error in totals.errors):
            raise NotFoundError(
                f"NASA has not published a matching {STEREO_PARTNER[image.instrument]} frame "
                f"({candidate}).",
                code="stereo_partner_not_found",
            )
        raise UpstreamError("; ".join(totals.errors) or "stereo partner download failed")
    session.expire_all()
    return mappers.image_summary(_get_image(session, candidate))


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
