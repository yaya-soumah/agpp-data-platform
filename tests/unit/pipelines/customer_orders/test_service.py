from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import agpp.pipelines.customer_orders.service as service
from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.loading import LoadResult, RunStatus
from agpp.pipelines.customer_orders.transformation import TransformedOrders
from agpp.pipelines.customer_orders.validation import ValidationResult
from agpp.shared.exceptions import (
    AgppError,
    SchemaValidationError,
    SourceUnavailableError,
    TransformationError,
    WarehouseWriteError,
)
from agpp.shared.extraction import CsvContent

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
LOADED = LoadResult(10, 8, 2, 1, 1, 3)
STAGES = ["start", "extract", "validate", "transform", "load"]
POOL: Any = object()


def _config(tmp_path: Path) -> CustomerOrdersConfig:
    return CustomerOrdersConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "allowed_currencies": ["EUR"],
                "max_line_amount": 1000,
                "future_tolerance_minutes": 5,
            },
            "source": {"type": "csv", "path": str(tmp_path / "orders.csv")},
        }
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[str],
    fail_at: str | None = None,
    error: Exception | None = None,
) -> None:
    def step(name: str, result: object = None) -> Any:
        def run(*_args: object, **_kwargs: object) -> object:
            calls.append(name)
            if name == fail_at and error is not None:
                raise error
            return result

        return run

    def record_failure(_pool: object, _run_id: str, failure: AgppError) -> None:
        calls.append(f"failure:{failure.stage}")

    def finish_run(_pool: object, _run_id: str, status: RunStatus) -> None:
        calls.append(f"finish:{status.value}")

    validation = ValidationResult("orders.csv", 0, (), ())
    monkeypatch.setattr(service, "start_run", step("start"))
    monkeypatch.setattr(service, "extract_orders", step("extract", CsvContent((), ())))
    monkeypatch.setattr(service, "validate_orders", step("validate", validation))
    monkeypatch.setattr(service, "transform_orders", step("transform", TransformedOrders((), ())))
    monkeypatch.setattr(service, "load_orders", step("load", LOADED))
    monkeypatch.setattr(service, "record_failure", record_failure)
    monkeypatch.setattr(service, "finish_run", finish_run)


def test_the_stages_run_in_order_and_the_run_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _install(monkeypatch, calls)

    summary = service.run_customer_orders(POOL, _config(tmp_path), run_id="run-1", now=NOW)

    assert calls == [*STAGES, "finish:succeeded"]
    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load == LOADED
    assert summary.error is None


@pytest.mark.parametrize(
    ("stage", "error"),
    [
        ("extract", SourceUnavailableError("share offline")),
        ("validate", SchemaValidationError("missing columns")),
        ("transform", TransformationError("duplicate line")),
        ("load", WarehouseWriteError("disk full")),
    ],
)
def test_a_failing_stage_is_recorded_and_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, error: AgppError
) -> None:
    calls: list[str] = []
    _install(monkeypatch, calls, fail_at=stage, error=error)

    summary = service.run_customer_orders(POOL, _config(tmp_path), run_id="run-1", now=NOW)

    reached = STAGES[: STAGES.index(stage) + 1]
    assert calls == [*reached, f"failure:{error.stage}", "finish:failed"]
    assert summary.status is RunStatus.FAILED
    assert summary.error is error
    assert summary.load is None


def test_an_unexpected_error_marks_the_run_failed_and_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _install(monkeypatch, calls, fail_at="transform", error=RuntimeError("bug"))

    with pytest.raises(RuntimeError, match="bug"):
        service.run_customer_orders(POOL, _config(tmp_path), run_id="run-1", now=NOW)

    assert calls == ["start", "extract", "validate", "transform", "finish:failed"]


def test_the_source_path_is_used_as_the_source_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    _install(monkeypatch, [])

    def validate(content: object, source_id: str, *_args: object, **_kwargs: object) -> object:
        seen["source_id"] = source_id
        return ValidationResult(source_id, 0, (), ())

    monkeypatch.setattr(service, "validate_orders", validate)
    config = _config(tmp_path)

    service.run_customer_orders(POOL, config, run_id="run-1", now=NOW)

    assert seen["source_id"] == config.source.path
