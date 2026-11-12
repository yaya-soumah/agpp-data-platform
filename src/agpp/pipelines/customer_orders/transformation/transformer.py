"""Pure transformation of validated order lines into warehouse rows (ADR-0013, ADR-0016)."""

from collections.abc import Sequence
from decimal import Decimal

from agpp.pipelines.customer_orders.models import OrderLine
from agpp.pipelines.customer_orders.transformation.rows import (
    CustomerRow,
    OrderLineRow,
    TransformedOrders,
)
from agpp.shared.dates.datetime_utils import date_key
from agpp.shared.exceptions import TransformationError

_STEP = Decimal("0.0001")


def collapse_whitespace(text: str) -> str:
    """Replace every run of whitespace with a single space."""
    return " ".join(text.split())


def to_rows(lines: Sequence[OrderLine]) -> TransformedOrders:
    """Map validated lines to fact rows and their distinct customers.

    A customer takes its name and country from its most recently updated line
    (the later line on a tie). Raises ``TransformationError`` if the same order
    line appears twice, which would mean a bug upstream.
    """
    seen: set[tuple[str, int]] = set()
    newest: dict[str, OrderLine] = {}
    rows: list[OrderLineRow] = []
    for line in lines:
        key = (line.order_id, line.line_number)
        if key in seen:
            raise TransformationError(
                "Duplicate order line after validation",
                context={"order_id": line.order_id, "line_number": line.line_number},
            )
        seen.add(key)

        current = newest.get(line.customer_id)
        if current is None or line.updated_at >= current.updated_at:
            newest[line.customer_id] = line

        rows.append(
            OrderLineRow(
                order_id=line.order_id,
                line_number=line.line_number,
                customer_id=line.customer_id,
                product_id=line.product_id,
                date_key=date_key(line.ordered_at.date()),
                quantity=line.quantity,
                unit_price=line.unit_price.quantize(_STEP),
                line_amount=line.line_amount.quantize(_STEP),
                currency=line.currency,
                status=line.status.value,
                ordered_at=line.ordered_at,
                source_updated_at=line.updated_at,
            )
        )

    customers = tuple(
        CustomerRow(
            customer_id=customer_id,
            customer_name=collapse_whitespace(line.customer_name),
            country=line.customer_country,
            source_updated_at=line.updated_at,
        )
        for customer_id, line in sorted(newest.items())
    )
    return TransformedOrders(customers=customers, lines=tuple(rows))
