"""Defensive parsing of raw-images feed records.

The feed encodes numbers as strings, tuples as ``"(a,b,c)"`` strings and unknown values as
``"UNK"``. Every helper here returns ``None`` instead of guessing when a value is unusable.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from mars_explorer.ingest.cameras import camera_info

_UNKNOWN = {"", "UNK", "UNKNOWN", "NONE", "NULL", "N/A"}
_LMST_RE = re.compile(r"M(\d{2}:\d{2}:\d{2})")


class ParseError(ValueError):
    pass


def clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().upper() in _UNKNOWN:
        return None
    return value


def to_float(value: Any) -> float | None:
    value = clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    number = to_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def to_tuple(value: Any) -> list[float] | None:
    """Parse ``"(1.0,-2,3e-6)"`` into floats. Returns None if any component is invalid."""
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, list | tuple):
        parts: list[Any] = list(value)
    else:
        parts = str(value).strip().strip("()").split(",")
    numbers = [to_float(p) for p in parts]
    if not numbers or any(n is None for n in numbers):
        return None
    return [n for n in numbers if n is not None]


def to_utc(value: Any) -> datetime | None:
    """Parse ISO datetimes. The feed omits the zone on ``date_taken_utc``; it is UTC."""
    value = clean(value)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_lmst(date_taken_mars: str | None) -> str | None:
    """``"Sol-02024M12:35:01.653"`` -> ``"12:35:01"`` (Local Mean Solar Time)."""
    if not date_taken_mars:
        return None
    match = _LMST_RE.search(date_taken_mars)
    return match.group(1) if match else None


def parse_sequence_id(image_id: str) -> str | None:
    """Best-effort command sequence id from the product id.

    The 5th underscore-separated segment is ``<N|T><site:3><drive:4><sequence>``, e.g.
    ``N0930000NCAM00518`` -> ``NCAM00518``. Returns None if the segment is not in that shape.
    """
    parts = image_id.split("_")
    if len(parts) < 5:
        return None
    segment = parts[4]
    if len(segment) <= 8 or not segment[1:8].isdigit():
        return None
    return segment[8:]


class NormalizedImage(BaseModel):
    image_id: str
    sol: int
    instrument: str
    camera_group: str
    sample_type: str
    date_taken_utc: datetime | None
    date_taken_mars: str | None
    lmst: str | None
    site: int | None
    drive: int | None
    width: int | None
    height: int | None
    title: str | None
    caption: str | None
    credit: str | None
    date_received: datetime | None
    filter_name: str | None
    sequence_id: str | None
    mast_az: float | None
    mast_el: float | None
    sclk: float | None
    scale_factor: float | None
    subframe_rect: list[int] | None
    attitude_quaternion: list[float] | None
    camera_model_type: str | None
    camera_position: list[float] | None
    camera_vector: list[float] | None
    url_small: str | None
    url_medium: str | None
    url_large: str | None
    url_full_res: str | None
    nasa_page_url: str | None
    nasa_json_url: str | None
    raw_json: str

    @property
    def is_thumbnail(self) -> bool:
        return self.sample_type.lower() == "thumbnail"


def parse_raw_image(raw: dict[str, Any]) -> NormalizedImage:
    """Normalise one feed record. Raises :class:`ParseError` if identity fields are missing."""
    image_id = clean(raw.get("imageid"))
    sol = to_int(raw.get("sol"))
    camera = raw.get("camera") or {}
    instrument = clean(camera.get("instrument"))
    if not image_id or sol is None or not instrument:
        raise ParseError(f"record missing imageid/sol/instrument: {str(raw)[:200]}")

    extended = raw.get("extended") or {}
    files = raw.get("image_files") or {}
    dimension = to_tuple(extended.get("dimension"))
    subframe = to_tuple(extended.get("subframeRect"))
    date_taken_mars = clean(raw.get("date_taken_mars"))

    return NormalizedImage(
        image_id=image_id,
        sol=sol,
        instrument=instrument,
        camera_group=camera_info(instrument).group.value,
        sample_type=clean(raw.get("sample_type")) or "Unknown",
        date_taken_utc=to_utc(raw.get("date_taken_utc")),
        date_taken_mars=date_taken_mars,
        lmst=parse_lmst(date_taken_mars),
        site=to_int(raw.get("site")),
        drive=to_int(raw.get("drive")),
        width=int(dimension[0]) if dimension and len(dimension) == 2 else None,
        height=int(dimension[1]) if dimension and len(dimension) == 2 else None,
        title=clean(raw.get("title")),
        caption=clean(raw.get("caption")),
        credit=clean(raw.get("credit")),
        date_received=to_utc(raw.get("date_received")),
        filter_name=clean(camera.get("filter_name")),
        sequence_id=parse_sequence_id(image_id),
        mast_az=to_float(extended.get("mastAz")),
        mast_el=to_float(extended.get("mastEl")),
        sclk=to_float(extended.get("sclk")),
        scale_factor=to_float(extended.get("scaleFactor")),
        subframe_rect=[int(v) for v in subframe] if subframe and len(subframe) == 4 else None,
        attitude_quaternion=to_tuple(raw.get("attitude")),
        camera_model_type=clean(camera.get("camera_model_type")),
        camera_position=to_tuple(camera.get("camera_position")),
        camera_vector=to_tuple(camera.get("camera_vector")),
        url_small=clean(files.get("small")),
        url_medium=clean(files.get("medium")),
        url_large=clean(files.get("large")),
        url_full_res=clean(files.get("full_res")),
        nasa_page_url=clean(raw.get("link")),
        nasa_json_url=clean(raw.get("json_link")),
        raw_json=json.dumps(raw, ensure_ascii=False, sort_keys=True),
    )
