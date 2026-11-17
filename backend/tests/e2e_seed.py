"""Build an isolated, offline data directory for the browser end-to-end tests.

Usage (from backend/):  uv run python -m tests.e2e_seed <data_dir>

Metadata comes from the real NASA/JPL responses captured in ``tests/fixtures/`` (feed records,
waypoints, traverse). Image *pixels* are a synthetic rock scene (``tests/vision_scenes``) so the
run needs no network; this directory is test-only and is never mixed with the user's ``data/``.
The directory is wiped first.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import httpx

from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import ImageSelection, IngestService
from tests.conftest import FakeNasa
from tests.vision_scenes import encode, rock_scene


def seed(data_dir: Path) -> None:
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    settings = Settings(
        data_dir=data_dir,
        request_delay_s=0,
        download_delay_s=0,
        anthropic_api_key=None,
        _env_file=None,  # type: ignore[call-arg]
    )
    nasa = FakeNasa()
    nasa.image_bytes = encode(rock_scene())
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        service.ingest_images([ImageSelection(sol_min=0, sol_max=5000)], sizes=("small", "large"))
        service.ingest_waypoints()
        service.ingest_traverse()
    engine.dispose()


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve()
    seed(target)
    print(f"e2e data ready in {target}")
