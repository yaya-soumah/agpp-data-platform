from collections.abc import Sequence
from typing import Protocol

from src.models.supplier_product import SupplierProduct
from src.pipelines.supplier_product.models import ValidateSupplierProductRecord


class SupplierProductTransformer(Protocol):
    """Contract for supplier product transformation."""

    def transform(
        self, records: Sequence[ValidateSupplierProductRecord]
    ) -> Sequence[SupplierProduct]:
        """Transform validated records into domain models."""

        pass
