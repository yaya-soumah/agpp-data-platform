from typing import Any, LiteralString

from agpp.shared.database import Pool, connection
from agpp.shared.quality import CheckStatus, QualityConfig, run_checks, run_quality_checks


def _config(*checks: tuple[str, str]) -> QualityConfig:
    return QualityConfig.model_validate(
        {
            "checks": [
                {
                    "name": name,
                    "description": "d",
                    "sql": sql,
                    "comparison": "max",
                    "warn": 0.1,
                    "fail": 0.5,
                }
                for name, sql in checks
            ]
        }
    )


def _scalar(pool: Pool, query: LiteralString) -> Any:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


def test_the_value_of_a_check_is_measured_and_evaluated(warehouse: Pool) -> None:
    results = run_checks(warehouse, _config(("quarter", "SELECT 0.25::double precision")))

    assert results[0].value == 0.25
    assert results[0].status is CheckStatus.WARN


def test_an_integer_result_becomes_a_number(warehouse: Pool) -> None:
    results = run_checks(warehouse, _config(("three", "SELECT 3")))

    assert results[0].value == 3.0
    assert results[0].status is CheckStatus.FAIL


def test_a_query_without_rows_or_with_null_is_no_data(warehouse: Pool) -> None:
    results = run_checks(
        warehouse,
        _config(("no_row", "SELECT 1 WHERE false"), ("null_value", "SELECT NULL::numeric")),
    )

    assert [r.status for r in results] == [CheckStatus.NO_DATA, CheckStatus.NO_DATA]


def test_a_broken_query_is_an_error_and_the_others_still_run(warehouse: Pool) -> None:
    results = run_checks(warehouse, _config(("broken", "SELEC 1"), ("fine", "SELECT 0")))

    assert [r.status for r in results] == [CheckStatus.ERROR, CheckStatus.PASS]
    assert results[0].message


def test_a_check_cannot_write(warehouse: Pool) -> None:
    results = run_checks(
        warehouse,
        _config(
            (
                "writer",
                "INSERT INTO operational.quality_check_results"
                " (run_id, check_name, status, warn_threshold, fail_threshold, comparison)"
                " VALUES ('x', 'y', 'pass', 1, 2, 'max') RETURNING 1",
            )
        ),
    )

    assert results[0].status is CheckStatus.ERROR
    assert _scalar(warehouse, "SELECT count(*) FROM operational.quality_check_results") == 0


def test_results_are_stored_per_run(warehouse: Pool) -> None:
    config = _config(("quarter", "SELECT 0.25"), ("zero", "SELECT 0"))

    first = run_quality_checks(warehouse, config, run_id="run-1")
    run_quality_checks(warehouse, config, run_id="run-2")

    assert not first.failed
    assert _scalar(warehouse, "SELECT count(*) FROM operational.quality_check_results") == 4
    assert (
        _scalar(
            warehouse,
            "SELECT status FROM operational.quality_check_results"
            " WHERE run_id = 'run-1' AND check_name = 'quarter'",
        )
        == "warn"
    )
