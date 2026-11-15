from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agpp.pipelines.inventory.models import InventoryItem, Location

VALUES = {
    "location_code": "lu-01",
    "location_name": "  Luxembourg Warehouse ",
    "location_country": "lu",
    "product_id": " sup-001:s1-00012 ",
    "on_hand": "120",
    "reserved": "20",
    "reorder_point": "50",
    "updated_at": "2026-11-13T07:00:00+01:00",
}


def test_text_values_are_converted_to_types() -> None:
    item = InventoryItem.model_validate(VALUES)

    assert (item.on_hand, item.reserved, item.reorder_point) == (120, 20, 50)


def test_values_are_normalized() -> None:
    item = InventoryItem.model_validate(VALUES)

    assert item.location_code == "LU-01"
    assert item.location_name == "Luxembourg Warehouse"
    assert item.location_country == "LU"
    assert item.product_id == "SUP-001:S1-00012"


def test_the_timestamp_is_converted_to_utc() -> None:
    item = InventoryItem.model_validate(VALUES)

    assert item.updated_at == datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
    assert item.updated_at.tzinfo is UTC


def test_available_stock_is_on_hand_minus_reserved() -> None:
    assert InventoryItem.model_validate(VALUES).available == 100


@pytest.mark.parametrize(
    ("available_overrides", "expected"),
    [
        ({"on_hand": "120", "reserved": "20", "reorder_point": "50"}, False),
        ({"on_hand": "120", "reserved": "20", "reorder_point": "100"}, False),
        ({"on_hand": "120", "reserved": "20", "reorder_point": "101"}, True),
        ({"on_hand": "0", "reserved": "0", "reorder_point": "1"}, True),
    ],
)
def test_below_reorder_point(available_overrides: dict[str, str], expected: bool) -> None:
    item = InventoryItem.model_validate({**VALUES, **available_overrides})

    assert item.below_reorder_point is expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("location_code", "LUX-1"),
        ("location_code", "L-01"),
        ("location_name", " "),
        ("location_country", "LUX"),
        ("product_id", "A-1"),
        ("product_id", "SUP-1:A-1"),
        ("on_hand", "-1"),
        ("on_hand", "1000001"),
        ("on_hand", "abc"),
        ("reserved", "-1"),
        ("reorder_point", "-5"),
        ("updated_at", "2026-11-13T07:00:00"),
        ("updated_at", "yesterday"),
    ],
)
def test_invalid_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as info:
        InventoryItem.model_validate({**VALUES, field: value})

    assert field in str(info.value)


def test_missing_and_unknown_fields_are_rejected() -> None:
    data = {k: v for k, v in VALUES.items() if k != "reserved"}

    with pytest.raises(ValidationError, match="reserved"):
        InventoryItem.model_validate(data)
    with pytest.raises(ValidationError, match="colour"):
        InventoryItem.model_validate({**VALUES, "colour": "red"})


def test_a_location_accepts_valid_data() -> None:
    location = Location(location_code="LU-01", name="Luxembourg Warehouse", country="LU")

    assert location.name == "Luxembourg Warehouse"


@pytest.mark.parametrize(
    ("field", "value"),
    [("location_code", "LUX-1"), ("country", "lux"), ("name", "")],
)
def test_a_location_rejects_invalid_data(field: str, value: str) -> None:
    data = {"location_code": "LU-01", "name": "Warehouse", "country": "LU", field: value}

    with pytest.raises(ValidationError, match=field):
        Location.model_validate(data)
