from __future__ import annotations

import math
from pathlib import Path

import httpx
import numpy as np
import pytest

from mars_explorer.core.errors import UpstreamError
from mars_explorer.ingest.traverse import parse_traverse
from mars_explorer.terrain.dem import Dem, DemSpec, en_to_lonlat, lonlat_to_en
from mars_explorer.terrain.fetch import download_resumable
from mars_explorer.terrain.layers import (
    CostModel,
    block_reduce,
    hillshade,
    roughness_m,
    slope_deg,
    traversability,
)
from tests.conftest import load_fixture
from tests.terrain_scenes import synthetic_elevation, synthetic_spec, write_dem


def plane(angle_deg: float, size: int = 64) -> np.ndarray:
    cols = np.arange(size, dtype=np.float32)[None, :].repeat(size, axis=0)
    return (cols * math.tan(math.radians(angle_deg))).astype(np.float32)


@pytest.mark.parametrize("angle", [0.0, 10.0, 25.0, 40.0])
def test_slope_of_a_tilted_plane_is_exact(angle: float) -> None:
    assert np.allclose(slope_deg(plane(angle), 1.0), angle, atol=1e-3)


def test_roughness_is_zero_on_a_plane_and_tracks_noise() -> None:
    # Interior is exact; two chained 5 px box filters reach 4 px into the reflected border
    # (the service pads maps with 8 m of real terrain, so ROIs never see it).
    assert np.nanmax(roughness_m(plane(20.0), 5)[4:-4, 4:-4]) < 1e-3
    rng = np.random.default_rng(0)
    noisy = plane(5.0, 128) + rng.normal(0, 0.2, (128, 128)).astype(np.float32)
    assert 0.1 < float(np.nanmedian(roughness_m(noisy, 5))) < 0.25
    holes = plane(5.0)
    holes[30, 30] = np.nan
    rough = roughness_m(holes, 5)
    assert np.isnan(rough[30, 30]) and np.isnan(rough[28, 32]) and np.isfinite(rough[40, 40])


def test_hillshade_range_and_block_reduce() -> None:
    shade = hillshade(plane(15.0), 1.0)
    assert 0.0 <= shade.min() <= shade.max() <= 1.0
    values = np.arange(16, dtype=np.float32).reshape(4, 4)
    assert block_reduce(values, 2, "max").tolist() == [[5, 7], [13, 15]]
    assert block_reduce(values, 2, "mean").tolist() == [[2.5, 4.5], [10.5, 12.5]]


def test_traversability_limits_and_cost_terms() -> None:
    model = CostModel(max_slope_deg=30, slope_weight=4, max_roughness_m=0.3, roughness_weight=3)
    gentle = traversability(plane(15.0), model)
    expected = 1 + 4 * (15 / 30) ** 2
    assert np.allclose(gentle.cost[5:-5, 5:-5], expected, atol=1e-3)
    assert np.all(gentle.risk[5:-5, 5:-5] == 1)  # 0.5 of the limit -> "moderate"
    steep = traversability(plane(35.0), model)
    assert np.all(np.isinf(steep.cost[5:-5, 5:-5])) and np.all(steep.risk[5:-5, 5:-5] == 3)
    unknown = plane(5.0)
    unknown[10:20, 10:20] = np.nan
    assert np.isinf(traversability(unknown, model).cost[15, 15])


def test_padding_removes_border_artefacts() -> None:
    padded = plane(20.0, 80)
    layers = traversability(padded, CostModel(), factor=1, pad=8)
    assert layers.roughness.shape == (64, 64)
    assert float(np.nanmax(layers.roughness)) < 1e-3  # no fake roughness at the ROI edge


def test_aggregation_is_conservative() -> None:
    z = plane(5.0)
    z[33, 33] += 3.0  # a 1 m spike
    coarse = traversability(z, CostModel(), factor=4)
    assert coarse.slope[8, 8] > 50  # the spike's steep flanks dominate its whole 4 m cell
    assert coarse.cost.shape == (16, 16)


