"""Download image renditions into the local store, with dedupe and atomic writes.

Layout: ``<data_dir>/images/m2020/sol_<sol:05d>/<image_id>/<size>.<ext>`` plus ``metadata.json``
holding the original NASA record verbatim.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from sqlmodel import Session, select

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import UpstreamError
from mars_explorer.db.models import ImageFile, ImageRecord, utcnow
from mars_explorer.ingest.http import get_with_retries

log = logging.getLogger(__name__)

ImageSize = Literal["small", "large", "full_res"]
SIZES: tuple[ImageSize, ...] = ("small", "large", "full_res")
_EXTENSIONS: dict[str, str] = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png"}
_CANONICAL_TYPES: dict[str, str] = {".jpg": "image/jpeg", ".png": "image/png"}


@dataclass(frozen=True, slots=True)
class DownloadResult:
    status: Literal["downloaded", "skipped", "failed"]
    file: ImageFile | None = None
    error: str | None = None


class ImageDownloader:
    def __init__(
        self,
        http: httpx.Client,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http
        self._settings = settings
        self._sleep = sleep

    def image_dir(self, image: ImageRecord) -> Path:
        return self._settings.images_dir / f"sol_{image.sol:05d}" / image.image_id

    def absolute(self, file: ImageFile) -> Path:
        return self._settings.data_dir / file.path

    def cached(self, session: Session, image_id: str, size: str) -> ImageFile | None:
        """Return the cache entry only if the file is really on disk with the recorded size."""
        file = session.exec(
            select(ImageFile).where(ImageFile.image_id == image_id, ImageFile.size == size)
        ).first()
        if file is None:
            return None
        path = self.absolute(file)
        if not path.is_file() or path.stat().st_size != file.bytes:
            return None
        return file

    def write_metadata(self, image: ImageRecord) -> None:
        target = self.image_dir(image) / "metadata.json"
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        record = json.loads(image.raw_json)
        _atomic_write(target, json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8"))

    def ensure(self, session: Session, image: ImageRecord, size: ImageSize) -> DownloadResult:
        """Make sure ``size`` of ``image`` is cached locally; download it if needed."""
        existing = self.cached(session, image.image_id, size)
        if existing is not None:
            return DownloadResult("skipped", existing)

        url = image.original_url(size)
        if not url:
            return DownloadResult("failed", error=f"no {size} URL in NASA record")
        try:
            response = get_with_retries(
                self._http, url, max_retries=self._settings.max_retries, sleep=self._sleep
            )
        except UpstreamError as exc:
            log.warning("download failed for %s/%s: %s", image.image_id, size, exc.message)
            return DownloadResult("failed", error=exc.message)

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        extension = _EXTENSIONS.get(content_type) or Path(url).suffix.lower()
        if extension not in _CANONICAL_TYPES:
            message = f"unexpected content-type {content_type!r} for {url}"
            log.warning(message)
            return DownloadResult("failed", error=message)
        content = response.content
        if not content:
            return DownloadResult("failed", error=f"empty body for {url}")

        directory = self.image_dir(image)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{size}{extension}"
        _atomic_write(target, content)
        self.write_metadata(image)

        file = session.exec(
            select(ImageFile).where(ImageFile.image_id == image.image_id, ImageFile.size == size)
        ).first() or ImageFile(
            image_id=image.image_id,
            size=size,
            path="",
            bytes=0,
            sha256="",
            content_type="",
            source_url=url,
        )
        file.path = target.relative_to(self._settings.data_dir).as_posix()
        file.bytes = len(content)
        file.sha256 = hashlib.sha256(content).hexdigest()
        file.content_type = _CANONICAL_TYPES[extension]
        file.source_url = url
        file.downloaded_at = utcnow()
        session.add(file)
        session.commit()
        session.refresh(file)
        self._sleep(self._settings.download_delay_s)
        return DownloadResult("downloaded", file)


def _atomic_write(target: Path, content: bytes) -> None:
    """Write via a temp file + rename so a crash never leaves a truncated image behind."""
    tmp = target.with_name(target.name + ".part")
    tmp.write_bytes(content)
    os.replace(tmp, target)
