"""Opt-in smoke tests against the real NASA/JPL endpoints: ``uv run pytest -m live``.

They detect upstream format changes early. They are excluded from the default run so the
suite stays fast, deterministic and offline.
"""

from __future__ import annotations

import pytest

from mars_explorer.core.config import Settings
from mars_explorer.ingest.http import get_with_retries, make_http_client
from mars_explorer.ingest.parse import parse_raw_image
from mars_explorer.ingest.raw_feed import FeedQuery, RawImagesClient
from mars_explorer.ingest.waypoints import parse_waypoints

pytestmark = pytest.mark.live


@pytest.fixture
def live_settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_raw_feed_contract(live_settings: Settings) -> None:
    with make_http_client(live_settings) as http:
        client = RawImagesClient(http, live_settings)
        page = client.fetch_page(
            FeedQuery(sol_min=2024, sol_max=2024, instruments=("NAVCAM_LEFT",), page_size=3), 0
        )
        assert page.images, "feed returned no NAVCAM_LEFT images for sol 2024"
        image = parse_raw_image(page.images[0])
        assert image.sol == 2024 and image.instrument == "NAVCAM_LEFT"
        assert image.url_large and image.date_taken_utc
        latest = client.latest()
        assert latest.latest_sol and latest.latest_sol >= 2031


def test_image_file_downloads(live_settings: Settings) -> None:
    with make_http_client(live_settings) as http:
        page = RawImagesClient(http, live_settings).fetch_page(
            FeedQuery(sol_min=2024, sol_max=2024, instruments=("NAVCAM_LEFT",), page_size=1), 0
        )
        url = parse_raw_image(page.images[0]).url_small
        assert url
        response = get_with_retries(http, url)
        assert response.headers["content-type"].startswith("image/")
        assert len(response.content) > 1000


def test_mmgis_waypoints_contract(live_settings: Settings) -> None:
    with make_http_client(live_settings) as http:
        response = get_with_retries(http, live_settings.mmgis_waypoints_url)
        waypoints = parse_waypoints(response.json())
        assert len(waypoints) >= 700
        assert waypoints[-1].sol >= 2022


def test_official_videos_and_featured_sequences_still_published(live_settings: Settings) -> None:
    from mars_explorer.ingest.parse import parse_sequence_id
    from mars_explorer.replay.service import FEATURED
    from mars_explorer.replay.videos import OFFICIAL_VIDEOS

    with make_http_client(live_settings) as http:
        for video in OFFICIAL_VIDEOS:
            for url in (video.video_url, video.poster_url):
                response = http.head(url, follow_redirects=True)
                assert response.status_code == 200, url
        assert http.head(OFFICIAL_VIDEOS[0].video_url).headers["content-type"] == "video/mp4"
        client = RawImagesClient(http, live_settings)
        for item in FEATURED:
            records = list(
                client.iter_images(
                    FeedQuery(sol_min=item.sol, sol_max=item.sol, instruments=(item.instrument,)),
                    limit=item.job_limit,
                )
            )
            ids = [parse_sequence_id(r["imageid"]) for r in records]
            in_sequence = [s for s in ids if s == item.sequence_id]
            assert len(in_sequence) == item.published_frames, item.key
