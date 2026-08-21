from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models import SupplierProduct
from src.shared.currency import Currency, Money


def test_supplier_product_can_be_created_with_required_fields() -> None:
    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Stainless Steel Bottle 500ml",
    )

    assert supplier_product.supplier_product_id == "SP-001"
    assert supplier_product.supplier_id == "SUP-001"
    assert supplier_product.name == "Stainless Steel Bottle 500ml"
    assert supplier_product.supplier_sku is None
    assert supplier_product.description is None
    assert supplier_product.price is None
    assert supplier_product.minimum_order_quantity is None
    assert supplier_product.lead_time_days is None


def test_supplier_product_accepts_optional_fields() -> None:
    price = Money(
        amount=Decimal("8.50"),
        currency=Currency.USD,
    )

    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        supplier_sku="ABC-500",
        name="Stainless Steel Bottle 500ml",
        description="Vacuum insulated stainless steel bottle",
        price=price,
        minimum_order_quantity=Decimal("100"),
        lead_time_days=7,
    )

    assert supplier_product.supplier_sku == "ABC-500"
    assert (
        supplier_product.description
        == "Vacuum insulated stainless steel bottle"
    )
    assert supplier_product.price == price
    assert supplier_product.price.amount == Decimal("8.50")
    assert supplier_product.price.currency == Currency.USD
    assert supplier_product.minimum_order_quantity == Decimal("100")
    assert supplier_product.lead_time_days == 7


def test_supplier_product_requires_supplier_product_id() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_id="SUP-001",
            name="Stainless Steel Bottle 500ml",
        )


def test_supplier_product_requires_supplier_id() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            name="Stainless Steel Bottle 500ml",
        )


def test_supplier_product_requires_name() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
        )


def test_supplier_product_rejects_empty_supplier_product_id() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="",
            supplier_id="SUP-001",
            name="Stainless Steel Bottle 500ml",
        )


def test_supplier_product_rejects_empty_supplier_id() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="",
            name="Stainless Steel Bottle 500ml",
        )


def test_supplier_product_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="",
        )


def test_supplier_product_accepts_money_as_price() -> None:
    price = Money(
        amount=Decimal("125.75"),
        currency=Currency.CNY,
    )

    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Product",
        price=price,
    )

    assert supplier_product.price == price
    assert supplier_product.price.amount == Decimal("125.75")
    assert supplier_product.price.currency == Currency.CNY


def test_supplier_product_rejects_invalid_minimum_order_quantity() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="Product",
            minimum_order_quantity=Decimal("-1"),
        )


def test_supplier_product_rejects_zero_minimum_order_quantity() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="Product",
            minimum_order_quantity=Decimal("0"),
        )


def test_supplier_product_rejects_negative_lead_time() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="Product",
            lead_time_days=-1,
        )


def test_supplier_product_accepts_zero_lead_time() -> None:
    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Product",
        lead_time_days=0,
    )

    assert supplier_product.lead_time_days == 0


def test_supplier_product_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SupplierProduct(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="Product",
            unknown_field="unexpected",
        )


def test_supplier_product_validates_assignment() -> None:
    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Product",
    )

    with pytest.raises(ValidationError):
        supplier_product.name = ""


def test_supplier_product_allows_valid_assignment() -> None:
    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Product",
    )

    supplier_product.name = "Updated Product"

    assert supplier_product.name == "Updated Product"

def test_supplier_product_preserves_money_value_object() -> None:
    price = Money(
        amount=Decimal("99.90"),
        currency=Currency.EUR,
    )

    supplier_product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Product",
        price=price,
    )

    assert supplier_product.price is price