import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agpp.pipelines.supplier_product.config import SupplierConfig, SupplierProductConfig
from agpp.pipelines.supplier_product.extraction import (
    ExtractionResult,
    Extractor,
    SupplierExtraction,
    extract_all,
)
from agpp.pipelines.supplier_product.sample_data import COLUMNS, generate_supplier_files
from agpp.shared.exceptions import (
    ExtractionError,
    SourceUnavailableError,
    UnsupportedSourceError,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _config(directory: Path, attempts: int = 3, delay: float = 0.5) -> SupplierProductConfig:
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
                "allowed_currencies": ["EUR"],
                "max_unit_price": 1000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": attempts, "initial_delay_seconds": delay},
            "suppliers": [supplier("001", ","), supplier("002", ";")],
        }
    )


def _result(supplier: SupplierConfig) -> ExtractionResult:
    return ExtractionResult(supplier.supplier_id, "memory", ("a",), ())


class OkExtractor:
    def __init__(self, supplier: SupplierConfig) -> None:
        self.supplier = supplier

    def extract(self) -> ExtractionResult:
        return _result(self.supplier)


class FailingExtractor:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def extract(self) -> ExtractionResult:
        self.calls += 1
        raise self.error


class FlakyExtractor:
    def __init__(self, supplier: SupplierConfig, failures: int) -> None:
        self.supplier = supplier
        self.failures = failures
        self.calls = 0

    def extract(self) -> ExtractionResult:
        self.calls += 1
        if self.calls <= self.failures:
            raise SourceUnavailableError("share offline")
        return _result(self.supplier)


def _no_sleep(_seconds: float) -> None:
    return None


def test_every_supplier_is_extracted(tmp_path: Path) -> None:
    outcomes = extract_all(
        _config(tmp_path), run_id="run-1", extractor_factory=OkExtractor, sleep=_no_sleep
    )

    assert [outcome.supplier_id for outcome in outcomes] == ["SUP-001", "SUP-002"]
    assert all(outcome.succeeded for outcome in outcomes)


def test_a_failing_supplier_does_not_stop_the_others(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    broken = ExtractionError("bad encoding")

    def factory(supplier: SupplierConfig) -> Extractor:
        if supplier.supplier_id == "SUP-001":
            return FailingExtractor(broken)
        return OkExtractor(supplier)

    with caplog.at_level(logging.INFO):
        outcomes = extract_all(
            _config(tmp_path), run_id="run-1", extractor_factory=factory, sleep=_no_sleep
        )

    first, second = outcomes
    assert first.error is broken
    assert first.result is None
    assert second.succeeded
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1


def test_retryable_errors_are_retried_with_backoff(tmp_path: Path) -> None:
    sleeps: list[float] = []
    flaky: dict[str, FlakyExtractor] = {}

    def factory(supplier: SupplierConfig) -> Extractor:
        flaky[supplier.supplier_id] = FlakyExtractor(supplier, failures=2)
        return flaky[supplier.supplier_id]

    outcomes = extract_all(
        _config(tmp_path), run_id="run-1", extractor_factory=factory, sleep=sleeps.append
    )

    assert all(outcome.succeeded for outcome in outcomes)
    assert flaky["SUP-001"].calls == 3
    assert sleeps == [0.5, 1.0, 0.5, 1.0]


def test_a_supplier_that_never_recovers_is_reported_after_the_attempts(tmp_path: Path) -> None:
    extractor = FailingExtractor(SourceUnavailableError("share offline"))

    outcomes = extract_all(
        _config(tmp_path, attempts=2),
        run_id="run-1",
        extractor_factory=lambda _supplier: extractor,
        sleep=_no_sleep,
    )

    assert all(isinstance(outcome.error, SourceUnavailableError) for outcome in outcomes)
    assert extractor.calls == 4  # two suppliers, two attempts each


def test_factory_errors_are_isolated_too(tmp_path: Path) -> None:
    def factory(supplier: SupplierConfig) -> Extractor:
        if supplier.supplier_id == "SUP-002":
            raise UnsupportedSourceError("no extractor")
        return OkExtractor(supplier)

    outcomes = extract_all(
        _config(tmp_path), run_id="run-1", extractor_factory=factory, sleep=_no_sleep
    )

    assert [outcome.succeeded for outcome in outcomes] == [True, False]


def test_unexpected_exceptions_propagate(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="bug"):
        extract_all(
            _config(tmp_path),
            run_id="run-1",
            extractor_factory=lambda _supplier: FailingExtractor(RuntimeError("bug")),
            sleep=_no_sleep,
        )


def test_log_records_carry_the_run_context(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        extract_all(
            _config(tmp_path), run_id="run-42", extractor_factory=OkExtractor, sleep=_no_sleep
        )

    fields = [
        record.__dict__ for record in caplog.records if record.name.startswith("agpp.pipelines")
    ]
    assert fields
    assert all(
        item["run_id"] == "run-42" and item["pipeline"] == "supplier_product" for item in fields
    )
    assert "Extraction finished" in caplog.text


def _rows(outcomes: list[SupplierExtraction]) -> list[int]:
    return [outcome.result.row_count for outcome in outcomes if outcome.result is not None]


def test_extracts_the_generated_sample_files(tmp_path: Path) -> None:
    config = _config(tmp_path)
    generate_supplier_files(config, rows_per_supplier=30, bad_row_ratio=0.1, seed=3, now=NOW)

    outcomes = extract_all(config, run_id="run-1")

    assert _rows(outcomes) == [30, 30]
    assert outcomes[0].result is not None
    assert outcomes[0].result.columns == COLUMNS


def test_missing_files_fail_every_supplier_after_retrying(tmp_path: Path) -> None:
    sleeps: list[float] = []

    outcomes = extract_all(_config(tmp_path), run_id="run-1", sleep=sleeps.append)

    assert all(isinstance(outcome.error, SourceUnavailableError) for outcome in outcomes)
    assert sleeps == [0.5, 1.0, 0.5, 1.0]
