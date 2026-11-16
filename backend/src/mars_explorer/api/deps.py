"""FastAPI dependencies. Shared resources live on ``app.state`` (created in the lifespan)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from mars_explorer.core.config import Settings
from mars_explorer.ingest.downloader import ImageDownloader


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_downloader(request: Request) -> ImageDownloader:
    return request.app.state.downloader


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[Session, Depends(get_session)]
DownloaderDep = Annotated[ImageDownloader, Depends(get_downloader)]
