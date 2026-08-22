from dataclasses import dataclass
from collections.abc import Sequence
from typing import Protocol

from src.models.supplier_product import SupplierProduct


@dataclass(frozen=True)
class LoadResult:
    """Result of a supplier product loading operation."""

    records_loaded: int


class SupplierProductLoader(Protocol):
    """Contract for supplier product persistence."""

    def load(
            self,
            products: Sequence[SupplierProduct],
    ) -> LoadResult:
        """Persist supplier products."""
        pass
