from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import agpp.pipelines.inventory.service as service
from agpp.pipelines.inventory.config import InventoryConfig
from agpp.pipelines.inventory.extraction import InventoryExtraction
from agpp.pipelines.inventory.loading import LoadResult, RunStatus
from agpp.pipelines.inventory.transformation import TransformedInventory
from agpp.pipelines.inventory.validation import ValidationResult
from agpp.shared.exceptions import (
    AgppError,
    InvalidSnapshotError,
    SourceUnavailableError,
    TransformationError,
    WarehouseWriteError,
)

NOW = datetime(2026, 11, 14, 7, 0, tzinfo=UTC)
LOADED = LoadResult(10, 8, 2, 1, 1, 3, 0)
STAGES = ["start", "extract", "validate", "transform", "load"]
POOL: Any = object()


def _config() -> InventoryConfig:
    return InventoryConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "max_snapshot_age_hours": 26,
                "future_tolerance_minutes": 5,
            },
            "source": {"type": "api", "base_url": "https://stock.test", "path": "/v1/stock"},
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

    extraction = InventoryExtraction("feed", "2026-11-14T06:00:00Z", 1, (), ())
    validation = ValidationResult(
        source_id="feed", snapshot_at=NOW, rows_read=0, valid=(), rejected=()
    )
    transformed = TransformedInventory(snapshot_at=NOW, date_key=20261114, locations=(), rows=())
    monkeypatch.setattr(service, "start_run", step("start"))
    monkeypatch.setattr(service, "extract_inventory", step("extract", extraction))
    monkeypatch.setattr(service, "validate_inventory", step("validate", validation))
    monkeypatch.setattr(service, "transform_inventory", step("transform", transformed))
    monkeypatch.setattr(service, "load_inventory", step("load", LOADED))
    monkeypatch.setattr(service, "record_failure", record_failure)
    monkeypatch.setattr(service, "finish_run", finish_run)


def test_the_stages_run_in_order_and_the_run_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _install(monkeypatch, calls)

    summary = service.run_inventory(POOL, _config(), run_id="run-1", now=NOW)

    assert calls == [*STAGES, "finish:succeeded"]
    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load == LOADED
    assert summary.error is None


@pytest.mark.parametrize(
    ("stage", "error"),
    [
        ("extract", SourceUnavailableError("feed offline")),
        ("validate", InvalidSnapshotError("snapshot too old")),
        ("transform", TransformationError("duplicate item")),
        ("load", WarehouseWriteError("disk full")),
    ],
)
def test_a_failing_stage_is_recorded_and_stops_the_run(
    monkeypatch: pytest.MonkeyPatch, stage: str, error: AgppError
) -> None:
    calls: list[str] = []
    _install(monkeypatch, calls, fail_at=stage, error=error)

    summary = service.run_inventory(POOL, _config(), run_id="run-1", now=NOW)

    reached = STAGES[: STAGES.index(stage) + 1]
    assert calls == [*reached, f"failure:{error.stage}", "finish:failed"]
    assert summary.status is RunStatus.FAILED
    assert summary.error is error
    assert summary.load is None


def test_an_unexpected_error_marks_the_run_failed_and_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    _install(monkeypatch, calls, fail_at="transform", error=RuntimeError("bug"))

    with pytest.raises(RuntimeError, match="bug"):
        service.run_inventory(POOL, _config(), run_id="run-1", now=NOW)

    assert calls == ["start", "extract", "validate", "transform", "finish:failed"]


def test_the_http_client_and_sleep_are_passed_to_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    _install(monkeypatch, [])

    def extract(_config: object, **kwargs: Any) -> InventoryExtraction:
        seen.update(kwargs)
        return InventoryExtraction("feed", "2026-11-14T06:00:00Z", 1, (), ())

    monkeypatch.setattr(service, "extract_inventory", extract)
    client: Any = object()
    sleeper = lambda _seconds: None  # noqa: E731

    service.run_inventory(POOL, _config(), run_id="run-1", now=NOW, sleep=sleeper, client=client)

    assert seen["client"] is client
    assert seen["sleep"] is sleeper
    assert seen["run_id"] == "run-1"


def test_a_config_path_is_not_needed(tmp_path: Path) -> None:
    assert not (tmp_path / "unused").exists()
