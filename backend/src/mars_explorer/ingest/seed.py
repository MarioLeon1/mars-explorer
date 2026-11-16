"""Curated starter set: a small, representative slice of the mission (~130 images, ~12 MB).

Sol choice is data-driven (checked 2026-11-16): Hazcams are mainly used around drives, so we
pick sols that appear in the real JPL localization list (i.e. drive sols) and that have
Navcam, front/rear Hazcam and Mastcam-Z imagery in the feed. They span the whole mission:

- 2022: latest published localization -> its images match the rover position shown in the UI
- 2009, 1503, 1000, 502, 104: drive sols across the mission
- 64: Ingenuity helicopter flight period
- 1: first full day on Mars
"""

from __future__ import annotations

from mars_explorer.ingest.service import ImageSelection

SEED_SOLS: tuple[int, ...] = (2022, 2009, 1503, 1000, 502, 104, 64, 1)

SEED_CAMERAS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("NAVCAM_LEFT",), 6),
    (("FRONT_HAZCAM_LEFT_A", "FRONT_HAZCAM_LEFT_B"), 3),
    (("REAR_HAZCAM_LEFT",), 2),
    (("MCZ_LEFT",), 5),
)


def seed_selections() -> list[ImageSelection]:
    return [
        ImageSelection(sol_min=sol, sol_max=sol, instruments=instruments, limit=limit)
        for sol in SEED_SOLS
        for instruments, limit in SEED_CAMERAS
    ]
