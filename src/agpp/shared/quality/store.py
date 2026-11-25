"""Persist quality check results (ADR-0020)."""

from collections.abc import Sequence
from typing import LiteralString

from agpp.shared.database import Pool, connection
from agpp.shared.quality.runner import CheckResult

_INSERT: LiteralString = (
    "INSERT INTO operational.quality_check_results"
    " (run_id, check_name, status, value, warn_threshold, fail_threshold, comparison, message)"
    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
)


def store_results(pool: Pool, run_id: str, results: Sequence[CheckResult]) -> None:
    """Store one row per check, all in one transaction."""
    with connection(pool) as conn:
        for result in results:
            check = result.check
            conn.execute(
                _INSERT,
                (
                    run_id,
                    check.name,
                    result.status.value,
                    result.value,
                    check.warn,
                    check.fail,
                    check.comparison,
                    result.message,
                ),
            )
