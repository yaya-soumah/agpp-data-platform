from pathlib import Path

import pytest

from agpp.pipelines.supplier_product.config import SupplierConfig
from agpp.pipelines.supplier_product.extraction.base import ExtractionResult
from agpp.pipelines.supplier_product.extraction.csv_extractor import CsvExtractor
from agpp.shared.exceptions import ExtractionError, SourceUnavailableError


def _supplier(path: Path, delimiter: str = ",", encoding: str = "utf-8") -> SupplierConfig:
    return SupplierConfig.model_validate(
        {
            "supplier_id": "SUP-001",
            "name": "One",
            "country": "LU",
            "source": {
                "type": "csv",
                "path": str(path),
                "delimiter": delimiter,
                "encoding": encoding,
            },
        }
    )


def _extract(
    tmp_path: Path, text: str, delimiter: str = ",", encoding: str = "utf-8"
) -> ExtractionResult:
    path = tmp_path / "supplier.csv"
    path.write_text(text, encoding=encoding, newline="")
    return CsvExtractor(_supplier(path, delimiter, encoding)).extract()


def test_reads_columns_and_records(tmp_path: Path) -> None:
    result = _extract(tmp_path, "supplier_sku,product_name\nA-1,Bolt\nA-2,Nut\n")

    assert result.supplier_id == "SUP-001"
    assert result.source == str(tmp_path / "supplier.csv")
    assert result.columns == ("supplier_sku", "product_name")
    assert result.row_count == 2
    assert result.records[0].values == {"supplier_sku": "A-1", "product_name": "Bolt"}
    assert result.records[0].line_number == 2
    assert result.records[0].problem is None


def test_uses_the_configured_delimiter(tmp_path: Path) -> None:
    result = _extract(tmp_path, "a;b\n1;2\n", delimiter=";")

    assert result.records[0].values == {"a": "1", "b": "2"}


def test_header_names_are_trimmed_and_lower_cased(tmp_path: Path) -> None:
    result = _extract(tmp_path, "Supplier_SKU , Product_Name\nA-1,Bolt\n")

    assert result.columns == ("supplier_sku", "product_name")


def test_a_byte_order_mark_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "supplier.csv"
    path.write_bytes(b"\xef\xbb\xbfsupplier_sku,product_name\nA-1,Bolt\n")

    result = CsvExtractor(_supplier(path)).extract()

    assert result.columns == ("supplier_sku", "product_name")


def test_values_are_kept_exactly_as_read(tmp_path: Path) -> None:
    result = _extract(tmp_path, "a,b\n x ,  y\n")

    assert result.records[0].values == {"a": " x ", "b": "  y"}


def test_blank_lines_and_empty_rows_are_skipped_but_line_numbers_stay_true(
    tmp_path: Path,
) -> None:
    result = _extract(tmp_path, "a,b\n\n1,2\n,\n3,4\n")

    assert [record.line_number for record in result.records] == [3, 5]


def test_quoted_fields_may_contain_delimiters_and_newlines(tmp_path: Path) -> None:
    result = _extract(tmp_path, 'a,b\n"x, y","line1\nline2"\n')

    assert result.records[0].values == {"a": "x, y", "b": "line1\nline2"}
    assert result.records[0].line_number == 3


def test_rows_with_the_wrong_number_of_fields_are_flagged(tmp_path: Path) -> None:
    result = _extract(tmp_path, "a,b,c\n1,2\n1,2,3,4\n1,2,3\n")

    short, long, fine = result.records
    assert short.problem == "expected 3 fields, found 2"
    assert short.values == {"a": "1", "b": "2"}
    assert long.problem == "expected 3 fields, found 4"
    assert long.values == {"a": "1", "b": "2", "c": "3"}
    assert fine.problem is None


def test_an_empty_file_has_no_columns_and_no_records(tmp_path: Path) -> None:
    result = _extract(tmp_path, "")

    assert result.columns == ()
    assert result.records == ()


def test_a_header_only_file_has_columns_and_no_records(tmp_path: Path) -> None:
    result = _extract(tmp_path, "a,b\n")

    assert result.columns == ("a", "b")
    assert result.records == ()


def test_a_missing_file_is_a_retryable_source_error(tmp_path: Path) -> None:
    extractor = CsvExtractor(_supplier(tmp_path / "absent.csv"))

    with pytest.raises(SourceUnavailableError) as info:
        extractor.extract()

    assert info.value.retryable is True
    assert info.value.context["supplier_id"] == "SUP-001"
    assert isinstance(info.value.__cause__, OSError)


def test_a_directory_is_a_source_error(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailableError):
        CsvExtractor(_supplier(tmp_path)).extract()


def test_undecodable_bytes_are_a_non_retryable_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "supplier.csv"
    path.write_bytes(b"a,b\n\xff\xfe,2\n")

    with pytest.raises(ExtractionError) as info:
        CsvExtractor(_supplier(path)).extract()

    assert not isinstance(info.value, SourceUnavailableError)
    assert info.value.retryable is False


def test_an_unknown_encoding_is_an_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "supplier.csv"
    path.write_text("a,b\n", encoding="utf-8")

    with pytest.raises(ExtractionError, match="encoding"):
        CsvExtractor(_supplier(path, encoding="no-such-encoding")).extract()


def test_duplicate_column_names_are_an_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="Duplicate column names"):
        _extract(tmp_path, "a,b,a\n1,2,3\n")


def test_oversized_fields_are_an_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="Malformed CSV"):
        _extract(tmp_path, "a\n" + "x" * 200_000 + "\n")
