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

__all__ = [
    "ExtractionResult",
    "Extractor",
    "RawRecord",
    "create_extractor",
    "register_extractor",
]
