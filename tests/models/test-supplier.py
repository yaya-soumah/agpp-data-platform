import pytest
from pydantic import ValidationError

from src.models import Supplier


def test_supplier_can_be_created_with_required_fields() -> None:
    supplier = Supplier(
        supplier_id="SUP-001",
        name="ABC Trading",
        country="CN",
    )

    assert supplier.supplier_id == "SUP-001"
    assert supplier.name == "ABC Trading"
    assert supplier.country == "CN"
    assert supplier.address is None
    assert supplier.email is None
    assert supplier.phone is None
    assert supplier.website is None


def test_supplier_accepts_optional_fields() -> None:
    supplier = Supplier(
        supplier_id="SUP-001",
        name="ABC Trading",
        country="CN",
        address="Shanghai, China",
        email="contact@example.com",
        phone="+86 123456789",
        website="https://example.com",
    )

    assert supplier.address == "Shanghai, China"
    assert str(supplier.email) == "contact@example.com"
    assert supplier.phone == "+86 123456789"
    assert str(supplier.website) == "https://example.com/"


def test_supplier_requires_supplier_id() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            name="ABC Trading",
            country="CN",
        )


def test_supplier_requires_name() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            supplier_id="SUP-001",
            country="CN",
        )


def test_supplier_rejects_empty_supplier_id() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            supplier_id="",
            name="ABC Trading",
            country="CN",
        )


def test_supplier_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            supplier_id="SUP-001",
            name="",
            country="CN",
        )


def test_supplier_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            supplier_id="SUP-001",
            name="ABC Trading",
            country="CN",
            email="not-an-email",
        )


def test_supplier_rejects_invalid_website() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            supplier_id="SUP-001",
            name="ABC Trading",
            country="CN",
            website="not-a-url",
        )


def test_supplier_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            supplier_id="SUP-001",
            name="ABC Trading",
            country="CN",
            unknown_field="unexpected",
        )


def test_supplier_validates_assignment() -> None:
    supplier = Supplier(
        supplier_id="SUP-001",
        name="ABC Trading",
        country="CN",
    )

    with pytest.raises(ValidationError):
        supplier.name = ""


def test_supplier_allows_valid_assignment() -> None:
    supplier = Supplier(
        supplier_id="SUP-001",
        name="ABC Trading",
        country="CN",
    )

    supplier.name = "ABC International Trading"

    assert supplier.name == "ABC International Trading"