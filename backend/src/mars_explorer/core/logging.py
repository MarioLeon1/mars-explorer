"""Logging setup shared by the API and the ingestion CLI."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT, datefmt="%H:%M:%S")
    # httpx logs every request at INFO; keep it quieter unless debugging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
