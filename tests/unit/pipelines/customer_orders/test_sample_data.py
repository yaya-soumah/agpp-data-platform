import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.extraction import extract_orders
from agpp.pipelines.customer_orders.sample_data import GenerationSummary, generate_orders_file
from agpp.pipelines.customer_orders.validation import validate_orders
from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
PRODUCTS = [f"SUP-001:S1-{number:05d}" for number in range(1, 11)]


def _config(path: Path, max_reject_ratio: float = 1.0) -> CustomerOrdersConfig:
    return CustomerOrdersConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": max_reject_ratio,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_line_amount": 1000000,
                "future_tolerance_minutes": 5,
            },
            "source": {"type": "csv", "path": str(path), "delimiter": ";"},
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
        }
    )


def _generate(
    path: Path,
    lines: int = 100,
    bad: float = 0.0,
    unknown: float = 0.0,
    seed: int = 1,
    products: list[str] | None = None,
) -> GenerationSummary:
    return generate_orders_file(
        _config(path),
        product_ids=PRODUCTS if products is None else products,
        lines=lines,
        bad_row_ratio=bad,
        unknown_product_ratio=unknown,
        seed=seed,
        now=NOW,
    )


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def test_the_configured_file_is_written_with_the_contract_columns(tmp_path: Path) -> None:
    path = tmp_path / "incoming" / "orders.csv"

    summary = _generate(path, lines=50)

    rows = _read(path)
    assert summary.path == path
    assert list(rows[0]) == list(REQUIRED_COLUMNS)
    assert len(rows) == summary.rows == 50


def test_the_same_seed_gives_identical_files(tmp_path: Path) -> None:
    _generate(tmp_path / "a.csv", seed=7)
    _generate(tmp_path / "b.csv", seed=7)
    _generate(tmp_path / "c.csv", seed=8)

    first = (tmp_path / "a.csv").read_bytes()
    assert first == (tmp_path / "b.csv").read_bytes()
    assert first != (tmp_path / "c.csv").read_bytes()


def test_a_clean_file_passes_validation_completely(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"
    _generate(path, lines=200)
    config = _config(path)

    content = extract_orders(config, run_id="r", sleep=lambda _seconds: None)
    result = validate_orders(content, str(path), config.quality, run_id="r", now=NOW)

    assert len(result.valid) == 200
    assert result.rejected == ()


def test_orders_have_consecutive_line_numbers_and_consistent_customers(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"
    _generate(path, lines=200)

    rows = _read(path)
    lines_by_order: dict[str, list[int]] = {}
    names: dict[str, set[str]] = {}
    for row in rows:
        lines_by_order.setdefault(row["order_id"], []).append(int(row["line_number"]))
        names.setdefault(row["customer_id"].strip().upper(), set()).add(
            " ".join(row["customer_name"].split())
        )
    assert all(numbers == list(range(1, len(numbers) + 1)) for numbers in lines_by_order.values())
    assert all(len(variants) == 1 for variants in names.values())


def test_products_come_from_the_given_ids_and_unknown_ones_are_counted(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"

    summary = _generate(path, lines=200, unknown=0.3)

    products = [row["product_id"].strip().upper() for row in _read(path)]
    unknown = [product for product in products if product.startswith("SUP-999:")]
    assert len(unknown) == summary.unknown_product_lines > 0
    assert all(product in PRODUCTS for product in products if product not in unknown)


def test_no_unknown_products_are_generated_by_default(tmp_path: Path) -> None:
    summary = _generate(tmp_path / "orders.csv", lines=100)

    assert summary.unknown_product_lines == 0


def test_only_unknown_products_can_be_generated_without_a_catalog(tmp_path: Path) -> None:
    summary = _generate(tmp_path / "orders.csv", lines=20, unknown=1.0, products=[])

    assert summary.unknown_product_lines == 20


def test_defective_rows_follow_the_ratio(tmp_path: Path) -> None:
    summary = _generate(tmp_path / "orders.csv", lines=100, bad=0.1)

    assert summary.defective_rows == 10


def test_defects_are_caught_by_validation(tmp_path: Path) -> None:
    path = tmp_path / "orders.csv"
    summary = _generate(path, lines=300, bad=0.1)
    config = _config(path)

    content = extract_orders(config, run_id="r", sleep=lambda _seconds: None)
    result = validate_orders(content, str(path), config.quality, run_id="r", now=NOW)

    assert 0 < len(result.rejected) <= summary.defective_rows
    assert len(result.valid) + len(result.rejected) == 300


@pytest.mark.parametrize(
    ("lines", "bad", "unknown", "products"),
    [
        (0, 0.1, 0.0, PRODUCTS),
        (10, -0.1, 0.0, PRODUCTS),
        (10, 1.5, 0.0, PRODUCTS),
        (10, 0.1, 1.5, PRODUCTS),
        (10, 0.1, 0.5, []),
    ],
)
def test_invalid_arguments_are_rejected(
    tmp_path: Path, lines: int, bad: float, unknown: float, products: list[str]
) -> None:
    with pytest.raises(ValueError, match="must"):
        _generate(tmp_path / "orders.csv", lines, bad, unknown, products=products)
