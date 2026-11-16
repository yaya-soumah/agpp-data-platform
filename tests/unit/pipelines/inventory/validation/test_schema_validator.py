import pytest

from agpp.pipelines.inventory.validation.schema import REQUIRED_COLUMNS
from agpp.pipelines.inventory.validation.schema_validator import validate_schema
from agpp.shared.exceptions import SchemaValidationError


def test_a_complete_set_of_fields_passes() -> None:
    assert validate_schema(REQUIRED_COLUMNS, "feed") == ()


def test_the_order_does_not_matter() -> None:
    assert validate_schema(tuple(reversed(REQUIRED_COLUMNS)), "feed") == ()


def test_missing_fields_raise_with_their_names() -> None:
    columns = tuple(name for name in REQUIRED_COLUMNS if name not in {"reserved", "on_hand"})

    with pytest.raises(SchemaValidationError) as info:
        validate_schema(columns, "feed")

    assert info.value.context == {"source": "feed", "missing_columns": ["on_hand", "reserved"]}


def test_extra_fields_are_reported_not_rejected() -> None:
    assert validate_schema((*REQUIRED_COLUMNS, "color", ""), "feed") == ("color",)
