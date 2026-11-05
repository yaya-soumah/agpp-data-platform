"""Warehouse-shaped rows produced by the transformation (ADR-0013)."""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import AwareDatetime

from agpp.shared.models import AgppModel


class SupplierRow(AgppModel):
    """A row for ``warehouse.dim_supplier`` (business key: ``supplier_id``)."""

    supplier_id: str
    supplier_name: str
    country: str


class ProductRow(AgppModel):
    """A row for ``warehouse.dim_product`` (business key: ``product_id``).

    The surrogate ``supplier_key`` is resolved by the loader.
    """

    product_id: str
    supplier_id: str
    supplier_sku: str
    product_name: str
    category: str
    unit_price: Decimal
    currency: str
    min_order_quantity: int
    lead_time_days: int
    is_active: bool
    source_updated_at: AwareDatetime


@dataclass(frozen=True)
class TransformedBatch:
    """Everything to load for one supplier."""

    supplier: SupplierRow
    products: tuple[ProductRow, ...]
