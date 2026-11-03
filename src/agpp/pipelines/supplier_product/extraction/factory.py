"""Create the extractor for a supplier's source type (ADR-0011)."""

from collections.abc import Callable

from agpp.pipelines.supplier_product.config import SupplierConfig
from agpp.pipelines.supplier_product.extraction.base import Extractor
from agpp.pipelines.supplier_product.extraction.csv_extractor import CsvExtractor
from agpp.shared.exceptions import UnsupportedSourceError

ExtractorBuilder = Callable[[SupplierConfig], Extractor]

_BUILDERS: dict[str, ExtractorBuilder] = {"csv": CsvExtractor}


def register_extractor(source_type: str, builder: ExtractorBuilder) -> None:
    """Make a new source type available without changing existing code."""
    _BUILDERS[source_type] = builder


def create_extractor(supplier: SupplierConfig) -> Extractor:
    """Return the extractor for ``supplier.source.type``."""
    source_type = supplier.source.type
    builder = _BUILDERS.get(source_type)
    if builder is None:
        raise UnsupportedSourceError(
            f"No extractor for source type {source_type!r}",
            context={"supplier_id": supplier.supplier_id, "source_type": source_type},
        )
    return builder(supplier)
