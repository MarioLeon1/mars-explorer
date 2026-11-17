"""Curated official NASA videos (NASA Image and Video Library, images.nasa.gov).

These are *real* NASA products, shown as such, with their own credit. The list is an allowlist
verified live on 2026-11-17: the ``~medium.mp4`` rendition exists for every entry and the poster
image (HTTP 200). Files are streamed by the browser straight from NASA (``<video>`` needs no CORS);
nothing is downloaded to ``data/``.

Asset URLs follow ``https://images-assets.nasa.gov/video/<id>/<id>~<rendition>.mp4`` with the id
percent-encoded (several ids contain a typographic apostrophe). The library's own API returns
``http://`` links; we always use ``https://``.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

ASSET_BASE = "https://images-assets.nasa.gov/video"
DETAILS_BASE = "https://images.nasa.gov/details"


@dataclass(frozen=True, slots=True)
class OfficialVideo:
    nasa_id: str
    title: str
    date: str
    sol: int | None
    description: str
    credit: str
    poster: str = "small"
    rendition: str = "medium"

    @property
    def video_url(self) -> str:
        encoded = quote(self.nasa_id)
        return f"{ASSET_BASE}/{encoded}/{encoded}~{self.rendition}.mp4"

    @property
    def poster_url(self) -> str:
        encoded = quote(self.nasa_id)
        return f"{ASSET_BASE}/{encoded}/{encoded}~{self.poster}.jpg"

    @property
    def page_url(self) -> str:
        return f"{DETAILS_BASE}/{quote(self.nasa_id)}"


OFFICIAL_VIDEOS: tuple[OfficialVideo, ...] = (
    OfficialVideo(
        nasa_id="JPL-20210222-M2020f-0001-Perseverance Rover’s Descent and Touchdown on Mars",
        title="Perseverance Rover's Descent and Touchdown on Mars (onboard camera views)",
        date="2021-02-22",
        sol=0,
        description=(
            "Real footage from the entry, descent and landing camera suite: parachute "
            "deployment, heat-shield separation, sky-crane manoeuvre and touchdown in Jezero "
            "crater on 18 February 2021."
        ),
        credit="NASA/JPL-Caltech",
    ),
    OfficialVideo(
        nasa_id="JPL-20210419-TECHf-0001-First Video of NASA’s Ingenuity Mars Helicopter in Flight",
        title="First Video of NASA's Ingenuity Mars Helicopter in Flight",
        date="2021-04-19",
        sol=58,
        description=(
            "Mastcam-Z images from Perseverance, parked at Van Zyl Overlook about 64 m away, of "
            "the first powered, controlled flight on another planet."
        ),
        credit="NASA/JPL-Caltech/ASU/MSSS",
        poster="medium",
    ),
    OfficialVideo(
        nasa_id="JPL-20210425-TECHf-0001-Ingenuity Third Flight MastcamZ Video",
        title="Perseverance's Mastcam-Z Captures Ingenuity's Third Flight",
        date="2021-04-25",
        sol=64,
        description=(
            "Ingenuity takes off, flies about 50 m downrange out of the field of view and "
            "returns to land, as recorded by Mastcam-Z."
        ),
        credit="NASA/JPL-Caltech/ASU/MSSS",
    ),
)
