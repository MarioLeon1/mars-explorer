"""Access to the PLACES orbital DEM (``m20_orbital_dem.img``) without loading it into memory.

Product facts (read from its PDS4 label and embedded ODL header, 2026-11-17):

* 5480 lines × 14800 samples, IEEE-754 big-endian float32 (metres), data at byte 118400.
* Equirectangular, planetocentric, east-positive, sphere R = 3396.19 km,
  standard parallel 18.4663°, 1.0 m/pixel.
* SAMPLE_PROJECTION_OFFSET = −4340890.5, LINE_PROJECTION_OFFSET = 1097069.5, i.e. the centre of
  pixel (row r, col c) is at easting = 4340890.5 + c, northing = 1097069.5 − r (metres).
  This is the same grid as the JPL MMGIS waypoint easting/northing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

MARS_RADIUS_M = 3_396_190.0
STANDARD_PARALLEL_DEG = 18.4663

Elevation = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class DemSpec:
    rows: int = 5480
    cols: int = 14800
    offset: int = 118_400
    dtype: str = ">f4"
    cell_m: float = 1.0
    x0: float = 4_340_890.5  # easting of column 0 centre
    y0: float = 1_097_069.5  # northing of row 0 centre

    @property
    def nbytes(self) -> int:
        return self.offset + self.rows * self.cols * 4

    @property
    def easting_range(self) -> tuple[float, float]:
        half = self.cell_m / 2
        return self.x0 - half, self.x0 + (self.cols - 1) * self.cell_m + half

    @property
    def northing_range(self) -> tuple[float, float]:
        half = self.cell_m / 2
        return self.y0 - (self.rows - 1) * self.cell_m - half, self.y0 + half


PLACES_DEM = DemSpec()


def lonlat_to_en(lon: float, lat: float) -> tuple[float, float]:
    """Planetocentric lon/lat (deg, east-positive) → easting/northing in the DEM projection."""
    k = math.cos(math.radians(STANDARD_PARALLEL_DEG))
    return MARS_RADIUS_M * k * math.radians(lon), MARS_RADIUS_M * math.radians(lat)


def en_to_lonlat(easting: float, northing: float) -> tuple[float, float]:
    k = math.cos(math.radians(STANDARD_PARALLEL_DEG))
    return math.degrees(easting / (MARS_RADIUS_M * k)), math.degrees(northing / MARS_RADIUS_M)


class Dem:
    """Read-only, memory-mapped DEM. Invalid samples are returned as NaN."""

    def __init__(self, path: Path, spec: DemSpec = PLACES_DEM, nodata_below: float = -1.0e6):
        size = path.stat().st_size
        if size != spec.nbytes:
            raise ValueError(f"{path} has {size} bytes, expected {spec.nbytes}")
        self.path = path
        self.spec = spec
        self._nodata_below = nodata_below
        self._data = np.memmap(
            path, dtype=spec.dtype, mode="r", offset=spec.offset, shape=(spec.rows, spec.cols)
        )

    # ---- coordinates -----------------------------------------------------------------------

    def rowcol(self, easting: float, northing: float) -> tuple[float, float]:
        """Fractional (row, col) of a point; integer values are pixel centres."""
        return (self.spec.y0 - northing) / self.spec.cell_m, (
            easting - self.spec.x0
        ) / self.spec.cell_m

    def en(self, row: float, col: float) -> tuple[float, float]:
        return self.spec.x0 + col * self.spec.cell_m, self.spec.y0 - row * self.spec.cell_m

    def contains(self, easting: float, northing: float) -> bool:
        (e0, e1), (n0, n1) = self.spec.easting_range, self.spec.northing_range
        return e0 <= easting <= e1 and n0 <= northing <= n1

    # ---- sampling --------------------------------------------------------------------------

    def _clean(self, values: np.ndarray) -> Elevation:
        out = np.asarray(values, dtype=np.float32)  # big-endian -> native copy
        out[~np.isfinite(out) | (out < self._nodata_below)] = np.nan
        return out

    def window(self, row0: int, col0: int, rows: int, cols: int) -> Elevation:
        """Copy of a window; parts outside the DEM are NaN."""
        out = np.full((rows, cols), np.nan, np.float32)
        r0, c0 = max(row0, 0), max(col0, 0)
        r1, c1 = min(row0 + rows, self.spec.rows), min(col0 + cols, self.spec.cols)
        if r0 < r1 and c0 < c1:
            out[r0 - row0 : r1 - row0, c0 - col0 : c1 - col0] = self._clean(
                self._data[r0:r1, c0:c1]
            )
        return out

    def sample(self, easting: float, northing: float) -> float | None:
        """Bilinear elevation at a point, or None outside / on missing data."""
        row, col = self.rowcol(easting, northing)
        r, c = math.floor(row), math.floor(col)
        patch = self.window(r, c, 2, 2)
        if np.isnan(patch).any():
            return None
        fr, fc = row - r, col - c
        top = patch[0, 0] * (1 - fc) + patch[0, 1] * fc
        bottom = patch[1, 0] * (1 - fc) + patch[1, 1] * fc
        return float(top * (1 - fr) + bottom * fr)

    def overview(self, factor: int) -> Elevation:
        """Block-mean downsampled copy of the whole DEM (NaN-aware)."""
        rows, cols = self.spec.rows // factor, self.spec.cols // factor
        out = np.empty((rows, cols), np.float32)
        band = 256  # process in horizontal bands to bound memory
        for start in range(0, rows, band):
            stop = min(rows, start + band)
            block = self._clean(self._data[start * factor : stop * factor, : cols * factor])
            block = block.reshape(stop - start, factor, cols, factor)
            with np.errstate(invalid="ignore"):
                out[start:stop] = np.nanmean(block, axis=(1, 3))
        return out
