"""Shared test fixtures. Everything here is offline: NASA is replaced by ``FakeNasa``.

The JSON fixtures in ``tests/fixtures/`` are real responses captured from the NASA endpoints
on 2026-11-16, so parsers are tested against the true format.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from mars_explorer.api.app import create_app
from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import IngestService

FIXTURES = Path(__file__).parent / "fixtures"
FEED_FIXTURES = (
    "raw_images_list_navcam_sol2024.json",
    "raw_images_list_mcz_sol2024.json",
    "raw_images_list_hazcam_sol1500.json",
)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"fake-jpeg-payload" * 8
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-payload" * 8


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def all_feed_records() -> list[dict[str, Any]]:
    return [img for name in FEED_FIXTURES for img in load_fixture(name)["images"]]


class FakeNasa:
    """A tiny stand-in for the NASA endpoints, recording every request it receives."""

    def __init__(self) -> None:
        self.records = all_feed_records()
        self.requests: list[httpx.Request] = []
        self.fail_files = False
        self.feed_status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = request.url
        if url.path == "/rss/api/":
            return self._feed(request)
        if url.path.endswith("M20_waypoints.json"):
            return httpx.Response(200, json=load_fixture("mmgis_waypoints_sample.json"))
        if "/mars2020-raw-images/" in url.path:
            if self.fail_files:
                return httpx.Response(404, text="missing")
            if url.path.endswith(".png"):
                return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
            return httpx.Response(200, content=JPEG_BYTES, headers={"content-type": "image/jpg"})
        return httpx.Response(404, text="unknown")

    def _feed(self, request: httpx.Request) -> httpx.Response:
        if self.feed_status != 200:
            return httpx.Response(self.feed_status, text="error")
        params = request.url.params
        if params.get("latest") == "true":
            return httpx.Response(200, json=load_fixture("raw_images_latest.json"))
        records = self.records
        if "search" in params:
            wanted = set(params["search"].strip("|").split("|"))
            records = [r for r in records if r["camera"]["instrument"] in wanted]
        if "condition_2" in params:
            low = int(params["condition_2"].split(":")[0])
            records = [r for r in records if r["sol"] >= low]
        if "condition_3" in params:
            high = int(params["condition_3"].split(":")[0])
            records = [r for r in records if r["sol"] <= high]
        num, page = int(params.get("num", 100)), int(params.get("page", 0))
        chunk = records[page * num : (page + 1) * num]
        return httpx.Response(
            200,
            json={"images": chunk, "total_results": len(records), "page": page, "per_page": num},
        )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        request_delay_s=0,
        download_delay_s=0,
        max_retries=1,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def fake_nasa() -> FakeNasa:
    return FakeNasa()


@pytest.fixture
def http(fake_nasa: FakeNasa, settings: Settings) -> Iterator[httpx.Client]:
    with httpx.Client(
        transport=httpx.MockTransport(fake_nasa),
        headers={"User-Agent": settings.http_user_agent},
    ) as client:
        yield client


@pytest.fixture
def engine(settings: Settings) -> Engine:
    return make_engine(settings.database_path)


@pytest.fixture
def service(engine: Engine, settings: Settings, http: httpx.Client) -> IngestService:
    return IngestService(engine, settings, http, sleep=lambda _: None)


@pytest.fixture
def client(settings: Settings, fake_nasa: FakeNasa) -> Iterator[TestClient]:
    app = create_app(settings, transport=httpx.MockTransport(fake_nasa))
    with TestClient(app) as test_client:
        yield test_client
