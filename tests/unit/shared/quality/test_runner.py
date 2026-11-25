from typing import Any

import pytest

import agpp.shared.quality.runner as runner
from agpp.shared.exceptions import WarehouseWriteError
from agpp.shared.quality import CheckStatus, QualityCheck, QualityConfig, run_checks

POOL: Any = object()


def _config(*names: str) -> QualityConfig:
    return QualityConfig.model_validate(
        {
            "checks": [
                {"name": name, "description": "d", "sql": "SELECT 1", "warn": 0.1, "fail": 0.2}
                for name in names
            ]
        }
    )


def test_each_check_is_measured_and_evaluated(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {"ok": 0.0, "warned": 0.15, "broken": 0.5, "empty": None}
    monkeypatch.setattr(runner, "measure", lambda _pool, check: values[check.name])

    results = run_checks(POOL, _config(*values))

    assert [(r.check.name, r.status) for r in results] == [
        ("ok", CheckStatus.PASS),
        ("warned", CheckStatus.WARN),
        ("broken", CheckStatus.FAIL),
        ("empty", CheckStatus.NO_DATA),
    ]
    assert results[1].value == 0.15


@pytest.mark.parametrize(
    "error", [WarehouseWriteError("disk full"), ValueError("not a number"), TypeError("bad")]
)
def test_a_check_that_cannot_run_is_an_error_and_the_others_continue(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def measure(_pool: object, check: QualityCheck) -> float:
        if check.name == "first":
            raise error
        return 0.0

    monkeypatch.setattr(runner, "measure", measure)

    results = run_checks(POOL, _config("first", "second"))

    assert [r.status for r in results] == [CheckStatus.ERROR, CheckStatus.PASS]
    assert results[0].value is None
    assert results[0].message == str(error)
