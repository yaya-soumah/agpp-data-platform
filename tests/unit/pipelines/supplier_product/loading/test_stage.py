import logging
from pathlib import Path
from typing import Any

import pytest

from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.loading import LoadResult, load_all
from agpp.pipelines.supplier_product.transformation import (
    SupplierRow,
    SupplierTransformation,
    TransformedBatch,
)
from agpp.pipelines.supplier_product.validation import SupplierValidation, ValidationResult
from agpp.shared.database import Pool
from agpp.shared.exceptions import QualityThresholdExceededError, WarehouseWriteError


def _config(directory: Path) -> SupplierProductConfig:
    def supplier(number: str) -> dict[str, object]:
        return {
            "supplier_id": f"SUP-{number}",
            "name": f"Supplier {number}",
            "country": "LU",
            "source": {"type": "csv", "path": str(directory / f"{number}.csv")},
        }

    return SupplierProductConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.1,
                "allowed_currencies": ["EUR"],
                "max_unit_price": 1000,
                "future_tolerance_minutes": 5,
            },
            "loading": {"max_attempts": 2, "initial_delay_seconds": 0.25},
            "suppliers": [supplier("001"), supplier("002")],
        }
    )


def _transformation(supplier_id: str) -> SupplierTransformation:
    batch = TransformedBatch(
        SupplierRow(supplier_id=supplier_id, supplier_name="N", country="LU"), ()
    )
    return SupplierTransformation(supplier_id, batch=batch)


def _validation(supplier_id: str) -> SupplierValidation:
    return SupplierValidation(supplier_id, result=ValidationResult(supplier_id, 0, (), ()))


class FakeLoader:
    def __init__(self, fail_for: str | None = None) -> None:
        self.fail_for = fail_for
        self.calls: list[dict[str, Any]] = []

    def __call__(self, pool: Pool, **kwargs: Any) -> LoadResult:
        batch = kwargs["batch"]
        supplier_id = batch.supplier.supplier_id
        self.calls.append(kwargs)
        if supplier_id == self.fail_for:
            raise WarehouseWriteError("disk full", context={"supplier_id": supplier_id})
        return LoadResult(supplier_id, 10, 4, 6, 1)


_POOL: Any = object()


def test_every_transformed_supplier_is_loaded(tmp_path: Path) -> None:
    loader = FakeLoader()

    outcomes = load_all(
        _POOL,
        _config(tmp_path),
        [_transformation("SUP-001"), _transformation("SUP-002")],
        [_validation("SUP-001"), _validation("SUP-002")],
        run_id="run-1",
        supplier_loader=loader,
    )

    assert all(outcome.succeeded for outcome in outcomes)
    assert outcomes[0].result == LoadResult("SUP-001", 10, 4, 6, 1)
    assert len(loader.calls) == 2


def test_the_retry_policy_comes_from_the_configuration(tmp_path: Path) -> None:
    loader = FakeLoader()

    load_all(
        _POOL,
        _config(tmp_path),
        [_transformation("SUP-001")],
        [_validation("SUP-001")],
        run_id="run-1",
        supplier_loader=loader,
    )

    policy = loader.calls[0]["retry_policy"]
    assert (policy.max_attempts, policy.initial_delay) == (2, 0.25)
    assert loader.calls[0]["run_id"] == "run-1"


def test_a_failing_supplier_does_not_stop_the_others(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    loader = FakeLoader(fail_for="SUP-001")

    with caplog.at_level(logging.INFO):
        outcomes = load_all(
            _POOL,
            _config(tmp_path),
            [_transformation("SUP-001"), _transformation("SUP-002")],
            [_validation("SUP-001"), _validation("SUP-002")],
            run_id="run-1",
            supplier_loader=loader,
        )

    assert [outcome.succeeded for outcome in outcomes] == [False, True]
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1


def test_earlier_errors_are_carried_through_without_loading(tmp_path: Path) -> None:
    gate = QualityThresholdExceededError("too many rejects")
    loader = FakeLoader()

    outcomes = load_all(
        _POOL,
        _config(tmp_path),
        [SupplierTransformation("SUP-001", error=gate), _transformation("SUP-002")],
        [SupplierValidation("SUP-001", error=gate), _validation("SUP-002")],
        run_id="run-1",
        supplier_loader=loader,
    )

    assert outcomes[0].error is gate
    assert len(loader.calls) == 1


def test_a_missing_validation_result_fails_that_supplier(tmp_path: Path) -> None:
    outcomes = load_all(
        _POOL,
        _config(tmp_path),
        [_transformation("SUP-001")],
        [],
        run_id="run-1",
        supplier_loader=FakeLoader(),
    )

    assert not outcomes[0].succeeded


def test_log_records_carry_the_run_context(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        load_all(
            _POOL,
            _config(tmp_path),
            [_transformation("SUP-001")],
            [_validation("SUP-001")],
            run_id="run-7",
            supplier_loader=FakeLoader(),
        )

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-7" for item in fields)
    assert "Loading finished" in caplog.text
