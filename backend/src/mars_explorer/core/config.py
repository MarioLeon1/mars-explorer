"""Application settings, loaded from environment variables (prefix ``MARS_``) and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/mars_explorer/core/config.py -> parents[4] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MARS_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
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
    mmgis_traverse_url: str = "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_traverse.json"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    places_dem_url: str = (
        "https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_rover_places/"
        "data_maps/m20_orbital_dem.img"
    )
    places_dem_label_url: str = (
        "https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_rover_places/"
        "data_maps/m20_orbital_dem.xml"
    )

    # ---- AI assistant (optional; disabled unless a key is configured) ----
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "MARS_ANTHROPIC_API_KEY"),
    )
    """Read from ANTHROPIC_API_KEY (the SDK's standard name) in the environment or ``.env``."""
    assistant_model: str = "claude-opus-5-5"
    assistant_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    assistant_max_tool_rounds: int = Field(default=8, ge=1, le=20)
    assistant_max_tokens: int = Field(default=16000, ge=1024, le=64000)
    assistant_fallbacks: bool = True
    """Server-side refusal fallbacks (beta). Ignored for Haiku models, which have none."""

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def database_path(self) -> Path:
        return self.db_path or self.data_dir / "mars.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images" / "m2020"

    @property
    def terrain_dir(self) -> Path:
        return self.data_dir / "terrain"


@lru_cache
def get_settings() -> Settings:
    return Settings()
