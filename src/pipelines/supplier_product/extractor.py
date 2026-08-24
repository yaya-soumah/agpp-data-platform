from collections.abc import Sequence
from typing import Protocol

from src.pipelines.supplier_product.models import SupplierProductRecord


class SupplierProductExtractor(Protocol):
    """Contract for supplier product extractor."""

    def extract(self) -> Sequence[SupplierProductRecord]:
        """Extract supplier product records from an external source."""

        pass
