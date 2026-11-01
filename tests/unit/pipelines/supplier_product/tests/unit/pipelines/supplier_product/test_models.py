from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agpp.pipelines.supplier_product.models import Supplier, SupplierProduct

VALID = {
    "supplier_id": "SUP-001",
    "supplier_sku": " ab-100 ",
    "product_name": "  Hex bolt M8  ",
    "category": "Fasteners",
    "unit_price": "12.5000",
    "currency": "eur",
    "min_order_quantity": "10",
    "lead_time_days": "7",
    "is_active": "true",
    "updated_at": "2026-10-30T12:00:00+02:00",
}


def test_text_values_are_converted_to_types() -> None:
    product = SupplierProduct.model_validate(VALID)

    assert product.unit_price == Decimal("12.5")
    assert product.min_order_quantity == 10
    assert product.lead_time_days == 7
    assert product.is_active is True


def test_values_are_normalized() -> None:
    product = SupplierProduct.model_validate(VALID)

    assert product.supplier_sku == "AB-100"
    assert product.product_name == "Hex bolt M8"
    assert product.currency == "EUR"
    assert product.updated_at == datetime(2026, 10, 30, 10, 0, tzinfo=UTC)
    assert product.updated_at.utcoffset() == timedelta(0)


def test_z_suffix_timestamps_are_accepted() -> None:
    product = SupplierProduct.model_validate({**VALID, "updated_at": "2026-10-30T10:00:00Z"})

    assert product.updated_at == datetime(2026, 10, 30, 10, 0, tzinfo=UTC)


def test_optional_columns_have_defaults() -> None:
    data = {k: v for k, v in VALID.items() if k not in {"min_order_quantity", "is_active"}}

    product = SupplierProduct.model_validate(data)

    assert product.min_order_quantity == 1
    assert product.is_active is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("supplier_sku", "   "),
        ("product_name", ""),
        ("category", ""),
        ("unit_price", "0"),
        ("unit_price", "-1"),
        ("unit_price", "1.23456"),
        ("unit_price", "abc"),
        ("currency", "EURO"),
        ("currency", "E1R"),
        ("min_order_quantity", "0"),
        ("lead_time_days", "366"),
        ("lead_time_days", "-1"),
        ("is_active", "maybe"),
        ("updated_at", "2026-10-30T12:00:00"),
        ("updated_at", "yesterday"),
        ("supplier_id", "SUP-1"),
    ],
)
def test_invalid_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as info:
        SupplierProduct.model_validate({**VALID, field: value})

    assert field in str(info.value)


def test_missing_required_fields_are_rejected() -> None:
    data = {k: v for k, v in VALID.items() if k != "category"}

    with pytest.raises(ValidationError, match="category"):
        SupplierProduct.model_validate(data)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="colour"):
        SupplierProduct.model_validate({**VALID, "colour": "red"})


def test_supplier_accepts_valid_data() -> None:
    supplier = Supplier(supplier_id="SUP-007", name="Alpine Components", country="LU")

    assert supplier.country == "LU"


@pytest.mark.parametrize(
    ("field", "value"),
    [("supplier_id", "SUP-1"), ("country", "lux"), ("name", "")],
)
def test_supplier_rejects_invalid_data(field: str, value: str) -> None:
    data = {"supplier_id": "SUP-007", "name": "Alpine", "country": "LU", field: value}

    with pytest.raises(ValidationError, match=field):
        Supplier.model_validate(data)
