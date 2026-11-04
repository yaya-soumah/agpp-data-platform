import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from agpp.pipelines.supplier_product.config import QualityConfig, SupplierProductConfig
from agpp.pipelines.supplier_product.extraction import (
    ExtractionResult,
    RawRecord,
    SupplierExtraction,
    extract_all,
)
from agpp.pipelines.supplier_product.sample_data import generate_supplier_files
from agpp.pipelines.supplier_product.validation import (
    RejectionStage,
    validate_all,
    validate_supplier,
)
from agpp.pipelines.supplier_product.validation.schema import KNOWN_COLUMNS
from agpp.shared.exceptions import (
    ExtractionError,
    QualityThresholdExceededError,
    SchemaValidationError,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
QUALITY = QualityConfig(
    max_reject_ratio=0.10,
    allowed_currencies=("EUR", "USD"),
    max_unit_price=Decimal("1000"),
    future_tolerance_minutes=5,
)
GOOD_ROW = {
    "supplier_sku": "A-001",
    "product_name": "Hex Bolt M8",
    "category": "Fasteners",
    "unit_price": "10.00",
    "currency": "EUR",
    "min_order_quantity": "1",
    "lead_time_days": "5",
    "is_active": "true",
    "updated_at": "2026-11-03T10:00:00Z",
}


def _extraction(
    supplier_id: str, rows: list[dict[str, str]], columns: tuple[str, ...] = KNOWN_COLUMNS
) -> ExtractionResult:
    records = tuple(RawRecord(index + 2, row) for index, row in enumerate(rows))
    return ExtractionResult(supplier_id, "memory", columns, records)


def _rows(count: int) -> list[dict[str, str]]:
    return [{**GOOD_ROW, "supplier_sku": f"A-{index:03d}"} for index in range(count)]


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


def test_a_clean_file_is_fully_valid() -> None:
    result = validate_supplier(_extraction("SUP-001", _rows(20)), QUALITY, now=NOW)

    assert result.rows_read == 20
    assert len(result.valid) == 20
    assert result.rejected == ()
    assert result.ignored_columns == ()


def test_rejects_from_every_check_are_collected_in_line_order() -> None:
    rows = _rows(40)
    rows[1] = {**rows[1], "unit_price": "0"}  # parsing, line 3
    rows[10] = {**rows[10], "currency": "JPY"}  # business, line 12
    rows[20] = {**rows[20], "supplier_sku": rows[0]["supplier_sku"]}  # duplicate of line 2
    rows[30] = {**rows[30], "unit_price": "abc", "currency": "EURO"}  # parsing, line 32

    result = validate_supplier(_extraction("SUP-001", rows), QUALITY, now=NOW)

    assert [r.line_number for r in result.rejected] == [2, 3, 12, 32]
    assert result.rejected_by(RejectionStage.PARSING) == 2
    assert result.rejected_by(RejectionStage.BUSINESS) == 1
    assert result.rejected_by(RejectionStage.DUPLICATE) == 1
    assert len(result.valid) == 36


def test_extra_columns_are_ignored_and_reported() -> None:
    rows = [{**row, "color": "red"} for row in _rows(5)]

    result = validate_supplier(
        _extraction("SUP-001", rows, (*KNOWN_COLUMNS, "color")), QUALITY, now=NOW
    )

    assert result.ignored_columns == ("color",)
    assert len(result.valid) == 5


def test_a_missing_required_column_stops_the_file() -> None:
    columns = tuple(name for name in KNOWN_COLUMNS if name != "category")

    with pytest.raises(SchemaValidationError):
        validate_supplier(_extraction("SUP-001", _rows(3), columns), QUALITY, now=NOW)


def test_too_many_rejects_fail_the_quality_gate() -> None:
    rows = _rows(10)
    rows[0] = {**rows[0], "unit_price": "0"}
    rows[1] = {**rows[1], "unit_price": "0"}

    with pytest.raises(QualityThresholdExceededError):
        validate_supplier(_extraction("SUP-001", rows), QUALITY, now=NOW)


def test_validate_all_isolates_failures_and_carries_extraction_errors(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    broken_rows = _rows(10)
    broken_rows[0] = {**broken_rows[0], "unit_price": "0"}
    broken_rows[1] = {**broken_rows[1], "unit_price": "0"}
    extraction_error = ExtractionError("bad encoding")
    extractions = [
        SupplierExtraction("SUP-001", result=_extraction("SUP-001", _rows(10))),
        SupplierExtraction("SUP-002", result=_extraction("SUP-002", broken_rows)),
        SupplierExtraction("SUP-003", error=extraction_error),
    ]

    with caplog.at_level(logging.INFO):
        outcomes = validate_all(_config(tmp_path), extractions, run_id="run-1", now=NOW)

    ok, gate, carried = outcomes
    assert ok.succeeded
    assert ok.result is not None
    assert len(ok.result.valid) == 10
    assert isinstance(gate.error, QualityThresholdExceededError)
    assert carried.error is extraction_error
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1


def test_log_records_carry_the_run_context(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    extractions = [SupplierExtraction("SUP-001", result=_extraction("SUP-001", _rows(5)))]

    with caplog.at_level(logging.INFO):
        validate_all(_config(tmp_path), extractions, run_id="run-9", now=NOW)

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-9" for item in fields)
    assert "Validation finished" in caplog.text


def test_a_header_only_file_passes_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    extractions = [SupplierExtraction("SUP-001", result=_extraction("SUP-001", []))]

    with caplog.at_level(logging.WARNING):
        outcomes = validate_all(_config(tmp_path), extractions, run_id="run-1", now=NOW)

    assert outcomes[0].succeeded
    assert "no data rows" in caplog.text


def test_generated_sample_files_pass_and_show_realistic_rejects(tmp_path: Path) -> None:
    config = _config(tmp_path)
    summaries = generate_supplier_files(
        config, rows_per_supplier=200, bad_row_ratio=0.05, seed=11, now=NOW
    )

    extractions = extract_all(config, run_id="run-1")
    outcomes = validate_all(config, extractions, run_id="run-1", now=NOW)

    assert all(outcome.succeeded for outcome in outcomes)
    for outcome, summary in zip(outcomes, summaries, strict=True):
        assert outcome.result is not None
        result = outcome.result
        assert len(result.valid) + len(result.rejected) == 200
        assert 0 < len(result.rejected) <= summary.defective_rows


def test_heavily_defective_sample_files_fail_the_gate(tmp_path: Path) -> None:
    config = _config(tmp_path)
    generate_supplier_files(config, rows_per_supplier=200, bad_row_ratio=0.5, seed=11, now=NOW)

    extractions = extract_all(config, run_id="run-1")
    outcomes = validate_all(config, extractions, run_id="run-1", now=NOW)

    assert all(isinstance(outcome.error, QualityThresholdExceededError) for outcome in outcomes)
