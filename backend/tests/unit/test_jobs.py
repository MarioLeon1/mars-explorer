from __future__ import annotations

import threading

import httpx
import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from mars_explorer.core.config import Settings
from mars_explorer.db.models import IngestRun
from mars_explorer.ingest.jobs import JobManager, JobRequest, TooManyJobsError
from tests.conftest import FakeNasa


def test_queue_limit_and_shutdown_cancellation(
    engine: Engine, settings: Settings, fake_nasa: FakeNasa
) -> None:
    release = threading.Event()
    started = threading.Event()

    def slow_nasa(request: httpx.Request) -> httpx.Response:
        if "/mars2020-raw-images/" in request.url.path:
            started.set()
            release.wait(timeout=10)  # hold the first job mid-download
        return fake_nasa(request)

    manager = JobManager(engine, settings, transport=httpx.MockTransport(slow_nasa))
    request = JobRequest(sol_min=2024, sol_max=2024, cameras=("MCZ_LEFT",), limit=3)
    first = manager.submit(request)
    assert started.wait(timeout=10)
    assert manager.get(first.id).status == "running"  # type: ignore[union-attr]
    second = manager.submit(request)
    manager.submit(request)
    with pytest.raises(TooManyJobsError):
        manager.submit(request)

    manager.shutdown()
    assert manager.get(second.id).status == "cancelled"  # type: ignore[union-attr]
    release.set()
    finished = manager.wait(first.id, timeout=10)
    assert finished is not None
    assert finished.status == "cancelled"  # stopped after the image in progress
    assert finished.run_id is not None  # the durable run record was still closed


def test_crashing_job_is_reported_not_fatal(engine: Engine, settings: Settings) -> None:
    def broken(_: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    manager = JobManager(engine, settings, transport=httpx.MockTransport(broken))
    job = manager.submit(JobRequest(sol_min=1, sol_max=1, cameras=(), limit=1))
    done = manager.wait(job.id, timeout=10)
    assert done is not None and done.status == "failed"
    assert done.error and "boom" in done.error
    # the worker survives and runs the next job
    again = manager.submit(JobRequest(sol_min=1, sol_max=1, cameras=(), limit=1))
    assert manager.wait(again.id, timeout=10).status == "failed"  # type: ignore[union-attr]
    manager.shutdown()
    # and no durable run record is left stuck in "running"
    with Session(engine) as session:
        runs = session.exec(select(IngestRun)).all()
    assert len(runs) == 2
    assert {run.status for run in runs} == {"failed"}
    assert all(run.error and "boom" in run.error for run in runs)
