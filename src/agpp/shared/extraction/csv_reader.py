"""Read delimited text files into raw records (ADR-0011, ADR-0017)."""

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from agpp.shared.exceptions import ExtractionError, SourceUnavailableError
from agpp.shared.extraction.records import RawRecord


@dataclass(frozen=True)
class CsvContent:
    """The columns and records found in one file."""

    columns: tuple[str, ...]
    records: tuple[RawRecord, ...]


def read_csv(
    path: Path,
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
    context: Mapping[str, object] | None = None,
) -> CsvContent:
    """Read a delimited file.

    A file that cannot be opened raises ``SourceUnavailableError`` (retryable).
    Malformed content (undecodable bytes, duplicate columns, broken quoting,
    oversized fields, unknown encoding) raises ``ExtractionError``. Rows with the
    wrong number of fields are flagged on the record, not raised. ``context`` is
    added to every error.
    """
    error_context: dict[str, object] = {**(context or {}), "path": str(path)}
    try:
        with path.open(encoding=encoding, newline="") as handle:
            return _parse(handle, path, delimiter, error_context)
    except OSError as error:
        raise SourceUnavailableError(f"Cannot read file {path}", context=error_context) from error
    except LookupError as error:
        raise ExtractionError(
            f"Unknown file encoding {encoding!r}", context=error_context
        ) from error
    except UnicodeDecodeError as error:
        raise ExtractionError(
            f"File {path} is not valid {encoding}", context=error_context
        ) from error
    except csv.Error as error:
        raise ExtractionError(f"Malformed CSV in {path}: {error}", context=error_context) from error


def _parse(
    lines: Iterable[str], path: Path, delimiter: str, context: Mapping[str, object]
) -> CsvContent:
    reader = csv.reader(lines, delimiter=delimiter)
    columns: tuple[str, ...] | None = None
    records: list[RawRecord] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue  # blank line or a row of empty cells
        if columns is None:
            columns = _parse_header(row, path, context)
            continue
        records.append(_record(reader.line_num, columns, row))
    return CsvContent(columns or (), tuple(records))


def _parse_header(row: list[str], path: Path, context: Mapping[str, object]) -> tuple[str, ...]:
    names = [cell.lstrip("\ufeff").strip().lower() for cell in row]
    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    if duplicates:
        raise ExtractionError(f"Duplicate column names in {path}: {duplicates}", context=context)
    return tuple(names)


def _record(line_number: int, columns: tuple[str, ...], row: list[str]) -> RawRecord:
    problem = None
    if len(row) != len(columns):
        problem = f"expected {len(columns)} fields, found {len(row)}"
    return RawRecord(line_number, dict(zip(columns, row, strict=False)), problem)
