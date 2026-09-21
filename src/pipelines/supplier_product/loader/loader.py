from dataclasses import dataclass
from typing import Protocol

import polars as pl


@dataclass(frozen=True)
class LoadResult:
    """Result of a supplier product loading operation."""

    records_loaded: int


class SupplierProductLoader(Protocol):
    """Contract for supplier product persistence."""

    def load(
        self,
        products: pl.DataFrame,
    ) -> LoadResult:
        """Persist supplier products."""
        ...


@dataclass(frozen=True)
class WarehouseLoadResult:
    """Result of a supplier product warehouse loading operation."""

    records_loaded: int


class SupplierProductWarehouseLoader(Protocol):
    """Contract for supplier warehouse product persistence."""

    def load(
        self,
        products: pl.DataFrame,
    ) -> WarehouseLoadResult:
        """Persist supplier products in the analytical warehouse."""
        ...
