from datetime import UTC, date, datetime

import pytest
from src.shared.dates import (
    InvalidTimeZoneError,
    NaiveDateTimeError,
    convert_timezone,
    ensure_aware,
    ensure_utc,
    is_date,
    timezone_from_name,
    to_utc,
    utc_now,
)


class TestUtcNow:
    def test_returns_timezone_aware_datetime(self) -> None:
        result = utc_now()

        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.utcoffset() == UTC.utcoffset(result)

    def test_returns_utc_datetime(self) -> None:
        result = utc_now()

        assert result.tzinfo == UTC


class TestEnsureAware:
    def test_accepts_timezone_aware_datetime(self) -> None:
        value = datetime(2026, 8, 12, 10, 30, tzinfo=UTC)

        result = ensure_aware(value)
        assert result == value

    def test_rejects_naive_datetime(self) -> None:
        value = datetime(
            2026,
            8,
            12,
            10,
            30,
        )

        with pytest.raises(NaiveDateTimeError):
            ensure_aware(value)


class TestToUtc:
    def test_converts_positive_offset_to_utc(self) -> None:
        value = datetime.fromisoformat("2026-08-12T10:00:00+08:00")

        result = to_utc(value)

        assert result == datetime(2026, 8, 12, 2, 0, tzinfo=UTC)

    def test_converts_negative_offset_to_utc(self) -> None:
        value = datetime.fromisoformat("2026-08-12T10:00:00-04:00")
        result = to_utc(value)

        assert result == datetime(2026, 8, 12, 14, 0, tzinfo=UTC)

    def test_rejects_naive_datetime(self) -> None:
        value = datetime(
            2026,
            8,
            12,
            10,
            30,
        )

        with pytest.raises(NaiveDateTimeError):
            to_utc(value)

    def test_timezone_conversion_handles_dst(self) -> None:
        value = datetime.fromisoformat("2026-07-01T12:00:00+00:00")

        result = convert_timezone(
            value,
            "Europe/Luxembourg",
        )

        assert result.hour == 14
        assert result.utcoffset().total_seconds() == 2 * 60 * 60


class TestEnsureUtc:
    def test_normalizes_aware_datetime_to_utc(self) -> None:
        value = datetime.fromisoformat("2026-08-12T10:00:00+08:00")

        result = ensure_utc(value)

        assert result == datetime(
            2026,
            8,
            12,
            2,
            0,
            tzinfo=UTC,
        )

    def test_rejects_naive_datetime(self) -> None:
        value = datetime(
            2026,
            8,
            12,
            10,
            30,
        )

        with pytest.raises(NaiveDateTimeError):
            ensure_utc(value)


class TestTimezone:
    def test_resolves_valid_iana_timezone(self) -> None:
        result = timezone_from_name("Europe/Luxembourg")

        assert result.key == "Europe/Luxembourg"

    def test_rejects_invalid_timezone(self) -> None:
        with pytest.raises(InvalidTimeZoneError):
            timezone_from_name("Not/A/Real/Timezone")


class TestConvertTimezone:
    def test_converts_timezone(self) -> None:
        value = datetime.fromisoformat("2026-08-12T10:00:00+00:00")

        result = convert_timezone(
            value,
            "Europe/Luxembourg",
        )

        assert result.tzinfo is not None
        assert result.hour == 12

    def test_preserves_same_instant_when_converting_timezone(self) -> None:
        value = datetime.fromisoformat("2026-08-12T10:00:00+00:00")

        result = convert_timezone(
            value,
            "Asia/Shanghai",
        )

        assert result.utcoffset().total_seconds() == 8 * 60 * 60
        assert result.astimezone(UTC) == value

    def test_rejects_naive_datetime(self) -> None:
        value = datetime(
            2026,
            8,
            12,
            10,
            30,
        )

        with pytest.raises(NaiveDateTimeError):
            convert_timezone(
                value,
                "Europe/Luxembourg",
            )


class TestIsDate:
    def test_returns_true_for_date(self) -> None:
        value = date(2026, 8, 12)

        assert is_date(value)

    def test_returns_false_for_datetime(self) -> None:
        value = datetime(
            2026,
            8,
            12,
            10,
            30,
        )

        assert not is_date(value)

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "2026-08-12",
            20260812,
        ],
    )
    def test_returns_false_for_non_date_values(self, value) -> None:
        assert not is_date(value)
