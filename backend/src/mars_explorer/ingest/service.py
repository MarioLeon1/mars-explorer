"""Ingestion orchestration: idempotent upserts, file downloads and run bookkeeping."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

import httpx
from sqlalchemy import Engine, delete
from sqlmodel import Session

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import AppError
from mars_explorer.db.models import (
    FeedStatus,
    ImageRecord,
    IngestRun,
    TraverseSegment,
    Waypoint,
    utcnow,
)
from mars_explorer.ingest.downloader import ImageDownloader, ImageSize
from mars_explorer.ingest.http import get_with_retries
from mars_explorer.ingest.parse import ParseError, parse_raw_image
from mars_explorer.ingest.raw_feed import MAX_PAGE_SIZE, FeedQuery, RawImagesClient
from mars_explorer.ingest.traverse import parse_traverse
from mars_explorer.ingest.waypoints import parse_waypoints

log = logging.getLogger(__name__)

Progress = Callable[[str], None]


class IngestCancelled(Exception):
    """Raised by an observer to stop a run early (e.g. on server shutdown)."""


@dataclass(frozen=True, slots=True)
class ImageSelection:
    """A slice of the feed: a sol range, optional instruments and a max number of records."""

    sol_min: int
    sol_max: int
    instruments: Sequence[str] = ()
    limit: int | None = None


@dataclass(slots=True)
class RunTotals:
    items_seen: int = 0
    items_added: int = 0
    items_skipped: int = 0
    items_failed: int = 0
    files_downloaded: int = 0
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    stored_ids: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.items_failed == 0:
            return "success"
        succeeded = self.items_added + self.items_skipped + self.files_downloaded
        return "partial" if succeeded else "failed"


class IngestService:
    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        http: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        progress: Progress | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._http = http
        self._sleep = sleep
        self._feed = RawImagesClient(http, settings, sleep=sleep)
        self._downloader = ImageDownloader(http, settings, sleep=sleep)
        self._progress = progress or (lambda message: log.info(message))

    # ---- public operations -------------------------------------------------------------

    def ingest_images(
        self,
        selections: Iterable[ImageSelection],
        sizes: Sequence[ImageSize] = ("small", "large"),
        kind: str = "images",
        observer: Callable[[RunTotals], None] | None = None,
    ) -> IngestRun:
        """Ingest feed slices. ``observer`` sees the running totals after every record and may
        raise :class:`IngestCancelled` to stop; the run is then finished as partial/failed."""
        selections = list(selections)
        params = {
            "selections": [
                {
                    "sol_min": s.sol_min,
                    "sol_max": s.sol_max,
                    "instruments": list(s.instruments),
                    "limit": s.limit,
                }
                for s in selections
            ],
            "sizes": list(sizes),
        }
        totals = RunTotals()
        run = self._start_run(kind, params)
        try:
            for selection in selections:
                self._ingest_selection(selection, sizes, totals, observer)
            self._refresh_feed_status(totals)
        except AppError as exc:
            totals.items_failed += 1
            totals.errors.append(exc.message)
            log.error("ingest aborted: %s", exc.message)
        except IngestCancelled:
            totals.items_failed += 1
            totals.errors.append("cancelled before completion")
            log.warning("ingest cancelled")
        except Exception as exc:
            # Never leave a run stuck in "running": close it, then let the caller see the bug.
            totals.items_failed += 1
            totals.errors.append(f"unexpected error: {exc!r}")
            self._finish_run(run, totals)
            raise
        return self._finish_run(run, totals)

    def ingest_image_ids(
        self,
        image_ids: Sequence[str],
        sizes: Sequence[ImageSize] = ("small", "large"),
        kind: str = "image_ids",
    ) -> tuple[IngestRun, RunTotals]:
        """Fetch specific products by id. Ids NASA has not published are reported, not invented."""
        totals = RunTotals()
        run = self._start_run(kind, {"image_ids": list(image_ids), "sizes": list(sizes)})
        try:
            for image_id in image_ids:
                totals.items_seen += 1
                raw = self._feed.fetch_by_id(image_id)
                if raw is None:
                    totals.items_failed += 1
                    totals.errors.append(f"{image_id}: not published in the NASA feed")
                    continue
                self._store_record(raw, sizes, totals)
        except AppError as exc:
            totals.items_failed += 1
            totals.errors.append(exc.message)
        return self._finish_run(run, totals), totals

    def ingest_waypoints(self) -> IngestRun:
        totals = RunTotals()
        run = self._start_run("waypoints", {"url": self._settings.mmgis_waypoints_url})
        try:
            self._ingest_waypoints(totals)
        except AppError as exc:
            totals.items_failed += 1
            totals.errors.append(exc.message)
            log.error("waypoint ingest failed: %s", exc.message)
        except Exception as exc:
            totals.items_failed += 1
            totals.errors.append(f"unexpected error: {exc!r}")
            self._finish_run(run, totals)
            raise
        return self._finish_run(run, totals)

    def ingest_traverse(self) -> IngestRun:
        """Dense real drive paths (replaces the table: the source is authoritative)."""
        totals = RunTotals()
        run = self._start_run("traverse", {"url": self._settings.mmgis_traverse_url})
        try:
            self._progress("rover drive paths (JPL MMGIS)")
            response = get_with_retries(
                self._http,
                self._settings.mmgis_traverse_url,
                max_retries=self._settings.max_retries,
                sleep=self._sleep,
            )
            try:
                payload = response.json()
            except ValueError as exc:
                raise AppError("MMGIS traverse returned non-JSON content") from exc
            drives = parse_traverse(payload)
            totals.items_seen = len(payload.get("features", []))
            totals.items_skipped = totals.items_seen - len(drives)
            retrieved = utcnow()
            with Session(self._engine) as session:
                session.exec(delete(TraverseSegment))  # type: ignore[call-overload]
                for drive in drives:
                    session.add(TraverseSegment(**drive.model_dump(), retrieved_at=retrieved))
                session.commit()
            totals.items_added = len(drives)
        except AppError as exc:
            totals.items_failed += 1
            totals.errors.append(exc.message)
            log.error("traverse ingest failed: %s", exc.message)
        return self._finish_run(run, totals)

    # ---- internals ---------------------------------------------------------------------

    def _ingest_selection(
        self,
        selection: ImageSelection,
        sizes: Sequence[ImageSize],
        totals: RunTotals,
        observer: Callable[[RunTotals], None] | None = None,
    ) -> None:
        label = "/".join(selection.instruments) or "all cameras"
        span = (
            f"sol {selection.sol_min}"
            if selection.sol_min == selection.sol_max
            else f"sols {selection.sol_min}-{selection.sol_max}"
        )
        self._progress(f"{span} | {label} | up to {selection.limit or 'all'} images")
        page_size = min(selection.limit or MAX_PAGE_SIZE, MAX_PAGE_SIZE)
        query = FeedQuery(
            selection.sol_min, selection.sol_max, tuple(selection.instruments), page_size=page_size
        )
        for raw in self._feed.iter_images(query, limit=selection.limit):
            totals.items_seen += 1
            self._store_record(raw, sizes, totals)
            if observer is not None:
                observer(totals)

    def _store_record(
        self, raw: dict[str, object], sizes: Sequence[ImageSize], totals: RunTotals
    ) -> None:
        """Parse, upsert and cache one feed record, updating ``totals``."""
        try:
            parsed = parse_raw_image(raw)
        except ParseError as exc:
            totals.items_failed += 1
            totals.errors.append(str(exc))
            return
        if parsed.is_thumbnail:
            totals.items_skipped += 1
            return
        with Session(self._engine) as session:
            record = session.get(ImageRecord, parsed.image_id)
            if record is None:
                record = ImageRecord(**parsed.model_dump())
                session.add(record)
                session.commit()
                session.refresh(record)
                totals.items_added += 1
            else:
                totals.items_skipped += 1
            totals.stored_ids.append(record.image_id)
            self._downloader.write_metadata(record)
            for size in sizes:
                result = self._downloader.ensure(session, record, size)
                if result.status == "downloaded":
                    totals.files_downloaded += 1
                elif result.status == "skipped":
                    totals.files_skipped += 1
                else:
                    totals.items_failed += 1
                    totals.errors.append(f"{record.image_id}/{size}: {result.error}")

    def _ingest_waypoints(self, totals: RunTotals) -> None:
        self._progress("rover localizations (JPL MMGIS)")
        response = get_with_retries(
            self._http,
            self._settings.mmgis_waypoints_url,
            max_retries=self._settings.max_retries,
            sleep=self._sleep,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError("MMGIS waypoints returned non-JSON content") from exc
        waypoints = parse_waypoints(payload)
        totals.items_seen = len(payload.get("features", []))
        totals.items_skipped = totals.items_seen - len(waypoints)
        retrieved = utcnow()
        with Session(self._engine) as session:
            # The source is the complete authoritative list: replace it atomically.
            session.exec(delete(Waypoint))  # type: ignore[call-overload]
            for waypoint in waypoints:
                session.add(Waypoint(**waypoint.model_dump(), retrieved_at=retrieved))
            session.commit()
        totals.items_added = len(waypoints)

    def _refresh_feed_status(self, totals: RunTotals) -> None:
        try:
            latest = self._feed.latest()
        except AppError as exc:
            totals.errors.append(f"feed status check failed: {exc.message}")
            return
        with Session(self._engine) as session:
            status = session.get(FeedStatus, 1) or FeedStatus(id=1)
            status.latest_sol = latest.latest_sol
            status.total_images = latest.total_images
            status.checked_at = utcnow()
            session.add(status)
            session.commit()

    def _start_run(self, kind: str, params: dict[str, object]) -> IngestRun:
        with Session(self._engine) as session:
            run = IngestRun(kind=kind, params=params)
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def _finish_run(self, run: IngestRun, totals: RunTotals) -> IngestRun:
        with Session(self._engine) as session:
            stored = session.get(IngestRun, run.id)
            assert stored is not None
            stored.finished_at = utcnow()
            stored.status = totals.status
            stored.items_seen = totals.items_seen
            stored.items_added = totals.items_added
            stored.items_skipped = totals.items_skipped
            stored.items_failed = totals.items_failed
            stored.files_downloaded = totals.files_downloaded
            stored.files_skipped = totals.files_skipped
            stored.error = "\n".join(totals.errors[:50]) or None
            session.add(stored)
            session.commit()
            session.refresh(stored)
            return stored
