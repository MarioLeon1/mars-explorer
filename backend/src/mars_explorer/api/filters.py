"""Image filters shared by listing and chronological navigation (one definition, one behaviour)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import Depends, Query

from mars_explorer.db.models import ImageRecord


@dataclass(frozen=True, slots=True)
class ImageFilter:
    sol: int | None = None
    sol_min: int | None = None
    sol_max: int | None = None
    cameras: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None

    def conditions(self) -> list[Any]:
        column = ImageRecord
        conditions: list[Any] = []
        if self.sol is not None:
            conditions.append(column.sol == self.sol)
        if self.sol_min is not None:
            conditions.append(column.sol >= self.sol_min)
        if self.sol_max is not None:
            conditions.append(column.sol <= self.sol_max)
        if self.cameras:
            conditions.append(column.instrument.in_(self.cameras))  # type: ignore[attr-defined]
        if self.groups:
            conditions.append(column.camera_group.in_(self.groups))  # type: ignore[attr-defined]
        if self.date_from is not None:
            start = datetime.combine(self.date_from, time.min, tzinfo=UTC)
            conditions.append(column.date_taken_utc >= start)  # type: ignore[operator]
        if self.date_to is not None:  # inclusive: the whole UTC day
            end = datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=UTC)
            conditions.append(column.date_taken_utc < end)  # type: ignore[operator]
        if self.q:
            escaped = self.q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            conditions.append(
                column.image_id.ilike(f"%{escaped}%", escape="\\")  # type: ignore[attr-defined]
            )
        return conditions


def image_filter(
    sol: int | None = None,
    sol_min: int | None = None,
    sol_max: int | None = None,
    camera: Annotated[list[str] | None, Query(description="Instrument id, repeatable")] = None,
    group: Annotated[list[str] | None, Query(description="Camera group, repeatable")] = None,
    date_from: Annotated[date | None, Query(description="UTC date taken, inclusive")] = None,
    date_to: Annotated[date | None, Query(description="UTC date taken, inclusive")] = None,
    q: Annotated[str | None, Query(max_length=80, description="Substring of the image id")] = None,
) -> ImageFilter:
    return ImageFilter(
        sol=sol,
        sol_min=sol_min,
        sol_max=sol_max,
        cameras=tuple(camera or ()),
        groups=tuple(group or ()),
        date_from=date_from,
        date_to=date_to,
        q=q.strip() if q and q.strip() else None,
    )


FilterDep = Annotated[ImageFilter, Depends(image_filter)]

CHRONOLOGICAL = (ImageRecord.sol, ImageRecord.date_taken_utc, ImageRecord.image_id)
"""Ordering key used everywhere: sol, then capture time, then id (stable tie-break)."""
