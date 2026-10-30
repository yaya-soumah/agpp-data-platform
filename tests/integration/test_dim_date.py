from datetime import date
from pathlib import Path

import pytest

from agpp.shared.database import Pool, connection
from agpp.shared.database.migrations import apply_migrations
from agpp.shared.dates.datetime_utils import date_key

FIRST_DAY = date(2000, 1, 1)
LAST_DAY = date(2049, 12, 31)


@pytest.fixture
def migrated(scratch_pool: Pool, project_root: Path) -> Pool:
    apply_migrations(scratch_pool, project_root / "sql" / "migrations")
    return scratch_pool


def test_dim_date_covers_every_day_once(migrated: Pool) -> None:
    with connection(migrated) as conn:
        row = conn.execute(
            "SELECT count(*), min(full_date), max(full_date) FROM warehouse.dim_date"
        ).fetchone()

    assert row == ((LAST_DAY - FIRST_DAY).days + 1, FIRST_DAY, LAST_DAY)


def test_date_keys_match_the_python_helper(migrated: Pool) -> None:
    with connection(migrated) as conn:
        rows = conn.execute("SELECT date_key, full_date FROM warehouse.dim_date").fetchall()

    assert all(key == date_key(day) for key, day in rows)


def test_calendar_attributes_of_a_known_day(migrated: Pool) -> None:
    with connection(migrated) as conn:
        row = conn.execute(
            "SELECT year, quarter, month, month_name, day_of_month, iso_day_of_week,"
            " day_name, iso_week, is_weekend FROM warehouse.dim_date WHERE full_date = %s",
            (date(2026, 10, 29),),
        ).fetchone()

    assert row == (2026, 4, 10, "October", 29, 4, "Thursday", 44, False)


def test_weekends_and_leap_days(migrated: Pool) -> None:
    with connection(migrated) as conn:
        saturday = conn.execute(
            "SELECT is_weekend FROM warehouse.dim_date WHERE full_date = %s",
            (date(2026, 10, 31),),
        ).fetchone()
        leap_day = conn.execute(
            "SELECT count(*) FROM warehouse.dim_date WHERE full_date = %s",
            (date(2028, 2, 29),),
        ).fetchone()

    assert saturday == (True,)
    assert leap_day == (1,)
