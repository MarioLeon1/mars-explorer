"""Application settings, loaded from environment variables (prefix ``MARS_``) and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/mars_explorer/core/config.py -> parents[4] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MARS_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = REPO_ROOT / "data"
    db_path: Path | None = None
    log_level: str = "INFO"

    http_user_agent: str = "mars-explorer/0.1 (educational portfolio project)"
    http_timeout_s: float = 30.0
    max_retries: int = 3
    request_delay_s: float = 0.5
    download_delay_s: float = 0.15

    raw_feed_url: str = "https://mars.nasa.gov/rss/api/"
    mmgis_waypoints_url: str = "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def database_path(self) -> Path:
        return self.db_path or self.data_dir / "mars.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images" / "m2020"


@lru_cache
def get_settings() -> Settings:
    return Settings()
