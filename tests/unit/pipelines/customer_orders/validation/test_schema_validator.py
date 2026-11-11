import pytest

from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS
from agpp.pipelines.customer_orders.validation.schema_validator import validate_schema
from agpp.shared.exceptions import SchemaValidationError


def test_a_complete_header_passes() -> None:
    assert validate_schema(REQUIRED_COLUMNS, "orders.csv") == ()


def test_column_order_does_not_matter() -> None:
    assert validate_schema(tuple(reversed(REQUIRED_COLUMNS)), "orders.csv") == ()


def test_missing_columns_raise_with_their_names() -> None:
    columns = tuple(name for name in REQUIRED_COLUMNS if name not in {"status", "quantity"})

    with pytest.raises(SchemaValidationError) as info:
        validate_schema(columns, "orders.csv")

    assert info.value.context == {"source": "orders.csv", "missing_columns": ["quantity", "status"]}


def test_an_empty_header_raises() -> None:
    with pytest.raises(SchemaValidationError, match="missing required columns"):
        validate_schema((), "orders.csv")


def test_extra_columns_are_reported_not_rejected() -> None:
    assert validate_schema((*REQUIRED_COLUMNS, "color", ""), "orders.csv") == ("color",)
