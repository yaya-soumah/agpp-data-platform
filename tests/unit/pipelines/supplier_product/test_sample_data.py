import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.models import SupplierProduct
from agpp.pipelines.supplier_product.sample_data import COLUMNS, generate_supplier_files

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def _config(directory: Path) -> SupplierProductConfig:
    return SupplierProductConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.1,
                "allowed_currencies": ["EUR", "USD"],
                "max_unit_price": 1000000,
                "future_tolerance_minutes": 5,
            },
            "suppliers": [
                {
                    "supplier_id": "SUP-001",
                    "name": "One",
                    "country": "LU",
                    "source": {"type": "csv", "path": str(directory / "one.csv")},
                },
                {
                    "supplier_id": "SUP-002",
                    "name": "Two",
                    "country": "DE",
                    "source": {
                        "type": "csv",
                        "path": str(directory / "two.csv"),
                        "delimiter": ";",
                    },
                },
            ],
        }
    )


def _generate(directory: Path, rows: int = 50, ratio: float = 0.0, seed: int = 1):  # type: ignore[no-untyped-def]
    return generate_supplier_files(
        _config(directory), rows_per_supplier=rows, bad_row_ratio=ratio, seed=seed, now=NOW
    )


def _read(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def _is_valid(row: dict[str, str]) -> bool:
    try:
        SupplierProduct.model_validate({**row, "supplier_id": "SUP-001"})
    except ValidationError:
        return False
    return True


def test_writes_one_file_per_supplier_in_its_format(tmp_path: Path) -> None:
    summaries = _generate(tmp_path)

    assert [s.supplier_id for s in summaries] == ["SUP-001", "SUP-002"]
    first = _read(tmp_path / "one.csv")
    second = _read(tmp_path / "two.csv", delimiter=";")
    assert list(first[0]) == list(COLUMNS)
    assert len(first) == len(second) == 50


def test_missing_directories_are_created(tmp_path: Path) -> None:
    _generate(tmp_path / "a" / "b")

    assert (tmp_path / "a" / "b" / "one.csv").is_file()


def test_same_seed_gives_identical_files(tmp_path: Path) -> None:
    _generate(tmp_path / "first", seed=7)
    _generate(tmp_path / "second", seed=7)
    _generate(tmp_path / "other", seed=8)

    first = (tmp_path / "first" / "one.csv").read_bytes()
    assert first == (tmp_path / "second" / "one.csv").read_bytes()
    assert first != (tmp_path / "other" / "one.csv").read_bytes()


def test_clean_files_contain_only_valid_rows(tmp_path: Path) -> None:
    _generate(tmp_path, rows=200, ratio=0.0)

    rows = _read(tmp_path / "one.csv") + _read(tmp_path / "two.csv", delimiter=";")
    assert all(_is_valid(row) for row in rows)


def test_defective_rows_follow_the_ratio(tmp_path: Path) -> None:
    summaries = _generate(tmp_path, rows=100, ratio=0.2)

    assert [s.defective_rows for s in summaries] == [20, 20]


def test_defects_break_the_rules(tmp_path: Path) -> None:
    summary = _generate(tmp_path, rows=200, ratio=0.2)[0]

    rows = _read(tmp_path / "one.csv")
    rejected = sum(1 for row in rows if not _is_valid(row))
    assert 0 < rejected <= summary.defective_rows


@pytest.mark.parametrize(
    ("rows", "ratio"),
    [(0, 0.1), (10, -0.1), (10, 1.5)],
)
def test_invalid_arguments_are_rejected(tmp_path: Path, rows: int, ratio: float) -> None:
    with pytest.raises(ValueError, match="must"):
        _generate(tmp_path, rows=rows, ratio=ratio)
