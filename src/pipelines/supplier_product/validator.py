from typing import Protocol

import polars as pl


class SupplierProductValidator(Protocol):
    """Contract for supplier product validation."""

    def validate(self, records: pl.DataFrame) -> pl.DataFrame:
        """Validate supplier product records."""
        pass
