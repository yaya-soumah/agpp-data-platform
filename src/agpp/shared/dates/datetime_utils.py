"""UTC-aware datetime helpers. Naive datetimes are never guessed."""

from datetime import UTC, date, datetime, tzinfo


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def to_utc(value: datetime, assume_tz: tzinfo | None = None) -> datetime:
    """Convert a datetime to UTC.

    A naive datetime needs ``assume_tz`` to say which timezone it is in;
    otherwise ``ValueError`` is raised rather than guessing.
    """
    if value.utcoffset() is None:
        if assume_tz is None:
            raise ValueError("Naive datetime: pass assume_tz to say which timezone it is in")
        value = value.replace(tzinfo=assume_tz)
    return value.astimezone(UTC)


def parse_iso_datetime(text: str, assume_tz: tzinfo | None = None) -> datetime:
    """Parse an ISO 8601 datetime (``Z`` is accepted) and convert it to UTC."""
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError as error:
        raise ValueError(f"Not an ISO 8601 datetime: {text!r}") from error
    return to_utc(parsed, assume_tz)


def date_key(value: date) -> int:
    """Return the ``YYYYMMDD`` integer key used by the date dimension."""
    return value.year * 10_000 + value.month * 100 + value.day


def from_date_key(key: int) -> date:
    """Inverse of ``date_key``."""
    year, remainder = divmod(key, 10_000)
    month, day = divmod(remainder, 100)
    try:
        return date(year, month, day)
    except ValueError as error:
        raise ValueError(f"Not a valid date key: {key}") from error
