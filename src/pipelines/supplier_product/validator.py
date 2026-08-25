from collections.abc import Sequence
from typing import Protocol

from src.pipelines.supplier_product.models import (
    SupplierProductRecord,
    ValidateSupplierProductRecord,
)


class SupplierProductValidator(Protocol):
    """Contract for supplier product validation."""

    def validate(
        self, records: Sequence[SupplierProductRecord]
    ) -> Sequence[ValidateSupplierProductRecord]:
        """Validate supplier product records."""
        pass
