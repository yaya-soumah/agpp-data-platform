"""Warehouse-shaped rows produced by the transformation (ADR-0016)."""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import AwareDatetime

from agpp.shared.models import AgppModel


class CustomerRow(AgppModel):
    """A row for ``warehouse.dim_customer`` (business key: ``customer_id``)."""

    customer_id: str
    customer_name: str
    country: str
    source_updated_at: AwareDatetime


class OrderLineRow(AgppModel):
    """A row for ``warehouse.fact_order_line`` (business key: ``order_id``, ``line_number``).

    The surrogate keys of the customer and the product are resolved by the loader.
    """

    order_id: str
    line_number: int
    customer_id: str
    product_id: str
    date_key: int
    quantity: int
    unit_price: Decimal
    line_amount: Decimal
    currency: str
    status: str
    ordered_at: AwareDatetime
    source_updated_at: AwareDatetime


@dataclass(frozen=True)
class TransformedOrders:
    """Everything to load for one run."""

    customers: tuple[CustomerRow, ...]
    lines: tuple[OrderLineRow, ...]
