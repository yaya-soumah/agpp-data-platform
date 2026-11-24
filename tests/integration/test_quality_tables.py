from typing import LiteralString

import psycopg
import pytest

from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import AgppError

INSERT: LiteralString = (
    "INSERT INTO operational.quality_check_results"
    " (run_id, check_name, status, value, warn_threshold, fail_threshold, comparison)"
    " VALUES (%s, %s, %s, %s, 1.0, 2.0, %s)"
)
REJECTED = (AgppError, psycopg.Error)


def _insert(
    pool: Pool,
    run_id: str = "run-1",
    name: str = "a_check",
    status: str = "pass",
    value: float | None = 0.5,
    comparison: str = "max",
) -> None:
    with connection(pool) as conn:
        conn.execute(INSERT, (run_id, name, status, value, comparison))


def _count(pool: Pool) -> int:
    with connection(pool) as conn:
        row = conn.execute("SELECT count(*) FROM operational.quality_check_results").fetchone()
    assert row is not None
    return int(row[0])


def test_a_result_can_be_stored(warehouse: Pool) -> None:
    _insert(warehouse)

    assert _count(warehouse) == 1


def test_a_result_without_a_value_can_be_stored(warehouse: Pool) -> None:
    _insert(warehouse, status="no_data", value=None)

    assert _count(warehouse) == 1


def test_an_unknown_status_is_rejected(warehouse: Pool) -> None:
    with pytest.raises(REJECTED):
        _insert(warehouse, status="great")

    assert _count(warehouse) == 0


def test_an_unknown_comparison_is_rejected(warehouse: Pool) -> None:
    with pytest.raises(REJECTED):
        _insert(warehouse, comparison="avg")


def test_a_check_is_stored_once_per_run(warehouse: Pool) -> None:
    _insert(warehouse)

    with pytest.raises(REJECTED):
        _insert(warehouse)

    _insert(warehouse, run_id="run-2")
    assert _count(warehouse) == 2
