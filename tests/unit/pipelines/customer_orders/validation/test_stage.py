import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from agpp.pipelines.customer_orders.config import CustomerOrdersConfig, QualityConfig
from agpp.pipelines.customer_orders.extraction import extract_orders
from agpp.pipelines.customer_orders.validation import RejectionStage, validate_orders
from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS
from agpp.shared.exceptions import QualityThresholdExceededError, SchemaValidationError
from agpp.shared.extraction import CsvContent, RawRecord

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
QUALITY = QualityConfig(
    max_reject_ratio=0.15,
    allowed_currencies=("EUR", "USD"),
    max_line_amount=Decimal("1000"),
    future_tolerance_minutes=5,
)
GOOD_ROW = {
    "order_id": "O-0000",
    "line_number": "1",
    "customer_id": "CUS-00042",
    "customer_name": "Marie Dupont",
    "customer_country": "LU",
    "ordered_at": "2026-11-09T10:00:00Z",
    "product_id": "SUP-001:S1-00012",
    "quantity": "2",
    "unit_price": "10.00",
    "currency": "EUR",
    "status": "placed",
    "updated_at": "2026-11-09T11:00:00Z",
}


def _content(rows: list[dict[str, str]], columns: tuple[str, ...] = REQUIRED_COLUMNS) -> CsvContent:
    records = tuple(RawRecord(index + 2, row) for index, row in enumerate(rows))
    return CsvContent(columns, records)


def _rows(count: int) -> list[dict[str, str]]:
    return [{**GOOD_ROW, "order_id": f"O-{index:04d}"} for index in range(count)]


def test_a_clean_file_is_fully_valid() -> None:
    result = validate_orders(_content(_rows(20)), "orders.csv", QUALITY, run_id="r", now=NOW)

    assert result.rows_read == 20
    assert len(result.valid) == 20
    assert result.rejected == ()


def test_rejects_from_every_check_are_collected_in_line_order() -> None:
    rows = _rows(40)
    rows[1] = {**rows[1], "quantity": "0"}  # parsing, line 3
    rows[10] = {**rows[10], "currency": "JPY"}  # business, line 12
    rows[20] = {**rows[20], "order_id": rows[0]["order_id"]}  # duplicate of line 2, line 22
    rows[30] = {**rows[30], "quantity": "x", "currency": "EURO"}  # parsing, line 32

    result = validate_orders(_content(rows), "orders.csv", QUALITY, run_id="r", now=NOW)

    assert [r.line_number for r in result.rejected] == [2, 3, 12, 32]
    assert result.rejected_by(RejectionStage.PARSING) == 2
    assert result.rejected_by(RejectionStage.BUSINESS) == 1
    assert result.rejected_by(RejectionStage.DUPLICATE) == 1
    assert len(result.valid) == 36


def test_extra_columns_are_ignored_and_reported() -> None:
    rows = [{**row, "color": "red"} for row in _rows(5)]

    result = validate_orders(
        _content(rows, (*REQUIRED_COLUMNS, "color")), "orders.csv", QUALITY, run_id="r", now=NOW
    )

    assert result.ignored_columns == ("color",)
    assert len(result.valid) == 5


def test_a_missing_required_column_stops_the_file() -> None:
    columns = tuple(name for name in REQUIRED_COLUMNS if name != "status")

    with pytest.raises(SchemaValidationError):
        validate_orders(_content(_rows(3), columns), "orders.csv", QUALITY, run_id="r", now=NOW)


def test_too_many_rejects_fail_the_quality_gate() -> None:
    rows = _rows(10)
    rows[0] = {**rows[0], "quantity": "0"}
    rows[1] = {**rows[1], "quantity": "0"}

    with pytest.raises(QualityThresholdExceededError):
        validate_orders(_content(rows), "orders.csv", QUALITY, run_id="r", now=NOW)


def test_a_header_only_file_passes_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = validate_orders(_content([]), "orders.csv", QUALITY, run_id="r", now=NOW)

    assert result.rows_read == 0
    assert "no data rows" in caplog.text


def test_log_records_carry_the_run_context(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        validate_orders(_content(_rows(5)), "orders.csv", QUALITY, run_id="run-9", now=NOW)

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-9" for item in fields)
    assert "Orders validated" in caplog.text


def test_a_real_file_flows_from_extraction_to_validation(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"
    header = ";".join(REQUIRED_COLUMNS)
    lines = [header] + [";".join(row[name] for name in REQUIRED_COLUMNS) for row in _rows(10)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config = CustomerOrdersConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.15,
                "allowed_currencies": ["EUR"],
                "max_line_amount": 1000,
                "future_tolerance_minutes": 5,
            },
            "source": {"type": "csv", "path": str(path), "delimiter": ";"},
        }
    )

    content = extract_orders(config, run_id="run-1")
    result = validate_orders(content, str(path), config.quality, run_id="run-1", now=NOW)

    assert len(result.valid) == 10
    assert result.rejected == ()
