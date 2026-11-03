"""Extraction stage of the Supplier Product pipeline."""

from agpp.pipelines.supplier_product.extraction.base import (
    ExtractionResult,
    Extractor,
    RawRecord,
)
from agpp.pipelines.supplier_product.extraction.factory import (
    create_extractor,
    register_extractor,
)
from agpp.pipelines.supplier_product.extraction.stage import SupplierExtraction, extract_all

__all__ = [
    "ExtractionResult",
    "Extractor",
    "RawRecord",
    "SupplierExtraction",
    "create_extractor",
    "extract_all",
    "register_extractor",
]
