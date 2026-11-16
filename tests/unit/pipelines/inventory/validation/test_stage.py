import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from agpp.pipelines.inventory.config import InventoryConfig, QualityConfig
from agpp.pipelines.inventory.extraction import InventoryExtraction, extract_inventory
from agpp.pipelines.inventory.validation import RejectionStage, validate_inventory
from agpp.pipelines.inventory.validation.schema import REQUIRED_COLUMNS
from agpp.shared.exceptions import (
    InvalidSnapshotError,
    QualityThresholdExceededError,
    SchemaValidationError,
)
from agpp.shared.extraction import RawRecord

NOW = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)
SNAPSHOT = "2026-11-13T06:00:00Z"
QUALITY = QualityConfig(
    max_reject_ratio=0.15, max_snapshot_age_hours=26, future_tolerance_minutes=5
)
GOOD = {
    "location_code": "LU-01",
    "location_name": "Luxembourg Warehouse",
    "location_country": "LU",
    "product_id": "SUP-001:S1-00000",
    "on_hand": "120",
    "reserved": "20",
    "reorder_point": "50",
    "updated_at": "2026-11-13T05:30:00Z",
}


def _rows(count: int) -> list[dict[str, str]]:
    return [{**GOOD, "product_id": f"SUP-001:S1-{index:05d}"} for index in range(count)]


def _extraction(
    rows: list[dict[str, str]],
    snapshot: str = SNAPSHOT,
    columns: tuple[str, ...] = REQUIRED_COLUMNS,
) -> InventoryExtraction:
    records = tuple(RawRecord(index + 1, row) for index, row in enumerate(rows))
    return InventoryExtraction(
        "https://stock.test/v1/stock", snapshot, 1, columns if rows else (), records
    )


def _validate(extraction: InventoryExtraction, run_id: str = "run-1") -> Any:
    return validate_inventory(extraction, QUALITY, run_id=run_id, now=NOW)


def test_a_clean_feed_is_fully_valid() -> None:
    result = _validate(_extraction(_rows(20)))

    assert result.rows_read == 20
    assert len(result.valid) == 20
    assert result.rejected == ()
    assert result.snapshot_at == datetime(2026, 11, 13, 6, 0, tzinfo=UTC)


def test_rejects_from_every_check_are_collected_in_position_order() -> None:
    rows = _rows(40)
    rows[1] = {**rows[1], "on_hand": "x"}  # parsing, item 2
    rows[10] = {**rows[10], "reserved": "500"}  # business, item 11
    rows[20] = {  # an older copy of item 1, so item 21 is the duplicate that is rejected
        **rows[20],
        "product_id": rows[0]["product_id"],
        "updated_at": "2026-11-13T04:00:00Z",
    }
    rows[30] = {**rows[30], "on_hand": "x", "reorder_point": "-1"}  # parsing, item 31

    result = _validate(_extraction(rows))

    assert [r.line_number for r in result.rejected] == [2, 11, 21, 31]
    assert result.rejected_by(RejectionStage.PARSING) == 2
    assert result.rejected_by(RejectionStage.BUSINESS) == 1
    assert result.rejected_by(RejectionStage.DUPLICATE) == 1
    assert len(result.valid) == 36


def test_extra_fields_are_ignored_and_reported() -> None:
    rows = [{**row, "color": "red"} for row in _rows(5)]

    result = _validate(_extraction(rows, columns=(*REQUIRED_COLUMNS, "color")))

    assert result.ignored_columns == ("color",)
    assert len(result.valid) == 5


def test_a_missing_field_stops_the_feed() -> None:
    columns = tuple(name for name in REQUIRED_COLUMNS if name != "reserved")

    with pytest.raises(SchemaValidationError):
        _validate(_extraction(_rows(3), columns=columns))


def test_too_many_rejects_fail_the_quality_gate() -> None:
    rows = _rows(10)
    rows[0] = {**rows[0], "on_hand": "x"}
    rows[1] = {**rows[1], "on_hand": "x"}

    with pytest.raises(QualityThresholdExceededError):
        _validate(_extraction(rows))


@pytest.mark.parametrize(
    "snapshot", ["2026-11-10T06:00:00Z", "2026-11-14T06:00:00Z", "2026-11-13T06:00:00", "nope"]
)
def test_a_stale_future_or_unreadable_snapshot_stops_the_feed(snapshot: str) -> None:
    with pytest.raises(InvalidSnapshotError):
        _validate(_extraction(_rows(3), snapshot=snapshot))


def test_an_empty_feed_is_valid_and_produces_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = _validate(_extraction([]))

    assert (result.rows_read, result.valid, result.rejected) == (0, (), ())
    assert "no items" in caplog.text


def test_log_records_carry_the_run_context(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _validate(_extraction(_rows(5)), run_id="run-9")

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-9" for item in fields)
    assert "Inventory validated" in caplog.text


def test_a_real_feed_flows_from_extraction_to_validation() -> None:
    items = [
        {
            "location_code": "lu-01",
            "location_name": "Luxembourg Warehouse",
            "location_country": "LU",
            "product_id": f"sup-001:s1-{index:05d}",
            "on_hand": 100 + index,
            "reserved": index,
            "reorder_point": 50,
            "updated_at": "2026-11-13T05:30:00Z",
        }
        for index in range(30)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        chunk = items[(page - 1) * 10 : page * 10]
        return httpx.Response(
            200,
            json={
                "snapshot_at": SNAPSHOT,
                "items": chunk,
                "next_page": page + 1 if page < 3 else None,
            },
        )

    config = InventoryConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.15,
                "max_snapshot_age_hours": 26,
                "future_tolerance_minutes": 5,
            },
            "source": {"type": "api", "base_url": "https://stock.test", "path": "/v1/stock"},
        }
    )
    client = httpx.Client(base_url="https://stock.test", transport=httpx.MockTransport(handler))

    extraction = extract_inventory(config, run_id="run-1", client=client)
    result = validate_inventory(extraction, config.quality, run_id="run-1", now=NOW)

    assert extraction.pages == 3
    assert len(result.valid) == 30
    assert result.rejected == ()
    assert result.valid[0].product_id == "SUP-001:S1-00000"
