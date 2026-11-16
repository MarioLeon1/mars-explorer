from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from mars_explorer.ingest.parse import (
    ParseError,
    parse_lmst,
    parse_raw_image,
    parse_sequence_id,
    to_float,
    to_int,
    to_tuple,
    to_utc,
)
from tests.conftest import all_feed_records


@pytest.mark.parametrize("value", ["UNK", "unk", "", "  ", None, "N/A"])
def test_unknown_values_become_none(value: object) -> None:
    assert to_float(value) is None
    assert to_tuple(value) is None


def test_numeric_and_tuple_strings() -> None:
    assert to_float("-90.4883") == pytest.approx(-90.4883)
    assert to_int("0") == 0
    assert to_int("1.5") is None
    assert to_tuple("(0.682313,0.00347943,0.0627555,0.728354)") == pytest.approx(
        [0.682313, 0.00347943, 0.0627555, 0.728354]
    )
    assert to_tuple("(1,UNK,3)") is None


def test_naive_feed_timestamps_are_utc() -> None:
    parsed = to_utc("2026-10-30T08:44:57.868")
    assert parsed == datetime(2026, 10, 30, 8, 44, 57, 868000, tzinfo=UTC)
    assert to_utc("2026-10-30T11:56:00Z") == datetime(2026, 10, 30, 11, 56, tzinfo=UTC)
    assert to_utc("not a date") is None


def test_lmst_and_sequence_id() -> None:
    assert parse_lmst("Sol-02024M12:35:01.653") == "12:35:01"
    assert parse_lmst("garbage") is None
    assert parse_sequence_id("NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J") == "NCAM00518"
    assert parse_sequence_id("too_short") is None


@pytest.mark.parametrize("raw", all_feed_records(), ids=lambda r: r["imageid"][:30])
def test_every_real_fixture_record_parses(raw: dict) -> None:
    image = parse_raw_image(raw)
    assert image.image_id == raw["imageid"]
    assert image.sol == raw["sol"]
    assert image.instrument == raw["camera"]["instrument"]
    assert image.camera_group != "other"
    assert image.date_taken_utc is not None and image.date_taken_utc.tzinfo is not None
    assert image.lmst is not None
    assert image.url_large and image.url_large.endswith("_1200.jpg")
    assert json.loads(image.raw_json) == raw  # original record preserved verbatim
    assert image.width and image.height


def test_navcam_record_details() -> None:
    raw = next(r for r in all_feed_records() if r["camera"]["instrument"] == "NAVCAM_LEFT")
    image = parse_raw_image(raw)
    assert image.camera_group == "navcam"
    assert image.filter_name is None  # "UNK" in the feed
    assert image.scale_factor == 4.0
    assert image.subframe_rect == [1, 1, 5120, 3840]
    assert (image.width, image.height) == (1280, 960)
    assert image.attitude_quaternion is not None and len(image.attitude_quaternion) == 4
    assert image.camera_model_type == "CAHVORE"


def test_missing_identity_fields_raise() -> None:
    with pytest.raises(ParseError):
        parse_raw_image({"sol": 1, "camera": {"instrument": "NAVCAM_LEFT"}})
