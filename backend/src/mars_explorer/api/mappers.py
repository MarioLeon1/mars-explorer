"""Conversions from database rows to API schemas."""

from __future__ import annotations

from mars_explorer.api import schemas
from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import ImageRecord
from mars_explorer.ingest.cameras import camera_info

RAW_PRODUCT_NOTE = (
    "Uncalibrated browse product (raw JPEG/PNG). Not suitable for radiometric or "
    "photogrammetric measurement."
)
FEED_SOURCE_NAME = "NASA Mars 2020 raw images feed"


def camera(instrument: str) -> schemas.Camera:
    info = camera_info(instrument)
    return schemas.Camera(instrument=info.instrument, group=info.group.value, label=info.label)


def _summary_fields(image: ImageRecord) -> dict[str, object]:
    base = f"/api/images/{image.image_id}/file"
    return {
        "image_id": image.image_id,
        "sol": image.sol,
        "camera": camera(image.instrument),
        "sample_type": image.sample_type,
        "date_taken_utc": image.date_taken_utc,
        "date_taken_mars": image.date_taken_mars,
        "lmst": image.lmst,
        "site": image.site,
        "drive": image.drive,
        "width": image.width,
        "height": image.height,
        "thumb_url": f"{base}/small",
        "preview_url": f"{base}/large",
        "credit": image.credit,
        "provenance": Provenance(image.provenance),
    }


def image_summary(image: ImageRecord) -> schemas.ImageSummary:
    return schemas.ImageSummary.model_validate(_summary_fields(image))


def image_detail(image: ImageRecord, cached_sizes: set[str]) -> schemas.ImageDetail:
    notes = [RAW_PRODUCT_NOTE]
    if image.scale_factor and image.scale_factor > 1:
        notes.append(
            f"Downsampled on board by a factor of {image.scale_factor:g} before transmission."
        )
    return schemas.ImageDetail.model_validate(
        {
            **_summary_fields(image),
            "title": image.title,
            "caption": image.caption,
            "date_received": image.date_received,
            "filter_name": image.filter_name,
            "sequence_id": image.sequence_id,
            "mast_az": image.mast_az,
            "mast_el": image.mast_el,
            "sclk": image.sclk,
            "scale_factor": image.scale_factor,
            "subframe_rect": image.subframe_rect,
            "attitude_quaternion": image.attitude_quaternion,
            "camera_model_type": image.camera_model_type,
            "camera_position": image.camera_position,
            "camera_vector": image.camera_vector,
            "source": {
                "nasa_page_url": image.nasa_page_url,
                "nasa_json_url": image.nasa_json_url,
                "original_files": {
                    "small": image.url_small,
                    "medium": image.url_medium,
                    "large": image.url_large,
                    "full_res": image.url_full_res,
                },
            },
            "local_files": {size: size in cached_sizes for size in ("small", "large", "full_res")},
            "ingested_at": image.ingested_at,
            "notes": notes,
        }
    )
