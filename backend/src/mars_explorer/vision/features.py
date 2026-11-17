"""ORB keypoints and robust matching between two images (e.g. a stereo pair).

Matches are filtered with Lowe's ratio test, then by a RANSAC-estimated fundamental matrix
(epipolar geometry). For a verified stereo pair the horizontal offset of inlier matches is the
*disparity in pixels*: larger for nearer surfaces. Converting it to metres needs the camera
models and baseline — not done here.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from mars_explorer.vision.ops import Gray, clahe


@dataclass(frozen=True, slots=True)
class Keypoint:
    x: float
    y: float
    size: float
    response: float


@dataclass(frozen=True, slots=True)
class Match:
    ax: float
    ay: float
    bx: float
    by: float
    inlier: bool


@dataclass(frozen=True, slots=True)
class MatchResult:
    keypoints_a: int
    keypoints_b: int
    tentative: int
    matches: list[Match]

    @property
    def inliers(self) -> list[Match]:
        return [m for m in self.matches if m.inlier]


def _orb(n_features: int) -> cv2.ORB:
    return cv2.ORB_create(nfeatures=n_features, scaleFactor=1.2, nlevels=8, fastThreshold=12)


def detect_keypoints(gray: Gray, *, n_features: int = 1500) -> list[Keypoint]:
    keypoints = _orb(n_features).detect(clahe(gray), None)
    return [Keypoint(k.pt[0], k.pt[1], k.size, k.response) for k in keypoints]


def match_images(
    gray_a: Gray,
    gray_b: Gray,
    *,
    n_features: int = 3000,
    ratio: float = 0.75,
    ransac_px: float = 1.5,
) -> MatchResult:
    orb = _orb(n_features)
    kp_a, des_a = orb.detectAndCompute(clahe(gray_a), None)
    kp_b, des_b = orb.detectAndCompute(clahe(gray_b), None)
    if des_a is None or des_b is None or len(kp_a) < 8 or len(kp_b) < 8:
        return MatchResult(len(kp_a), len(kp_b), 0, [])

    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des_a, des_b, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < ratio * p[1].distance]
    if len(good) < 8:
        return MatchResult(len(kp_a), len(kp_b), len(good), [])

    pts_a = np.float32([kp_a[m.queryIdx].pt for m in good])
    pts_b = np.float32([kp_b[m.trainIdx].pt for m in good])
    _, mask = cv2.findFundamentalMat(pts_a, pts_b, cv2.FM_RANSAC, ransac_px, 0.999)
    inlier = mask.reshape(-1).astype(bool) if mask is not None else np.zeros(len(good), bool)
    matches = [
        Match(float(a[0]), float(a[1]), float(b[0]), float(b[1]), bool(ok))
        for a, b, ok in zip(pts_a, pts_b, inlier, strict=True)
    ]
    return MatchResult(len(kp_a), len(kp_b), len(good), matches)


def disparity_stats(matches: list[Match]) -> dict[str, float]:
    """Horizontal/vertical offsets (B − A) of matches, in pixels: median and interquartile range."""
    if not matches:
        return {}
    dx = np.array([m.bx - m.ax for m in matches])
    dy = np.array([m.by - m.ay for m in matches])
    q = lambda v, p: float(np.percentile(v, p))  # noqa: E731
    return {
        "dx_median_px": q(dx, 50),
        "dx_iqr_px": q(dx, 75) - q(dx, 25),
        "dy_median_px": q(dy, 50),
        "dy_iqr_px": q(dy, 75) - q(dy, 25),
    }
