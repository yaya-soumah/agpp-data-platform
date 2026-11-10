from pathlib import Path

import pytest

from agpp.shared.exceptions import ExtractionError, SourceUnavailableError
from agpp.shared.extraction import RawRecord, read_csv


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "data.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return path


def test_columns_and_records_are_read(tmp_path: Path) -> None:
    content = read_csv(_write(tmp_path, "Order_ID,Quantity\nO-1,2\nO-2,3\n"))

    assert content.columns == ("order_id", "quantity")
    assert content.records[0] == RawRecord(2, {"order_id": "O-1", "quantity": "2"})
    assert len(content.records) == 2


def test_another_delimiter_can_be_used(tmp_path: Path) -> None:
    content = read_csv(_write(tmp_path, "a;b\n1;2\n"), delimiter=";")

    assert content.records[0].values == {"a": "1", "b": "2"}


def test_ragged_rows_are_flagged(tmp_path: Path) -> None:
    content = read_csv(_write(tmp_path, "a,b\n1\n"))

    assert content.records[0].problem == "expected 2 fields, found 1"


def test_a_missing_file_is_retryable_and_carries_the_context(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailableError) as info:
        read_csv(tmp_path / "absent.csv", context={"source": "orders"})

    assert info.value.retryable is True
    assert info.value.context == {"source": "orders", "path": str(tmp_path / "absent.csv")}


def test_undecodable_bytes_raise_an_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_bytes(b"a,b\n\xff\xfe,2\n")

    with pytest.raises(ExtractionError) as info:
        read_csv(path, context={"source": "orders"})

    assert info.value.retryable is False
    assert info.value.context["source"] == "orders"


def test_duplicate_columns_raise_an_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="Duplicate column names"):
        read_csv(_write(tmp_path, "a,a\n1,2\n"))


def test_a_byte_order_mark_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_bytes(b"\xef\xbb\xbfa,b\n1,2\n")

    assert read_csv(path).columns == ("a", "b")
