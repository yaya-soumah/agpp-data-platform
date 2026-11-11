from agpp.shared.dates.calendar import FIRST_DATE, LAST_DATE
from agpp.shared.dates.datetime_utils import date_key


def test_the_calendar_matches_the_date_dimension_migration() -> None:
    assert date_key(FIRST_DATE) == 20000101
    assert date_key(LAST_DATE) == 20491231
