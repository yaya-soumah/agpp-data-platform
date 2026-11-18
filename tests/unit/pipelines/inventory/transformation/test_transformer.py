from datetime import UTC, datetime

import pytest

from agpp.pipelines.inventory.models import InventoryItem
from agpp.pipelines.inventory.transformation import to_rows, transform_inventory
from agpp.pipelines.inventory.validation import ValidationResult
from agpp.shared.exceptions import TransformationError

SNAPSHOT = datetime(2026, 11, 13, 23, 30, tzinfo=UTC)
VALUES = {
    "location_code": "LU-01",
    "location_name": "Luxembourg Warehouse",
    "location_country": "LU",
    "product_id": "SUP-001:S1-00012",
    "on_hand": "120",
    "reserved": "20",
    "reorder_point": "50",
    "updated_at": "2026-11-13T22:00:00Z",
}


def _item(**overrides: str) -> InventoryItem:
    return InventoryItem.model_validate({**VALUES, **overrides})


def test_an_item_is_mapped_to_a_snapshot_row() -> None:
    row = to_rows(SNAPSHOT, [_item()]).rows[0]

    assert (row.location_code, row.product_id) == ("LU-01", "SUP-001:S1-00012")
    assert (row.on_hand, row.reserved, row.available, row.reorder_point) == (120, 20, 100, 50)
    assert row.below_reorder_point is False
    assert row.source_updated_at == datetime(2026, 11, 13, 22, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("on_hand", "reserved", "reorder_point", "expected"),
    [("120", "20", "100", False), ("120", "20", "101", True), ("0", "0", "1", True)],
)
def test_the_reorder_flag_follows_the_available_stock(
    on_hand: str, reserved: str, reorder_point: str, expected: bool
) -> None:
    item = _item(on_hand=on_hand, reserved=reserved, reorder_point=reorder_point)

    assert to_rows(SNAPSHOT, [item]).rows[0].below_reorder_point is expected


def test_the_date_key_is_the_utc_date_of_the_snapshot() -> None:
    late = datetime(2026, 11, 14, 0, 30, tzinfo=UTC)

    assert to_rows(SNAPSHOT, []).date_key == 20261113
    assert to_rows(late, []).date_key == 20261114


def test_the_snapshot_time_is_carried_through() -> None:
    assert to_rows(SNAPSHOT, [_item()]).snapshot_at == SNAPSHOT


def test_locations_are_distinct_and_sorted() -> None:
    items = [
        _item(location_code="LU-02", product_id="SUP-001:A"),
        _item(location_code="LU-01", product_id="SUP-001:A"),
        _item(location_code="LU-02", product_id="SUP-001:B"),
    ]

    transformed = to_rows(SNAPSHOT, items)

    assert [loc.location_code for loc in transformed.locations] == ["LU-01", "LU-02"]
    assert len(transformed.rows) == 3


def test_a_location_takes_its_details_from_its_latest_item() -> None:
    items = [
        _item(
            product_id="SUP-001:A", location_name="Old   Name", updated_at="2026-11-13T10:00:00Z"
        ),
        _item(product_id="SUP-001:B", location_name="New Name", updated_at="2026-11-13T12:00:00Z"),
        _item(product_id="SUP-001:C", location_name="Middle", updated_at="2026-11-13T11:00:00Z"),
    ]

    location = to_rows(SNAPSHOT, items).locations[0]

    assert location.location_name == "New Name"
    assert location.source_updated_at == datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


def test_transformation_is_deterministic() -> None:
    items = [_item(product_id="SUP-001:A"), _item(product_id="SUP-001:B")]

    assert to_rows(SNAPSHOT, items) == to_rows(SNAPSHOT, items)


def test_an_empty_feed_gives_no_rows() -> None:
    transformed = to_rows(SNAPSHOT, [])

    assert transformed.locations == ()
    assert transformed.rows == ()


def test_a_repeated_stock_item_is_rejected() -> None:
    with pytest.raises(TransformationError, match="Duplicate stock item"):
        to_rows(SNAPSHOT, [_item(), _item()])


def test_the_stage_transforms_the_valid_items() -> None:
    result = ValidationResult(
        source_id="feed",
        snapshot_at=SNAPSHOT,
        rows_read=2,
        valid=(_item(product_id="SUP-001:A"), _item(product_id="SUP-001:B", on_hand="1")),
        rejected=(),
    )

    transformed = transform_inventory(result, run_id="run-1")

    assert len(transformed.rows) == 2
    assert transformed.date_key == 20261113
