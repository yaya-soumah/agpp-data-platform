import logging
from typing import Any

import pytest

import agpp.shared.quality.service as service
from agpp.shared.quality import (
    CheckResult,
    CheckStatus,
    QualityCheck,
    QualityConfig,
    QualitySummary,
)

POOL: Any = object()


def _check(name: str) -> QualityCheck:
    return QualityCheck.model_validate(
        {"name": name, "description": "d", "sql": "SELECT 1", "warn": 0.1, "fail": 0.2}
    )


def _config() -> QualityConfig:
    return QualityConfig(checks=[_check("a_check")])


def _install(
    monkeypatch: pytest.MonkeyPatch, *statuses: CheckStatus
) -> list[tuple[str, tuple[CheckResult, ...]]]:
    results = tuple(CheckResult(_check(f"check_{i}"), s, 0.0) for i, s in enumerate(statuses))
    stored: list[tuple[str, tuple[CheckResult, ...]]] = []
    monkeypatch.setattr(service, "run_checks", lambda _pool, _config: results)
    monkeypatch.setattr(
        service, "store_results", lambda _pool, run_id, rs: stored.append((run_id, tuple(rs)))
    )
    return stored


def test_results_are_stored_under_the_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = _install(monkeypatch, CheckStatus.PASS, CheckStatus.WARN)

    summary = service.run_quality_checks(POOL, _config(), run_id="run-1")

    assert stored == [("run-1", summary.results)]
    assert summary.run_id == "run-1"


@pytest.mark.parametrize(
    ("statuses", "failed"),
    [
        ((CheckStatus.PASS, CheckStatus.WARN, CheckStatus.NO_DATA), False),
        ((CheckStatus.PASS, CheckStatus.FAIL), True),
        ((CheckStatus.ERROR,), True),
    ],
)
def test_a_failed_or_unrunnable_check_fails_the_summary(
    monkeypatch: pytest.MonkeyPatch, statuses: tuple[CheckStatus, ...], failed: bool
) -> None:
    _install(monkeypatch, *statuses)

    assert service.run_quality_checks(POOL, _config(), run_id="run-1").failed is failed


def test_outcomes_are_logged_at_their_level(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    _install(monkeypatch, CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL)

    service.run_quality_checks(POOL, _config(), run_id="run-1")

    levels = [record.levelno for record in caplog.records]
    assert logging.WARNING in levels
    assert logging.ERROR in levels


def test_counts_by_status() -> None:
    results = (
        CheckResult(_check("a_check"), CheckStatus.PASS, 0.0),
        CheckResult(_check("b_check"), CheckStatus.PASS, 0.0),
        CheckResult(_check("c_check"), CheckStatus.WARN, 0.2),
    )

    summary = QualitySummary("run-1", results)

    assert summary.count(CheckStatus.PASS) == 2
    assert summary.count(CheckStatus.WARN) == 1
    assert summary.count(CheckStatus.FAIL) == 0
