from typing import Protocol

import polars as pl


class SupplierProductExtractor(Protocol):
    """Contract for supplier-product data extraction."""

    def extract(self) -> pl.DataFrame:
        """Extract data from an external source."""

        ...
