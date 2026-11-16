from agpp.pipelines.inventory.models import InventoryItem
from agpp.pipelines.inventory.validation.duplicate_detector import remove_duplicates
from agpp.pipelines.inventory.validation.result import ParsedItem, RejectionStage

VALUES = {
    "location_code": "LU-01",
    "location_name": "Luxembourg Warehouse",
    "location_country": "LU",
    "product_id": "SUP-001:S1-00012",
    "on_hand": "120",
    "reserved": "20",
    "reorder_point": "50",
    "updated_at": "2026-11-13T05:30:00Z",
}


def _item(position: int, **overrides: str) -> ParsedItem:
    return ParsedItem(position, {}, InventoryItem.model_validate({**VALUES, **overrides}))


def test_distinct_items_pass_through_in_order() -> None:
    items = [
        _item(1),
        _item(2, location_code="LU-02"),
        _item(3, product_id="SUP-001:S1-00013"),
    ]

    unique, rejected = remove_duplicates(items, source_id="feed")

    assert [item.line_number for item in unique] == [1, 2, 3]
    assert rejected == []


def test_the_latest_update_wins() -> None:
    older = _item(1, updated_at="2026-11-13T04:00:00Z")
    newer = _item(2, updated_at="2026-11-13T05:00:00Z", on_hand="99")

    unique, rejected = remove_duplicates([newer, older], source_id="feed")

    assert unique == [newer]
    assert rejected[0].line_number == 1
    assert rejected[0].stage is RejectionStage.DUPLICATE
    assert rejected[0].reasons == ("location_code: duplicate of item 2, which was kept",)


def test_on_a_tie_the_later_item_wins() -> None:
    first = _item(1)
    second = _item(5)

    unique, rejected = remove_duplicates([first, second], source_id="feed")

    assert unique == [second]
    assert rejected[0].line_number == 1


def test_three_copies_leave_exactly_one() -> None:
    items = [
        _item(1, updated_at="2026-11-13T04:00:00Z"),
        _item(2, updated_at="2026-11-13T05:30:00Z"),
        _item(3, updated_at="2026-11-13T05:00:00Z"),
    ]

    unique, rejected = remove_duplicates(items, source_id="feed")

    assert [item.line_number for item in unique] == [2]
    assert sorted(r.line_number for r in rejected) == [1, 3]
