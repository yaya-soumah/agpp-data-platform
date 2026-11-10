"""Extractor for supplier files in CSV format."""

from pathlib import Path

from agpp.pipelines.supplier_product.config import SupplierConfig
from agpp.pipelines.supplier_product.extraction.base import ExtractionResult
from agpp.shared.extraction import read_csv


class CsvExtractor:
    """Reads a supplier's delimited file into raw records."""

    def __init__(self, supplier: SupplierConfig) -> None:
        self._supplier = supplier

    def extract(self) -> ExtractionResult:
        source = self._supplier.source
        path = Path(source.path)
        content = read_csv(
            path,
            delimiter=source.delimiter,
            encoding=source.encoding,
            context={"supplier_id": self._supplier.supplier_id},
        )
        return ExtractionResult(
            supplier_id=self._supplier.supplier_id,
            source=str(path),
            columns=content.columns,
            records=content.records,
        )
