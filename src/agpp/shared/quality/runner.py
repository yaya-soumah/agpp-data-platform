"""Run quality checks, each in its own read-only transaction (ADR-0020)."""

from dataclasses import dataclass
from typing import LiteralString, cast

import psycopg

from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import AgppError
from agpp.shared.quality.models import CheckStatus, QualityCheck, QualityConfig

MAX_MESSAGE_LENGTH = 300


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one check."""

    check: QualityCheck
    status: CheckStatus
    value: float | None = None
    message: str | None = None


def evaluate(check: QualityCheck, value: float | None) -> CheckStatus:
    """Compare a measured value with the thresholds of its check."""
    if value is None:
        return CheckStatus.NO_DATA
    sign = 1.0 if check.comparison == "max" else -1.0
    if sign * value > sign * check.fail:
        return CheckStatus.FAIL
    if sign * value > sign * check.warn:
        return CheckStatus.WARN
    return CheckStatus.PASS


def measure(pool: Pool, check: QualityCheck) -> float | None:
    """Run the query of a check and return its single number, or None for no data.

    The query is configuration (trusted); the read-only transaction and the timeout
    protect against mistakes, not against a hostile author.
    """
    with connection(pool) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '30s'")
        row = conn.execute(cast(LiteralString, check.sql)).fetchone()  # type: ignore[redundant-cast]
    if row is None or row[0] is None:
        return None
    return float(row[0])


def run_checks(pool: Pool, config: QualityConfig) -> tuple[CheckResult, ...]:
    """Run every check. A check that cannot run is an ``error``; the others continue."""
    return tuple(_run_one(pool, check) for check in config.checks)


def _run_one(pool: Pool, check: QualityCheck) -> CheckResult:
    try:
        value = measure(pool, check)
    except (AgppError, psycopg.Error, ValueError, TypeError) as error:
        return CheckResult(check, CheckStatus.ERROR, message=_short(error))
    return CheckResult(check, evaluate(check, value), value)


def _short(error: Exception) -> str:
    lines = str(error).strip().splitlines()
    text = lines[0] if lines else type(error).__name__
    return text[:MAX_MESSAGE_LENGTH]
