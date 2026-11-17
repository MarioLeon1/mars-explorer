"""Resumable download of large PDS products (HTTP Range), with size verification."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

import httpx

from mars_explorer.core.errors import UpstreamError

log = logging.getLogger(__name__)

CHUNK = 1 << 20  # 1 MiB


def download_resumable(
    client: httpx.Client,
    url: str,
    target: Path,
    *,
    expected_size: int | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Download ``url`` to ``target``. Partial data in ``target.part`` is resumed with a Range
    request; the file is renamed into place only when complete (and size-checked)."""
    if target.is_file() and (expected_size is None or target.stat().st_size == expected_size):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}

    with client.stream("GET", url, headers=headers, timeout=60.0) as response:
        if response.status_code == 416 and expected_size and have == expected_size:
            pass  # already complete
        elif response.status_code not in (200, 206):
            raise UpstreamError(f"GET {url} returned HTTP {response.status_code}")
        else:
            if response.status_code == 200 and have:
                log.info("server ignored Range; restarting download of %s", url)
                have = 0
            length = response.headers.get("content-length")
            total = have + int(length) if length else expected_size
            mode = "ab" if response.status_code == 206 else "wb"
            with part.open(mode) as handle:
                done = have
                for chunk in response.iter_bytes(CHUNK):
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)

    size = part.stat().st_size
    if expected_size is not None and size != expected_size:
        raise UpstreamError(
            f"incomplete download: {size} of {expected_size} bytes (rerun to resume)"
        )
    os.replace(part, target)
    return target
