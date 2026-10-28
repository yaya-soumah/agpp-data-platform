from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from agpp.shared.dates.datetime_utils import (
    date_key,
    from_date_key,
    parse_iso_datetime,
    to_utc,
    utc_now,
)

PLUS_TWO = timezone(timedelta(hours=2))
NOON_UTC = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


def test_utc_now_is_timezone_aware_utc() -> None:
    assert utc_now().tzinfo is UTC


def test_to_utc_converts_aware_values() -> None:
    value = datetime(2026, 10, 28, 12, 0, tzinfo=PLUS_TWO)

    assert to_utc(value) == NOON_UTC
    assert to_utc(value).utcoffset() == timedelta(0)


def test_to_utc_localizes_naive_values_with_assume_tz() -> None:
    assert to_utc(datetime(2026, 10, 28, 12, 0), PLUS_TWO) == NOON_UTC


def test_to_utc_rejects_naive_values_without_assume_tz() -> None:
    with pytest.raises(ValueError, match="Naive"):
        to_utc(datetime(2026, 10, 28, 12, 0))


def test_parse_accepts_z_suffix() -> None:
    assert parse_iso_datetime("2026-10-28T10:00:00Z") == NOON_UTC


def test_parse_accepts_offsets() -> None:
    assert parse_iso_datetime("2026-10-28T12:00:00+02:00") == NOON_UTC


def test_parse_naive_text_uses_assume_tz() -> None:
    assert parse_iso_datetime("2026-10-28T12:00:00", PLUS_TWO) == NOON_UTC


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="ISO 8601"):
        parse_iso_datetime("yesterday-ish")


def test_date_key_round_trip() -> None:
    assert date_key(date(2026, 10, 28)) == 20261028
    assert from_date_key(20261028) == date(2026, 10, 28)


def test_from_date_key_rejects_invalid_keys() -> None:
    with pytest.raises(ValueError, match="date key"):
        from_date_key(20261340)
