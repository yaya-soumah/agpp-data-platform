import logging
from pathlib import Path

import pytest

from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.extraction import extract_orders
from agpp.shared.exceptions import ExtractionError, SourceUnavailableError


def _config(path: Path, attempts: int = 3, delay: float = 0.5) -> CustomerOrdersConfig:
    return CustomerOrdersConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "allowed_currencies": ["EUR"],
                "max_line_amount": 1000,
                "future_tolerance_minutes": 5,
            },
            "source": {"type": "csv", "path": str(path)},
            "extraction": {"max_attempts": attempts, "initial_delay_seconds": delay},
        }
    )


def _no_sleep(_seconds: float) -> None:
    return None


def test_the_configured_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"
    path.write_text("order_id,quantity\nO-1,2\nO-2,3\n", encoding="utf-8")

    content = extract_orders(_config(path), run_id="run-1", sleep=_no_sleep)

    assert content.columns == ("order_id", "quantity")
    assert [record.values["order_id"] for record in content.records] == ["O-1", "O-2"]


def test_a_missing_file_is_retried_and_then_raised(tmp_path: Path) -> None:
    sleeps: list[float] = []

    with pytest.raises(SourceUnavailableError) as info:
        extract_orders(_config(tmp_path / "absent.csv"), run_id="run-1", sleep=sleeps.append)

    assert sleeps == [0.5, 1.0]
    assert info.value.context["pipeline"] == "customer_orders"


def test_a_file_that_appears_between_attempts_is_read(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"

    def sleep_then_deliver(_seconds: float) -> None:
        path.write_text("order_id\nO-1\n", encoding="utf-8")

    content = extract_orders(_config(path), run_id="run-1", sleep=sleep_then_deliver)

    assert len(content.records) == 1


def test_malformed_content_is_not_retried(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"
    path.write_bytes(b"order_id\n\xff\xfe\n")
    sleeps: list[float] = []

    with pytest.raises(ExtractionError):
        extract_orders(_config(path), run_id="run-1", sleep=sleeps.append)

    assert sleeps == []


def test_log_records_carry_the_run_context(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "orders.csv"
    path.write_text("order_id\nO-1\n", encoding="utf-8")

    with caplog.at_level(logging.INFO):
        extract_orders(_config(path), run_id="run-5", sleep=_no_sleep)

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-5" for item in fields)
    assert "Orders extracted" in caplog.text