def test_projection_round_trip_matches_mmgis() -> None:
    # Real waypoint (sol 2022): MMGIS lists easting 4342256.503, northing 1092764.278.
    e, n = lonlat_to_en(77.23322287, 18.43559434)
    assert e == pytest.approx(4342256.503, abs=0.01) and n == pytest.approx(1092764.278, abs=0.01)
    assert en_to_lonlat(e, n) == pytest.approx((77.23322287, 18.43559434), abs=1e-9)


def test_dem_reader_window_sample_and_overview(tmp_path: Path) -> None:
    spec = DemSpec(rows=40, cols=60, offset=64, x0=1000.5, y0=2000.5)
    z = np.arange(40 * 60, dtype=np.float32).reshape(40, 60)
    z[0, 0] = -3.0e38  # a no-data sentinel below the threshold
    path = tmp_path / "dem.img"
    write_dem(path, spec, z)
    dem = Dem(path, spec)
    assert np.isnan(dem.window(0, 0, 1, 1)[0, 0])
    win = dem.window(-2, 58, 4, 4)  # partly outside -> NaN padding
    assert np.isnan(win[0]).all() and win[2, 0] == z[0, 58]
    row, col = dem.rowcol(1005.5, 1990.5)
    assert (row, col) == (10.0, 5.0) and dem.en(10, 5) == (1005.5, 1990.5)
    assert dem.sample(1005.5, 1990.5) == pytest.approx(z[10, 5])
    assert dem.sample(1006.0, 1990.5) == pytest.approx((z[10, 5] + z[10, 6]) / 2)
    assert dem.sample(5000, 5000) is None
    assert dem.overview(10).shape == (4, 6)
    with pytest.raises(ValueError):
        Dem(path, DemSpec(rows=41, cols=60, offset=64))


def test_synthetic_scene_contains_the_fixture_drives(tmp_path: Path) -> None:
    spec = synthetic_spec()
    write_dem(tmp_path / "d.img", spec, synthetic_elevation(spec))
    dem = Dem(tmp_path / "d.img", spec)
    for drive in parse_traverse(load_fixture("mmgis_traverse_sample.json")):
        assert all(dem.contains(p[0], p[1]) for p in drive.points)


def test_traverse_parsing_preserves_real_geometry() -> None:
    drives = parse_traverse(load_fixture("mmgis_traverse_sample.json"))
    assert [d.sol for d in drives] == [1108, 1109, 1110]
    assert [len(d.points) for d in drives] == [80, 25, 34]
    for drive in drives:
        polyline = sum(
            math.dist(a[:2], b[:2]) for a, b in zip(drive.points, drive.points[1:], strict=False)
        )
        assert drive.length_m is not None
        assert polyline == pytest.approx(drive.length_m, rel=0.05)  # JPL's own length property


def test_download_resumes_with_range_requests(tmp_path: Path) -> None:
    payload = bytes(range(256)) * 40
    seen_ranges: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        rng = request.headers.get("range")
        seen_ranges.append(rng)
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
            return httpx.Response(206, content=payload[start:])
        return httpx.Response(200, content=payload)

    target = tmp_path / "file.bin"
    target.with_name("file.bin.part").write_bytes(payload[:1000])  # interrupted earlier
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download_resumable(client, "https://x/file", target, expected_size=len(payload))
    assert target.read_bytes() == payload and seen_ranges == ["bytes=1000-"]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download_resumable(client, "https://x/file", target, expected_size=len(payload))
    assert len(seen_ranges) == 1  # already complete: no request

    truncated = tmp_path / "t.bin"
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"abc"))
        ) as c,
        pytest.raises(UpstreamError),
    ):
        download_resumable(c, "https://x/t", truncated, expected_size=10)
    assert not truncated.exists()
