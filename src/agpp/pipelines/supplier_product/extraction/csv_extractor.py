"""Extractor for supplier files in CSV format."""

import csv
from collections.abc import Iterable
from pathlib import Path

from agpp.pipelines.supplier_product.config import SupplierConfig
from agpp.pipelines.supplier_product.extraction.base import ExtractionResult, RawRecord
from agpp.shared.exceptions import ExtractionError, SourceUnavailableError


class CsvExtractor:
    """Reads a delimited text file into raw records."""

    def __init__(self, supplier: SupplierConfig) -> None:
        self._supplier = supplier

    def extract(self) -> ExtractionResult:
        source = self._supplier.source
        path = Path(source.path)
        context = {"supplier_id": self._supplier.supplier_id, "path": str(path)}
        try:
            with path.open(encoding=source.encoding, newline="") as handle:
                return self._read(handle, path)
        except OSError as error:
            raise SourceUnavailableError(
                f"Cannot read supplier file {path}", context=context
            ) from error
        except LookupError as error:
            raise ExtractionError(
                f"Unknown file encoding {source.encoding!r}", context=context
            ) from error
        except UnicodeDecodeError as error:
            raise ExtractionError(
                f"File {path} is not valid {source.encoding}", context=context
            ) from error
        except csv.Error as error:
            raise ExtractionError(f"Malformed CSV in {path}: {error}", context=context) from error

    def _read(self, lines: Iterable[str], path: Path) -> ExtractionResult:
        reader = csv.reader(lines, delimiter=self._supplier.source.delimiter)
        columns: tuple[str, ...] | None = None
        records: list[RawRecord] = []
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue  # blank line or a row of empty cells
            if columns is None:
                columns = _parse_header(row, path)
                continue
            records.append(_record(reader.line_num, columns, row))
        return ExtractionResult(
            supplier_id=self._supplier.supplier_id,
            source=str(path),
            columns=columns or (),
            records=tuple(records),
        )


def _parse_header(row: list[str], path: Path) -> tuple[str, ...]:
    names = [cell.lstrip("\ufeff").strip().lower() for cell in row]
    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    if duplicates:
        raise ExtractionError(
            f"Duplicate column names in {path}: {duplicates}", context={"path": str(path)}
        )
    return tuple(names)


def _record(line_number: int, columns: tuple[str, ...], row: list[str]) -> RawRecord:
    problem = None
    if len(row) != len(columns):
        problem = f"expected {len(columns)} fields, found {len(row)}"
    return RawRecord(line_number, dict(zip(columns, row, strict=False)), problem)
