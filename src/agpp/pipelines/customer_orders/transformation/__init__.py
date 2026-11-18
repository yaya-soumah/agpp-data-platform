"""Transformation stage of the Customer Orders pipeline."""

from agpp.pipelines.customer_orders.transformation.rows import (
    CustomerRow,
    OrderLineRow,
    TransformedOrders,
)
from agpp.pipelines.customer_orders.transformation.stage import transform_orders
from agpp.pipelines.customer_orders.transformation.transformer import to_rows
from agpp.shared.text import collapse_whitespace

__all__ = [
    "CustomerRow",
    "OrderLineRow",
    "TransformedOrders",
    "collapse_whitespace",
    "to_rows",
    "transform_orders",
]
