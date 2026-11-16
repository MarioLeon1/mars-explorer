"""Polite HTTP access to NASA/JPL endpoints: identified User-Agent, timeouts, retries."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping

import httpx

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import UpstreamError

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def make_http_client(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.http_user_agent},
        timeout=settings.http_timeout_s,
        follow_redirects=True,
        transport=transport,
    )


def get_with_retries(
    client: httpx.Client,
    url: str,
    *,
    params: Mapping[str, str | int] | None = None,
    max_retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """GET with exponential backoff on network errors and retryable statuses.

    Query parameters must be passed via ``params`` so they are percent-encoded: the raw-images
    feed answers HTTP 400 to a literal ``|`` in the URL.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:
            if attempt > max_retries:
                raise UpstreamError(f"GET {url} failed after {attempt} attempts: {exc}") from exc
            log.warning("GET %s failed (%s); retry %d/%d", url, exc, attempt, max_retries)
        else:
            if response.status_code < 400:
                return response
            if response.status_code not in RETRYABLE_STATUS or attempt > max_retries:
                raise UpstreamError(
                    f"GET {response.request.url} returned HTTP {response.status_code}"
                )
            log.warning(
                "GET %s returned %d; retry %d/%d",
                url,
                response.status_code,
                attempt,
                max_retries,
            )
        sleep(min(2 ** (attempt - 1), 30))
