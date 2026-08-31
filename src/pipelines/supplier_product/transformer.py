from collections.abc import Sequence
from typing import Protocol

import polars as pl
from src.models.supplier_product import SupplierProduct


class SupplierProductTransformer(Protocol):
    """Contract for supplier product transformation."""

    def transform(self, records: pl.DataFrame) -> Sequence[SupplierProduct]:
        """Transform validated records into domain models."""

        pass
