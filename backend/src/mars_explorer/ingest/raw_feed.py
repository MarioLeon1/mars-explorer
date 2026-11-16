"""Client for the Mars 2020 raw-images JSON feed (the one behind the official raw-images page).

Endpoint verified live 2026-11-16. It is undocumented, so responses are validated defensively.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import UpstreamError
from mars_explorer.ingest.http import get_with_retries

log = logging.getLogger(__name__)

MAX_PAGE_SIZE = 100  # the feed caps `num` at 100


@dataclass(frozen=True, slots=True)
class FeedQuery:
    sol_min: int | None = None
    sol_max: int | None = None
    instruments: Sequence[str] = ()
    order: Literal["desc", "asc"] = "desc"
    page_size: int = MAX_PAGE_SIZE


@dataclass(frozen=True, slots=True)
class FeedPage:
    images: list[dict[str, Any]]
    total_results: int | None


@dataclass(frozen=True, slots=True)
class FeedLatest:
    latest_sol: int | None
    total_images: int | None


def build_params(query: FeedQuery, page: int) -> dict[str, str]:
    """Translate a query into feed parameters (encoded later by httpx)."""
    params = {
        "feed": "raw_images",
        "category": "mars2020",
        "feedtype": "json",
        "num": str(max(1, min(query.page_size, MAX_PAGE_SIZE))),
        "page": str(page),
        "order": f"sol {query.order}",
        "extended": "sample_type::full,",
    }
    if query.instruments:
        params["search"] = "|" + "|".join(query.instruments)
    if query.sol_min is not None:
        params["condition_2"] = f"{query.sol_min}:sol:gte"
    if query.sol_max is not None:
        params["condition_3"] = f"{query.sol_max}:sol:lte"
    return params


class RawImagesClient:
    def __init__(
        self,
        http: httpx.Client,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http
        self._settings = settings
        self._sleep = sleep

    def _get_json(self, params: dict[str, str]) -> dict[str, Any]:
        response = get_with_retries(
            self._http,
            self._settings.raw_feed_url,
            params=params,
            max_retries=self._settings.max_retries,
            sleep=self._sleep,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamError("raw-images feed returned non-JSON content") from exc
        if not isinstance(payload, dict):
            raise UpstreamError("raw-images feed returned an unexpected JSON shape")
        return payload

    def fetch_page(self, query: FeedQuery, page: int) -> FeedPage:
        payload = self._get_json(build_params(query, page))
        images = payload.get("images")
        if not isinstance(images, list):
            raise UpstreamError("raw-images feed response has no 'images' list")
        total = payload.get("total_results")
        return FeedPage(images=images, total_results=total if isinstance(total, int) else None)

    def iter_images(self, query: FeedQuery, limit: int | None = None) -> Iterator[dict[str, Any]]:
        """Yield raw records page by page until ``limit``, an empty page, or the reported total."""
        yielded = 0
        page = 0
        while True:
            if page > 0:
                self._sleep(self._settings.request_delay_s)
            result = self.fetch_page(query, page)
            for record in result.images:
                if limit is not None and yielded >= limit:
                    return
                yield record
                yielded += 1
            seen = (page + 1) * query.page_size
            if not result.images or (
                result.total_results is not None and seen >= result.total_results
            ):
                return
            if limit is not None and yielded >= limit:
                return
            page += 1

    def latest(self) -> FeedLatest:
        payload = self._get_json(
            {
                "feed": "raw_images",
                "category": "mars2020",
                "feedtype": "json",
                "ver": "1.2",
                "latest": "true",
                "num": "1",
            }
        )
        latest_sol = payload.get("latest_sol")
        total = payload.get("total")
        return FeedLatest(
            latest_sol=latest_sol if isinstance(latest_sol, int) else None,
            total_images=total if isinstance(total, int) else None,
        )
