"""Mission Replay core: sequence grouping/classification, LMST placement, official videos."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mars_explorer.replay.sequences import (
    FrameMeta,
    build_sequence,
    group_sequences,
    parse_sequence_key,
    sequence_key,
)
from mars_explorer.replay.timeline import SECONDS_PER_LMST_HOUR, calibrate, lmst_hours
from mars_explorer.replay.videos import OFFICIAL_VIDEOS


def frame(
    n: int,
    sclk: float | None,
    *,
    instrument: str = "NAVCAM_LEFT",
    seq: str | None = "NCAM00520",
    az: float | None = -90.49,
    el: float | None = 29.67,
    sol: int = 2024,
    utc: datetime | None = None,
) -> FrameMeta:
    return FrameMeta(
        image_id=f"IMG_{n:03d}",
        sol=sol,
        instrument=instrument,
        sequence_id=seq,
        sclk=sclk,
        date_taken_utc=utc,
        mast_az=az,
        mast_el=el,
        width=1280,
        height=960,
    )


def test_fixed_pointing_time_series_is_ordered_by_sclk() -> None:
    # Real sol 2024 NCAM00518 shape: same pointing (tiny metadata jitter), one frame every ~25 s.
    frames = [frame(i, 846620257.3 + 25 * i, az=-90.4881 - 0.0001 * (i % 2)) for i in (3, 0, 2, 1)]
    seq = build_sequence(frames)
    assert seq.kind == "fixed_pointing"
    assert [f.meta.image_id for f in seq.frames] == ["IMG_000", "IMG_001", "IMG_002", "IMG_003"]
    assert [f.t_offset_s for f in seq.frames] == pytest.approx([0, 25, 50, 75])
    assert seq.duration_s == pytest.approx(75)
    assert seq.median_interval_s == pytest.approx(25)
    assert seq.distinct_pointings == 1


def test_sclk_wins_over_wrong_utc_dates() -> None:
    # Around landing the feed's UTC dates are wrong; SCLK is the instrument's own clock.
    late = datetime(2021, 1, 1, tzinfo=UTC)
    early = datetime(2030, 1, 1, tzinfo=UTC)
    seq = build_sequence([frame(1, 200.0, utc=late), frame(2, 100.0, utc=early)])
    assert [f.meta.image_id for f in seq.frames] == ["IMG_002", "IMG_001"]


def test_changing_mast_pointing_is_a_sweep_not_motion() -> None:
    frames = [frame(i, 1000.0 + 15 * i, az=10.0 * i) for i in range(5)]
    seq = build_sequence(frames)
    assert seq.kind == "pointing_sweep"
    assert seq.distinct_pointings == 5
    assert "not motion" in seq.notes[0]


def test_vehicle_fixed_cameras_ignore_mast_pointing() -> None:
    # LCAM / Hazcams: the mast az/el in the metadata is not their pointing (LCAM has "UNK").
    lcam = [
        frame(i, 666952943.9 + 3.4 * i, instrument="LCAM", seq="LVS", az=None, el=None)
        for i in range(4)
    ]
    assert build_sequence(lcam).kind == "vehicle_fixed"
    haz = [frame(i, 10.0 + i, instrument="FRONT_HAZCAM_LEFT_A", az=5.0 * i) for i in range(3)]
    assert build_sequence(haz).kind == "vehicle_fixed"


def test_identical_sclk_is_a_single_exposure() -> None:
    seq = build_sequence([frame(i, 773571684.369) for i in range(3)])
    assert seq.kind == "single_exposure"
    assert seq.duration_s == 0


def test_mast_camera_without_pointing_is_unclassified() -> None:
    seq = build_sequence([frame(i, 10.0 + i, instrument="MCZ_LEFT", az=None) for i in range(3)])
    assert seq.kind == "unclassified"


def test_missing_sclk_frames_go_last_and_are_noted() -> None:
    seq = build_sequence([frame(1, None), frame(2, 50.0), frame(3, 10.0)])
    assert [f.meta.image_id for f in seq.frames] == ["IMG_003", "IMG_002", "IMG_001"]
    assert seq.frames[-1].t_offset_s is None
    assert any("no SCLK" in n for n in seq.notes)


def test_grouping_by_sol_instrument_and_sequence() -> None:
    frames = [
        *(frame(i, 100.0 + i) for i in range(3)),
        *(frame(10 + i, 50.0 + i, seq="NCAM00518") for i in range(2)),
        frame(20, 10.0, instrument="NAVCAM_RIGHT"),
        *(frame(30 + i, 5.0 + i, sol=1, seq=None) for i in range(3)),
    ]
    groups = group_sequences(frames, min_frames=2)
    assert [g.id for g in groups] == [
        "1-NAVCAM_LEFT-NOSEQ",
        "2024-NAVCAM_LEFT-NCAM00518",
        "2024-NAVCAM_LEFT-NCAM00520",
    ]
    assert [g.frame_count for g in group_sequences(frames, min_frames=3)] == [3, 3]


@pytest.mark.parametrize(
    ("sol", "instrument", "seq"),
    [(0, "LCAM", "LVS"), (2024, "FRONT_HAZCAM_LEFT_A", "FHAZ02008"), (1, "NAVCAM_LEFT", None)],
)
def test_sequence_key_round_trip(sol: int, instrument: str, seq: str | None) -> None:
    assert parse_sequence_key(sequence_key(sol, instrument, seq)) == (sol, instrument, seq)


@pytest.mark.parametrize("bad", ["", "abc", "x-NAVCAM-1", "12-", "12--SEQ"])
def test_bad_sequence_keys(bad: str) -> None:
    assert parse_sequence_key(bad) is None


@pytest.mark.parametrize(
    ("text", "hours"),
    [
        ("16:20:47", 16 + 20 / 60 + 47 / 3600),
        ("Sol-02022M16:20:47.500", 16 + 20 / 60 + 47.5 / 3600),
        ("00:00:00", 0.0),
        (None, None),
        ("", None),
        ("UNK", None),
        ("25:61:00", None),
    ],
)
def test_lmst_parsing(text: str | None, hours: float | None) -> None:
    result = lmst_hours(text)
    assert result == (pytest.approx(hours) if hours is not None else None)


def test_sclk_to_lmst_calibration() -> None:
    # Two images one LMST hour apart in SCLK, plus a small residual on the third.
    base = 846456111.143
    pairs = [
        (base, 16.0),
        (base + SECONDS_PER_LMST_HOUR, 17.0),
        (base + 2 * SECONDS_PER_LMST_HOUR, 18.0 + 1 / 3600),
    ]
    cal = calibrate(pairs)
    assert cal is not None
    assert cal.samples == 3
    assert cal.to_lmst(base + 0.5 * SECONDS_PER_LMST_HOUR) == pytest.approx(16.5, abs=1e-6)
    assert cal.max_residual_s == pytest.approx(1.0, abs=0.05)
    assert calibrate([]) is None


def test_official_videos_are_https_and_percent_encoded() -> None:
    assert len(OFFICIAL_VIDEOS) == 3
    for video in OFFICIAL_VIDEOS:
        for url in (video.video_url, video.poster_url, video.page_url):
            assert url.startswith("https://")
            assert " " not in url and "’" not in url
        assert video.video_url.endswith("~medium.mp4")
        assert video.credit.startswith("NASA/JPL-Caltech")
    assert "%E2%80%99" in OFFICIAL_VIDEOS[0].video_url  # the typographic apostrophe
