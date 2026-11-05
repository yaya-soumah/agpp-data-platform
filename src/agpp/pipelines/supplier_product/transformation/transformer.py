"""Pure transformation of validated products into warehouse rows (ADR-0013)."""

from collections.abc import Sequence
from decimal import Decimal

from agpp.pipelines.supplier_product.models import Supplier, SupplierProduct
from agpp.pipelines.supplier_product.transformation.rows import (
    ProductRow,
    SupplierRow,
    TransformedBatch,
)
from agpp.shared.exceptions import TransformationError

_PRICE_STEP = Decimal("0.0001")


def collapse_whitespace(text: str) -> str:
    """Replace every run of whitespace with a single space."""
    return " ".join(text.split())


def to_product_row(product: SupplierProduct) -> ProductRow:
    """Map one validated product to its warehouse row."""
    return ProductRow(
        product_id=f"{product.supplier_id}:{product.supplier_sku}",
        supplier_id=product.supplier_id,
        supplier_sku=product.supplier_sku,
        product_name=collapse_whitespace(product.product_name),
        category=collapse_whitespace(product.category),
        unit_price=product.unit_price.quantize(_PRICE_STEP),
        currency=product.currency,
        min_order_quantity=product.min_order_quantity,
        lead_time_days=product.lead_time_days,
        is_active=product.is_active,
        source_updated_at=product.updated_at,
    )


def transform_supplier(supplier: Supplier, products: Sequence[SupplierProduct]) -> TransformedBatch:
    """Transform one supplier's valid products.

    Raises ``TransformationError`` if a product belongs to another supplier or
    if two products end up with the same ``product_id`` (both mean an upstream bug).
    """
    rows: list[ProductRow] = []
    seen: set[str] = set()
    for product in products:
        if product.supplier_id != supplier.supplier_id:
            raise TransformationError(
                "Product does not belong to the supplier being transformed",
                context={
                    "supplier_id": supplier.supplier_id,
                    "product_supplier_id": product.supplier_id,
                },
            )
        row = to_product_row(product)
        if row.product_id in seen:
            raise TransformationError(
                "Duplicate product_id after validation",
                context={"supplier_id": supplier.supplier_id, "product_id": row.product_id},
            )
        seen.add(row.product_id)
        rows.append(row)

    return TransformedBatch(
        supplier=SupplierRow(
            supplier_id=supplier.supplier_id,
            supplier_name=supplier.name,
            country=supplier.country,
        ),
        products=tuple(rows),
    )
