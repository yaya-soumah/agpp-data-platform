from __future__ import annotations

from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class DateTimeError(ValueError):
    """Base exception for date/time utility errors."""
    pass

class NaiveDateTimeError(DateTimeError):
    """Raised when a timezone-aware datetime is required."""
    pass 

class InvalidTimeZoneError(DateTimeError):
    """Raised when a timezone cannot be resolved."""
    pass

def utc_now() -> datetime:
    """"
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(timezone.utc)

def ensure_aware(value: datetime) -> datetime:
    """"
    Validate that a datetime is timezone-aware.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDateTimeError("A timezone-aware datetime is required.")
    return value

def to_utc(value: datetime) -> datetime:
    """"
    Convert a timezone-aware datetime to UTC.
    """

    value = ensure_aware(value)

    return value.astimezone(timezone.utc)

def timezone_from_name(name: str) -> ZoneInfo:
    """"
    Resolve an IANA timezone name.
    """

    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimeZoneError(f"Unknown IANA timezone: {name!r}") from exc

def convert_timezone(
        value: datetime,
        timezone_name: str,
    ) -> datetime:
    """"
    Convert a timezone-aware datetime to the requested IANA timezone
    """

    value = ensure_aware(value)
    target_timezone = timezone_from_name(timezone_name)

    return value.astimezone(target_timezone)

def ensure_utc(value: datetime) -> datetime:
    """
    Validate that a datetime is timezone-aware and normalized to UTC."""

    normalized = to_utc(value)

    if normalized.tzinfo != timezone.utc:
        raise DateTimeError("Datetime could not be normalized to UTC.")

    return normalized

def is_date(value: object) -> bool:
    """
    Return True if the value is a date but not a datetime object.
    """

    return isinstance(value, date) and not isinstance(value, datetime)