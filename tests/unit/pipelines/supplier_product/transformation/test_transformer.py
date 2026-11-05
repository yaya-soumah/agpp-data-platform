from datetime import UTC, datetime
from decimal import Decimal

import pytest

from agpp.pipelines.supplier_product.models import Supplier, SupplierProduct
from agpp.pipelines.supplier_product.transformation.transformer import (
    collapse_whitespace,
    to_product_row,
    transform_supplier,
)
from agpp.shared.exceptions import TransformationError

SUPPLIER = Supplier(supplier_id="SUP-001", name="Alpine Components", country="LU")
VALUES = {
    "supplier_id": "SUP-001",
    "supplier_sku": "A-001",
    "product_name": "Hex Bolt M8",
    "category": "Fasteners",
    "unit_price": "12.5",
    "currency": "EUR",
    "min_order_quantity": "10",
    "lead_time_days": "7",
    "is_active": "false",
    "updated_at": "2026-11-03T10:00:00Z",
}


def _product(**overrides: str) -> SupplierProduct:
    return SupplierProduct.model_validate({**VALUES, **overrides})


def test_collapse_whitespace() -> None:
    assert collapse_whitespace("  Hex \t Bolt\n M8 ") == "Hex Bolt M8"


def test_product_id_combines_supplier_and_sku() -> None:
    assert to_product_row(_product()).product_id == "SUP-001:A-001"


def test_names_and_categories_have_their_whitespace_collapsed() -> None:
    row = to_product_row(_product(product_name="Hex   Bolt\tM8", category="Fast   eners"))

    assert row.product_name == "Hex Bolt M8"
    assert row.category == "Fast eners"


def test_the_sku_is_left_alone() -> None:
    assert to_product_row(_product(supplier_sku="a-001")).supplier_sku == "A-001"


def test_prices_are_fixed_to_four_decimals() -> None:
    row = to_product_row(_product(unit_price="12.5"))

    assert row.unit_price == Decimal("12.5")
    assert str(row.unit_price) == "12.5000"


def test_other_fields_are_carried_over() -> None:
    row = to_product_row(_product())

    assert row.currency == "EUR"
    assert row.min_order_quantity == 10
    assert row.lead_time_days == 7
    assert row.is_active is False
    assert row.source_updated_at == datetime(2026, 11, 3, 10, 0, tzinfo=UTC)


def test_a_supplier_row_is_built_from_the_supplier() -> None:
    batch = transform_supplier(SUPPLIER, [_product()])

    assert batch.supplier.supplier_id == "SUP-001"
    assert batch.supplier.supplier_name == "Alpine Components"
    assert batch.supplier.country == "LU"
    assert len(batch.products) == 1


def test_a_supplier_without_products_still_yields_its_row() -> None:
    batch = transform_supplier(SUPPLIER, [])

    assert batch.supplier.supplier_id == "SUP-001"
    assert batch.products == ()


def test_transformation_is_deterministic() -> None:
    products = [_product(supplier_sku="A-1"), _product(supplier_sku="A-2")]

    assert transform_supplier(SUPPLIER, products) == transform_supplier(SUPPLIER, products)


def test_a_product_of_another_supplier_is_rejected() -> None:
    with pytest.raises(TransformationError) as info:
        transform_supplier(SUPPLIER, [_product(supplier_id="SUP-002")])

    assert info.value.context["product_supplier_id"] == "SUP-002"


def test_repeated_product_ids_are_rejected() -> None:
    with pytest.raises(TransformationError, match="Duplicate product_id"):
        transform_supplier(SUPPLIER, [_product(), _product()])
