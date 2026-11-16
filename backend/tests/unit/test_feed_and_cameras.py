from __future__ import annotations

import httpx
import pytest

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import UpstreamError
from mars_explorer.ingest.cameras import CATALOG, CameraGroup, camera_info
from mars_explorer.ingest.http import get_with_retries
from mars_explorer.ingest.raw_feed import FeedQuery, RawImagesClient, build_params
from tests.conftest import FakeNasa


def test_camera_catalog() -> None:
    assert camera_info("NAVCAM_LEFT").group is CameraGroup.NAVCAM
    assert camera_info("FRONT_HAZCAM_LEFT_B").group is CameraGroup.HAZCAM_FRONT
    assert camera_info("MCZ_RIGHT").group is CameraGroup.MASTCAMZ
    unknown = camera_info("NEW_CAMERA_X")
    assert unknown.group is CameraGroup.OTHER and unknown.instrument == "NEW_CAMERA_X"
    assert len(CATALOG) == 24


def test_build_params() -> None:
    params = build_params(
        FeedQuery(
            sol_min=10, sol_max=12, instruments=("FRONT_HAZCAM_LEFT_A", "FRONT_HAZCAM_LEFT_B")
        ),
        page=2,
    )
    assert params["search"] == "|FRONT_HAZCAM_LEFT_A|FRONT_HAZCAM_LEFT_B"
    assert params["condition_2"] == "10:sol:gte"
    assert params["condition_3"] == "12:sol:lte"
    assert params["page"] == "2" and params["num"] == "100"
    assert params["extended"] == "sample_type::full,"


def test_pipe_is_percent_encoded_on_the_wire(
    http: httpx.Client, settings: Settings, fake_nasa: FakeNasa
) -> None:
    # A literal '|' in the URL makes the real feed answer HTTP 400.
    client = RawImagesClient(http, settings, sleep=lambda _: None)
    client.fetch_page(FeedQuery(instruments=("NAVCAM_LEFT",)), page=0)
    raw_url = str(fake_nasa.requests[-1].url)
    assert "|" not in raw_url
    assert "search=%7CNAVCAM_LEFT" in raw_url


def test_iter_images_respects_limit_and_pages(
    http: httpx.Client, settings: Settings, fake_nasa: FakeNasa
) -> None:
    client = RawImagesClient(http, settings, sleep=lambda _: None)
    records = list(client.iter_images(FeedQuery(page_size=2), limit=5))
    assert len(records) == 5
    assert len(fake_nasa.requests) == 3  # pages of 2, 2, 1


def test_iter_images_stops_at_reported_total(
    http: httpx.Client, settings: Settings, fake_nasa: FakeNasa
) -> None:
    client = RawImagesClient(http, settings, sleep=lambda _: None)
    records = list(client.iter_images(FeedQuery(instruments=("MCZ_LEFT",), page_size=2)))
    assert len(records) == 3
    assert len(fake_nasa.requests) == 2


def test_latest(http: httpx.Client, settings: Settings) -> None:
    latest = RawImagesClient(http, settings, sleep=lambda _: None).latest()
    assert latest.latest_sol == 2031 and latest.total_images == 1055868


def test_retries_then_raises_on_server_errors() -> None:
    calls: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    sleeps: list[float] = []
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(UpstreamError),
    ):
        get_with_retries(client, "https://example.test/x", max_retries=2, sleep=sleeps.append)
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_client_errors_are_not_retried() -> None:
    calls: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(UpstreamError),
    ):
        get_with_retries(client, "https://example.test/x", max_retries=3, sleep=lambda _: None)
    assert len(calls) == 1
