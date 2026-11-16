from datetime import UTC, datetime, timedelta

import pytest

from agpp.pipelines.inventory.config import QualityConfig
from agpp.pipelines.inventory.validation.snapshot import check_snapshot
from agpp.shared.exceptions import InvalidSnapshotError

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
QUALITY = QualityConfig(
    max_reject_ratio=0.05, max_snapshot_age_hours=26, future_tolerance_minutes=5
)


def test_a_fresh_snapshot_is_returned_in_utc() -> None:
    parsed = check_snapshot("2026-11-13T07:00:00+01:00", QUALITY, now=NOW)

    assert parsed == datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
    assert parsed.tzinfo is UTC


def test_the_oldest_allowed_snapshot_passes_but_older_ones_fail() -> None:
    oldest = (NOW - timedelta(hours=26)).isoformat()
    too_old = (NOW - timedelta(hours=26, minutes=1)).isoformat()

    check_snapshot(oldest, QUALITY, now=NOW)
    with pytest.raises(InvalidSnapshotError, match="hours old"):
        check_snapshot(too_old, QUALITY, now=NOW)


def test_a_little_clock_skew_is_tolerated_but_the_future_is_not() -> None:
    within = (NOW + timedelta(minutes=4)).isoformat()
    beyond = (NOW + timedelta(minutes=6)).isoformat()

    check_snapshot(within, QUALITY, now=NOW)
    with pytest.raises(InvalidSnapshotError, match="in the future"):
        check_snapshot(beyond, QUALITY, now=NOW)


@pytest.mark.parametrize("text", ["yesterday", "2026-11-13T06:00:00", "", "2026-13-45"])
def test_an_unreadable_or_naive_snapshot_is_rejected(text: str) -> None:
    with pytest.raises(InvalidSnapshotError, match="ISO 8601"):
        check_snapshot(text, QUALITY, now=NOW)


def test_the_error_is_not_retryable_and_carries_context() -> None:
    with pytest.raises(InvalidSnapshotError) as info:
        check_snapshot("2026-11-01T06:00:00Z", QUALITY, now=NOW)

    assert info.value.retryable is False
    assert info.value.context["max_snapshot_age_hours"] == 26
