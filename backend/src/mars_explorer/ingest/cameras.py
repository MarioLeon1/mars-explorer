"""Catalog of Mars 2020 camera instrument ids as used by the raw-images feed.

Ids taken from the filter configuration of the official raw-images page (verified 2026-11-16).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CameraGroup(StrEnum):
    NAVCAM = "navcam"
    HAZCAM_FRONT = "hazcam_front"
    HAZCAM_REAR = "hazcam_rear"
    MASTCAMZ = "mastcamz"
    SKYCAM = "skycam"
    SUPERCAM = "supercam"
    SHERLOC = "sherloc"
    PIXL = "pixl"
    CACHECAM = "cachecam"
    EDL = "edl"
    HELICOPTER = "helicopter"
    OTHER = "other"


GROUP_ORDER: list[CameraGroup] = list(CameraGroup)


@dataclass(frozen=True, slots=True)
class CameraInfo:
    instrument: str
    group: CameraGroup
    label: str


_CATALOG: tuple[CameraInfo, ...] = (
    CameraInfo("NAVCAM_LEFT", CameraGroup.NAVCAM, "Navigation Camera — left (Navcam)"),
    CameraInfo("NAVCAM_RIGHT", CameraGroup.NAVCAM, "Navigation Camera — right (Navcam)"),
    CameraInfo("FRONT_HAZCAM_LEFT_A", CameraGroup.HAZCAM_FRONT, "Front Hazcam — left A"),
    CameraInfo("FRONT_HAZCAM_LEFT_B", CameraGroup.HAZCAM_FRONT, "Front Hazcam — left B"),
    CameraInfo("FRONT_HAZCAM_RIGHT_A", CameraGroup.HAZCAM_FRONT, "Front Hazcam — right A"),
    CameraInfo("FRONT_HAZCAM_RIGHT_B", CameraGroup.HAZCAM_FRONT, "Front Hazcam — right B"),
    CameraInfo("REAR_HAZCAM_LEFT", CameraGroup.HAZCAM_REAR, "Rear Hazcam — left"),
    CameraInfo("REAR_HAZCAM_RIGHT", CameraGroup.HAZCAM_REAR, "Rear Hazcam — right"),
    CameraInfo("MCZ_LEFT", CameraGroup.MASTCAMZ, "Mastcam-Z — left"),
    CameraInfo("MCZ_RIGHT", CameraGroup.MASTCAMZ, "Mastcam-Z — right"),
    CameraInfo("SKYCAM", CameraGroup.SKYCAM, "MEDA SkyCam"),
    CameraInfo("SUPERCAM_RMI", CameraGroup.SUPERCAM, "SuperCam Remote Micro-Imager"),
    CameraInfo("SHERLOC_WATSON", CameraGroup.SHERLOC, "SHERLOC — WATSON"),
    CameraInfo("SHERLOC_ACI", CameraGroup.SHERLOC, "SHERLOC — Context Imager (ACI)"),
    CameraInfo("PIXL_MCC", CameraGroup.PIXL, "PIXL Micro-Context Camera"),
    CameraInfo("CACHECAM", CameraGroup.CACHECAM, "Sample Caching System Camera (CacheCam)"),
    CameraInfo("EDL_PUCAM1", CameraGroup.EDL, "EDL — Parachute Up-Look Camera A"),
    CameraInfo("EDL_PUCAM2", CameraGroup.EDL, "EDL — Parachute Up-Look Camera B"),
    CameraInfo("EDL_DDCAM", CameraGroup.EDL, "EDL — Descent Stage Down-Look Camera"),
    CameraInfo("EDL_RUCAM", CameraGroup.EDL, "EDL — Rover Up-Look Camera"),
    CameraInfo("EDL_RDCAM", CameraGroup.EDL, "EDL — Rover Down-Look Camera"),
    CameraInfo("LCAM", CameraGroup.EDL, "Lander Vision System Camera (LCAM)"),
    CameraInfo("HELI_NAV", CameraGroup.HELICOPTER, "Ingenuity — Navigation Camera"),
    CameraInfo("HELI_RTE", CameraGroup.HELICOPTER, "Ingenuity — Return-to-Earth Camera"),
)

CATALOG: dict[str, CameraInfo] = {c.instrument: c for c in _CATALOG}


def camera_info(instrument: str) -> CameraInfo:
    """Return catalog info; unknown instruments are kept (never dropped) under group OTHER."""
    known = CATALOG.get(instrument)
    if known is not None:
        return known
    return CameraInfo(instrument, CameraGroup.OTHER, instrument.replace("_", " ").title())
