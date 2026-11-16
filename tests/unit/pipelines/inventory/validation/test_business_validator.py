from datetime import UTC, datetime, timedelta

from agpp.pipelines.inventory.config import QualityConfig
from agpp.pipelines.inventory.models import InventoryItem
from agpp.pipelines.inventory.validation.business_validator import validate_business_rules
from agpp.pipelines.inventory.validation.result import ParsedItem, RejectionStage

SNAPSHOT = datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
QUALITY = QualityConfig(
    max_reject_ratio=0.05, max_snapshot_age_hours=26, future_tolerance_minutes=5
)
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


def _item(position: int = 1, **overrides: str) -> ParsedItem:
    return ParsedItem(position, {}, InventoryItem.model_validate({**VALUES, **overrides}))


def _validate(*items: ParsedItem):  # type: ignore[no-untyped-def]
    return validate_business_rules(items, QUALITY, source_id="feed", snapshot_at=SNAPSHOT)


def test_a_compliant_item_is_accepted() -> None:
    accepted, rejected = _validate(_item())

    assert len(accepted) == 1
    assert rejected == []


def test_reserved_stock_may_equal_but_not_exceed_what_is_on_hand() -> None:
    accepted, rejected = _validate(
        _item(1, on_hand="10", reserved="10"), _item(2, on_hand="10", reserved="11")
    )

    assert [r.line_number for r in accepted] == [1]
    assert [r.line_number for r in rejected] == [2]
    assert rejected[0].stage is RejectionStage.BUSINESS
    assert rejected[0].reasons == ("reserved: 11 exceeds on_hand 10",)


def test_items_newer_than_the_snapshot_beyond_the_tolerance_are_rejected() -> None:
    within = (SNAPSHOT + timedelta(minutes=4)).isoformat()
    beyond = (SNAPSHOT + timedelta(minutes=6)).isoformat()

    accepted, rejected = _validate(_item(1, updated_at=within), _item(2, updated_at=beyond))

    assert [r.line_number for r in accepted] == [1]
    assert "is after the snapshot" in rejected[0].reasons[0]


def test_every_violated_rule_is_reported() -> None:
    beyond = (SNAPSHOT + timedelta(hours=1)).isoformat()

    _, rejected = _validate(_item(on_hand="1", reserved="5", updated_at=beyond))

    assert len(rejected[0].reasons) == 2
