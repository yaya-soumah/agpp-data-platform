import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.extraction import extract_all
from agpp.pipelines.supplier_product.models import SupplierProduct
from agpp.pipelines.supplier_product.sample_data import generate_supplier_files
from agpp.pipelines.supplier_product.transformation import transform_all
from agpp.pipelines.supplier_product.validation import (
    SupplierValidation,
    ValidationResult,
    validate_all,
)
from agpp.shared.exceptions import QualityThresholdExceededError

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
VALUES = {
    "supplier_sku": "A-001",
    "product_name": "Hex Bolt",
    "category": "Fasteners",
    "unit_price": "10.00",
    "currency": "EUR",
    "lead_time_days": "5",
    "updated_at": "2026-11-04T10:00:00Z",
}


def _config(directory: Path) -> SupplierProductConfig:
    def supplier(number: str, delimiter: str) -> dict[str, object]:
        return {
            "supplier_id": f"SUP-{number}",
            "name": f"Supplier {number}",
            "country": "LU",
            "source": {
                "type": "csv",
                "path": str(directory / f"{number}.csv"),
                "delimiter": delimiter,
            },
        }

    return SupplierProductConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.1,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_unit_price": 1000000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "suppliers": [supplier("001", ","), supplier("002", ";")],
        }
    )


def _validation(supplier_id: str, skus: list[str]) -> SupplierValidation:
    products = tuple(
        SupplierProduct.model_validate({**VALUES, "supplier_id": supplier_id, "supplier_sku": sku})
        for sku in skus
    )
    result = ValidationResult(supplier_id, len(products), products, ())
    return SupplierValidation(supplier_id, result=result)


def test_every_validated_supplier_is_transformed(tmp_path: Path) -> None:
    validations = [_validation("SUP-001", ["A-1", "A-2"]), _validation("SUP-002", ["B-1"])]

    outcomes = transform_all(_config(tmp_path), validations, run_id="run-1")

    assert [outcome.supplier_id for outcome in outcomes] == ["SUP-001", "SUP-002"]
    assert all(outcome.succeeded for outcome in outcomes)
    assert outcomes[0].batch is not None
    assert [row.product_id for row in outcomes[0].batch.products] == ["SUP-001:A-1", "SUP-001:A-2"]


def test_earlier_errors_are_carried_through(tmp_path: Path) -> None:
    gate = QualityThresholdExceededError("too many rejects")
    validations = [SupplierValidation("SUP-001", error=gate), _validation("SUP-002", ["B-1"])]

    outcomes = transform_all(_config(tmp_path), validations, run_id="run-1")

    assert outcomes[0].error is gate
    assert outcomes[0].batch is None
    assert outcomes[1].succeeded


def test_an_unconfigured_supplier_fails_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    validations = [_validation("SUP-009", ["X-1"]), _validation("SUP-001", ["A-1"])]

    with caplog.at_level(logging.INFO):
        outcomes = transform_all(_config(tmp_path), validations, run_id="run-1")

    assert [outcome.succeeded for outcome in outcomes] == [False, True]
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1


def test_log_records_carry_the_run_context(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        transform_all(_config(tmp_path), [_validation("SUP-001", ["A-1"])], run_id="run-5")

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-5" for item in fields)
    assert "Transformation finished" in caplog.text


def test_generated_sample_files_flow_through_all_stages(tmp_path: Path) -> None:
    config = _config(tmp_path)
    generate_supplier_files(config, rows_per_supplier=200, bad_row_ratio=0.05, seed=5, now=NOW)

    extractions = extract_all(config, run_id="run-1")
    validations = validate_all(config, extractions, run_id="run-1", now=NOW)
    outcomes = transform_all(config, validations, run_id="run-1")

    assert all(outcome.succeeded for outcome in outcomes)
    for outcome, validation in zip(outcomes, validations, strict=True):
        assert outcome.batch is not None
        assert validation.result is not None
        ids = [row.product_id for row in outcome.batch.products]
        assert len(ids) == len(validation.result.valid)
        assert len(set(ids)) == len(ids)
        assert all(row.unit_price.as_tuple().exponent == -4 for row in outcome.batch.products)
