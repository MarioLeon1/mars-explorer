"""Background ingestion jobs started from the UI.

One worker thread runs jobs in order (NASA politeness + SQLite single-writer). Job state is
in memory — it is a progress view; the durable record of every run is the ``ingest_runs``
table. Jobs still queued when the server stops are cancelled; a running job stops after the
current image.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

import httpx
from sqlalchemy import Engine

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import AppError, InvalidRequestError
from mars_explorer.db.models import utcnow
from mars_explorer.ingest.downloader import ImageSize
from mars_explorer.ingest.http import make_http_client
from mars_explorer.ingest.service import (
    ImageSelection,
    IngestCancelled,
    IngestService,
    RunTotals,
)

log = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "success", "partial", "failed", "cancelled"]
ACTIVE: frozenset[str] = frozenset({"queued", "running"})

MAX_ACTIVE_JOBS = 3
MAX_SOL_SPAN = 30
MAX_LIMIT = 200
_HISTORY = 20


class TooManyJobsError(AppError):
    status_code = 429
    code = "too_many_jobs"


@dataclass(frozen=True, slots=True)
class JobRequest:
    sol_min: int
    sol_max: int
    cameras: tuple[str, ...]
    limit: int
    full_res: bool = False

    def validate(self) -> None:
        if self.sol_min < 0 or self.sol_max < self.sol_min:
            raise InvalidRequestError("sol_max must be >= sol_min >= 0")
        if self.sol_max - self.sol_min > MAX_SOL_SPAN:
            raise InvalidRequestError(
                f"At most {MAX_SOL_SPAN + 1} sols per job; split larger ranges."
            )
        if not 1 <= self.limit <= MAX_LIMIT:
            raise InvalidRequestError(f"limit must be between 1 and {MAX_LIMIT}")


@dataclass(slots=True)
class Job:
    id: str
    request: JobRequest
    status: JobStatus = "queued"
    seen: int = 0
    added: int = 0
    skipped: int = 0
    failed: int = 0
    downloaded: int = 0
    run_id: int | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def snapshot(self) -> Job:
        return replace(self)


class JobManager:
    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._transport = transport
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest-job")
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._futures: dict[str, Future[None]] = {}
        self._lock = threading.Lock()
        self._stopping = threading.Event()

    def submit(self, request: JobRequest) -> Job:
        request.validate()
        with self._lock:
            active = sum(1 for job in self._jobs.values() if job.status in ACTIVE)
            if active >= MAX_ACTIVE_JOBS:
                raise TooManyJobsError(
                    f"{active} ingestion jobs are already queued or running; wait for one to end."
                )
            job = Job(id=uuid.uuid4().hex[:12], request=request)
            self._jobs[job.id] = job
            self._trim_history()
            self._futures[job.id] = self._executor.submit(self._run, job.id)
            return job.snapshot()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def list(self) -> list[Job]:
        with self._lock:
            return [job.snapshot() for job in reversed(self._jobs.values())]

    def wait(self, job_id: str, timeout: float | None = None) -> Job | None:
        """Block until a job finishes (used by tests and scripts)."""
        future = self._futures.get(job_id)
        if future is not None:
            future.result(timeout=timeout)
        return self.get(job_id)

    def shutdown(self) -> None:
        self._stopping.set()
        with self._lock:
            for job in self._jobs.values():
                if job.status == "queued":
                    job.status = "cancelled"
                    job.finished_at = utcnow()
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ---- worker --------------------------------------------------------------------------

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.status != "queued":
                return
            job.status = "running"
            job.started_at = utcnow()
            request = job.request

        def observe(totals: RunTotals) -> None:
            self._update(
                job_id,
                seen=totals.items_seen,
                added=totals.items_added,
                skipped=totals.items_skipped,
                failed=totals.items_failed,
                downloaded=totals.files_downloaded,
            )
            if self._stopping.is_set():
                raise IngestCancelled

        sizes: tuple[ImageSize, ...] = (
            ("small", "large", "full_res") if request.full_res else ("small", "large")
        )
        try:
            with make_http_client(self._settings, transport=self._transport) as http:
                service = IngestService(self._engine, self._settings, http)
                run = service.ingest_images(
                    [
                        ImageSelection(
                            request.sol_min, request.sol_max, request.cameras, request.limit
                        )
                    ],
                    sizes=sizes,
                    kind="ui_job",
                    observer=observe,
                )
            status: JobStatus = "cancelled" if self._stopping.is_set() else run.status  # type: ignore[assignment]
            self._update(
                job_id,
                status=status,
                run_id=run.id,
                seen=run.items_seen,
                added=run.items_added,
                skipped=run.items_skipped,
                failed=run.items_failed,
                downloaded=run.files_downloaded,
                error=run.error,
                finished_at=utcnow(),
            )
        except Exception as exc:  # a job must never kill the worker thread
            log.exception("ingest job %s crashed", job_id)
            self._update(job_id, status="failed", error=str(exc), finished_at=utcnow())

    def _trim_history(self) -> None:
        while len(self._jobs) > _HISTORY:
            oldest_id, oldest = next(iter(self._jobs.items()))
            if oldest.status in ACTIVE:
                break
            self._jobs.pop(oldest_id)
            self._futures.pop(oldest_id, None)
