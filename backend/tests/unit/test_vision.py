from __future__ import annotations

import numpy as np
import pytest

from mars_explorer.core.errors import InvalidRequestError
from mars_explorer.vision.evaluation import Point, agreement, match_points
from mars_explorer.vision.features import disparity_stats, match_images
from mars_explorer.vision.methods import METHODS, MethodOutput, get_method
from mars_explorer.vision.ops import canny_auto, clahe, valid_mask
from mars_explorer.vision.rocks import Candidate, detect_blobs, detect_contours, non_max_suppression
from mars_explorer.vision.texture import texture_classes
from tests.vision_scenes import ROCKS, SIZE, rock_scene, textured_pair

TRUTH = [Point(x, y) for x, y, _ in ROCKS]


def _recall(found: list[Candidate]) -> float:
    counts = match_points([Point(c.x, c.y, c.r) for c in found], TRUTH, SIZE[1])
    assert counts.recall is not None
    return counts.recall


def test_blob_detector_finds_known_rocks() -> None:
    found = detect_blobs(rock_scene())
    assert _recall(found) == 1.0
    assert len(found) <= 3 * len(ROCKS)  # few spurious candidates on clean ground


def test_contour_detector_finds_known_rocks() -> None:
    found = detect_contours(rock_scene())
    assert _recall(found) >= 5 / 6


def test_edge_rejection_suppresses_the_long_shadow_boundary() -> None:
    boundary_y = SIZE[0] // 5

    def on_boundary(found: list[Candidate]) -> int:
        return sum(1 for c in found if abs(c.y - boundary_y) < 12 and c.y < 60 + boundary_y)

    # A low threshold makes the straight shadow boundary respond; only the Hessian test differs.
    with_test = detect_blobs(rock_scene(), edge_ratio=10.0, min_strength=0.3)
    without_test = detect_blobs(rock_scene(), edge_ratio=0.0, min_strength=0.3)
    assert on_boundary(without_test) > 0, "scene should provoke edge responses"
    assert on_boundary(with_test) < on_boundary(without_test)


def test_roi_excludes_top_band() -> None:
    found = detect_blobs(rock_scene(), roi_top=0.5)
    assert all(c.y >= SIZE[0] * 0.5 for c in found)


def test_working_resolution_maps_back_to_input_pixels() -> None:
    big = np.kron(rock_scene(), np.ones((2, 2), np.uint8))  # 960×1520 > WORK_MAX_SIDE
    found = detect_blobs(big, min_radius=12, max_radius=120)
    counts = match_points(
        [Point(c.x, c.y, c.r) for c in found],
        [Point(2 * p.x, 2 * p.y) for p in TRUTH],
        big.shape[1],
    )
    assert counts.recall == 1.0


def test_non_max_suppression_keeps_strongest() -> None:
    kept = non_max_suppression([Candidate(10, 10, 5, 1.0, 1), Candidate(12, 10, 5, 2.0, 1)])
    assert kept == [Candidate(12, 10, 5, 2.0, 1)]


def test_basic_ops() -> None:
    scene = rock_scene()
    assert clahe(scene).shape == scene.shape
    assert canny_auto(scene).any()
    mask = valid_mask(scene, margin=0.1, roi_top=0.0)
    assert not mask[0].any() and mask[SIZE[0] // 2, SIZE[1] // 2]


def test_texture_ranks_smooth_before_rough() -> None:
    rng = np.random.default_rng(0)
    image = np.full((256, 256), 128, np.uint8)
    image[:, 128:] = np.clip(128 + rng.normal(0, 30, (256, 128)), 0, 255).astype(np.uint8)
    result = texture_classes(image, tile=16, k=2)
    assert (result.labels[:, :8] == 0).all()  # smooth half -> class 0
    assert (result.labels[:, 8:] == 1).all()
    assert result.fractions == pytest.approx([0.5, 0.5])


def test_matching_recovers_a_known_shift() -> None:
    left, right = textured_pair(shift=20)
    result = match_images(left, right)
    assert len(result.inliers) > 100
    stats = disparity_stats(result.inliers)
    assert stats["dx_median_px"] == pytest.approx(-20, abs=0.5)
    assert stats["dy_median_px"] == pytest.approx(0, abs=0.5)


def test_one_to_one_matching_and_tolerance() -> None:
    truth = [Point(100, 100), Point(300, 300)]
    detections = [Point(102, 101, 5), Point(104, 99, 5), Point(500, 500, 5)]
    counts = match_points(detections, truth, image_width=1000)  # tolerance 15 px
    assert (counts.true_positives, counts.false_positives, counts.false_negatives) == (1, 2, 1)
    assert counts.precision == pytest.approx(1 / 3)
    assert counts.recall == pytest.approx(1 / 2)
    assert match_points([], [], 1000).precision is None
    assert agreement([], [], 1000) is None
    assert agreement(truth, truth, 1000) == pytest.approx(1.0)


def test_param_validation() -> None:
    spec = get_method("rocks_blob")
    assert spec.resolve({})["min_radius"] == 6.0
    assert spec.resolve({"min_radius": "8"})["min_radius"] == 8.0
    for bad in ({"min_radius": 1000}, {"nope": 1}, {"polarity": "sideways"}, {"min_radius": "x"}):
        with pytest.raises(InvalidRequestError):
            spec.resolve(bad)
    with pytest.raises(InvalidRequestError):
        get_method("texture").resolve({"relative": "yes"})
    with pytest.raises(InvalidRequestError):
        get_method("texture").resolve({"k": 2.5})
    with pytest.raises(InvalidRequestError):
        get_method("magic")


@pytest.mark.parametrize("name", sorted(METHODS))
def test_every_method_runs_and_reports(name: str) -> None:
    spec = METHODS[name]
    output = MethodOutput()
    spec.run(rock_scene(), spec.resolve({}), output)
    assert output.timings_ms and all(v >= 0 for v in output.timings_ms.values())
    for layer in output.layers:
        assert layer.rgba.shape == (*SIZE, 4) and layer.rgba.dtype == np.uint8
    if spec.category == "detection":
        assert output.detections is not None and spec.score_definition
    assert spec.limitations, "every method must state its limitations"


def test_detection_stats_report_the_candidate_cap() -> None:
    rng = np.random.default_rng(1)
    noisy = np.clip(128 + rng.normal(0, 60, (900, 1200)), 0, 255).astype(np.uint8)
    spec = METHODS["rocks_blob"]
    output = MethodOutput()
    spec.run(noisy, spec.resolve({"min_strength": 0.2, "min_radius": 2.0}), output)
    assert output.stats["candidates"] == 300
    assert "strongest 300" in str(output.stats["capped"])


def test_nms_is_fast_and_bounded_on_pathological_input() -> None:
    import time

    rng = np.random.default_rng(2)
    many = [
        Candidate(float(x), float(y), 3.0, float(s), 28.0)
        for x, y, s in zip(
            rng.uniform(0, 1200, 50_000),
            rng.uniform(0, 900, 50_000),
            rng.uniform(0, 1, 50_000),
            strict=True,
        )
    ]
    start = time.perf_counter()
    kept = non_max_suppression(many, limit=300)
    assert len(kept) == 300
    assert time.perf_counter() - start < 2.0
    assert kept[0].score == max(c.score for c in many)
