"""Feed-level check of the snapshot time (ADR-0018)."""

from datetime import datetime, timedelta

from agpp.pipelines.inventory.config import QualityConfig
from agpp.shared.dates.datetime_utils import parse_iso_datetime
from agpp.shared.exceptions import InvalidSnapshotError


def check_snapshot(snapshot_at: str, quality: QualityConfig, *, now: datetime) -> datetime:
    """Parse the snapshot time and check it is neither too old nor in the future.

    ``now`` must be timezone-aware. Returns the snapshot time in UTC.
    """
    try:
        parsed = parse_iso_datetime(snapshot_at)
    except ValueError as error:
        raise InvalidSnapshotError(
            "snapshot_at must be an ISO 8601 timestamp with an offset",
            context={"snapshot_at": snapshot_at[:50]},
        ) from error

    age = now - parsed
    if age > timedelta(hours=quality.max_snapshot_age_hours):
        raise InvalidSnapshotError(
            f"Snapshot is {age.total_seconds() / 3600:.1f} hours old,"
            f" above the allowed {quality.max_snapshot_age_hours}",
            context={
                "snapshot_at": parsed.isoformat(),
                "max_snapshot_age_hours": quality.max_snapshot_age_hours,
            },
        )
    if parsed > now + timedelta(minutes=quality.future_tolerance_minutes):
        raise InvalidSnapshotError(
            "Snapshot is in the future", context={"snapshot_at": parsed.isoformat()}
        )
    return parsed
