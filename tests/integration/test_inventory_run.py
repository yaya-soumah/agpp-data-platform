from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, LiteralString

import pytest

import agpp.pipelines.inventory.service as service_module
from agpp.pipelines.inventory.config import InventoryConfig
from agpp.pipelines.inventory.mock_feed import FeedState, MockFeed
from agpp.pipelines.inventory.sample_data import SampleFeed, generate_feed
from agpp.pipelines.inventory.service import RunSummary, run_inventory
from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import (
    ExtractionError,
    InvalidSnapshotError,
    QualityThresholdExceededError,
)
from agpp.shared.runs import RunStatus

FIRST_SNAPSHOT = datetime(2026, 11, 14, 6, 0, tzinfo=UTC)
LATER_SNAPSHOT = datetime(2026, 11, 14, 18, 0, tzinfo=UTC)
NEXT_DAY_SNAPSHOT = datetime(2026, 11, 15, 6, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 14, 7, 0, tzinfo=UTC)
LATER_NOW = datetime(2026, 11, 14, 19, 0, tzinfo=UTC)
NEXT_DAY_NOW = datetime(2026, 11, 15, 7, 0, tzinfo=UTC)
PRODUCTS = [f"SUP-001:S1-{number:05d}" for number in range(1, 21)]


def _no_sleep(_seconds: float) -> None:
    return None


def _sample(snapshot_at: datetime = FIRST_SNAPSHOT, bad: float = 0.02) -> SampleFeed:
    return generate_feed(
        PRODUCTS,
        locations=3,
        coverage=0.8,
        bad_item_ratio=bad,
        unknown_product_ratio=0.2,
        seed=5,
        snapshot_at=snapshot_at,
    )


def _serve(state: FeedState, sample: SampleFeed) -> None:
    state.snapshot_at = sample.snapshot_at
    state.items = sample.items


@pytest.fixture
def feed_state() -> FeedState:
    sample = _sample()
    return FeedState(snapshot_at=sample.snapshot_at, items=sample.items)


@pytest.fixture
def feed(feed_state: FeedState) -> Iterator[MockFeed]:
    with MockFeed(feed_state) as running:
        yield running


def _config(feed: MockFeed, token: str | None = None, path: str = "/v1/stock") -> InventoryConfig:
    source: dict[str, Any] = {
        "type": "api",
        "base_url": feed.base_url,
        "path": path,
        "page_size": 25,
    }
    if token is not None:
        source["token"] = token
    return InventoryConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "max_snapshot_age_hours": 26,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 3, "initial_delay_seconds": 0},
            "loading": {"max_attempts": 3, "initial_delay_seconds": 0},
            "source": source,
        }
    )


def _run(
    pool: Pool, config: InventoryConfig, run_id: str = "run-1", now: datetime = NOW
) -> RunSummary:
    return run_inventory(pool, config, run_id=run_id, now=now, sleep=_no_sleep)


def _seed_products(pool: Pool, product_ids: list[str]) -> None:
    """Insert products the way the Supplier Product pipeline would have."""
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.dim_supplier (supplier_id, supplier_name, country)"
            " VALUES ('SUP-001', 'Alpine Components', 'LU') ON CONFLICT (supplier_id) DO NOTHING"
        )
        for product_id in product_ids:
            conn.execute(
                "INSERT INTO warehouse.dim_product (product_id, supplier_key, supplier_sku,"
                " product_name, category, unit_price, currency, min_order_quantity,"
                " lead_time_days, is_active, source_updated_at)"
                " SELECT %s, supplier_key, %s, 'Hex Bolt', 'Fasteners', 10, 'EUR', 1, 5, true,"
                " now() FROM warehouse.dim_supplier WHERE supplier_id = 'SUP-001'",
                (product_id, product_id.split(":", 1)[1]),
            )


def _scalar(pool: Pool, query: LiteralString) -> Any:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


def _snapshot(pool: Pool) -> list[tuple[Any, ...]]:
    with connection(pool) as conn:
        return conn.execute(
            "SELECT * FROM warehouse.fact_inventory_snapshot ORDER BY date_key, location_key,"
            " product_id"
        ).fetchall()


def test_a_first_run_loads_the_snapshot_over_http(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    _seed_products(warehouse, PRODUCTS)

    summary = _run(warehouse, _config(feed))

    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load is not None
    load = summary.load
    assert len(feed_state.requests) >= 2  # the feed has more than one page
    assert load.rows_attempted + load.rejects_stored == len(feed_state.items)
    assert load.unknown_product_rows > 0
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot") == (
        load.rows_written
    )
    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "succeeded"
    assert _scalar(warehouse, "SELECT status FROM operational.inventory_run_results") == "loaded"


def test_running_the_pipeline_twice_leaves_the_warehouse_unchanged(
    warehouse: Pool, feed: MockFeed
) -> None:
    _seed_products(warehouse, PRODUCTS)
    first = _run(warehouse, _config(feed), "run-1")
    before = _snapshot(warehouse)

    second = _run(warehouse, _config(feed), "run-2")

    assert second.status is RunStatus.SUCCEEDED
    assert second.load is not None
    assert first.load is not None
    assert second.load.rows_written == 0
    assert second.load.rows_unchanged == first.load.rows_written
    assert _snapshot(warehouse) == before


def test_a_later_snapshot_replaces_the_day_and_an_older_one_cannot_overwrite_it(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    _seed_products(warehouse, PRODUCTS)
    first = _run(warehouse, _config(feed), "run-1")
    count = _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot")
    assert first.load is not None

    _serve(feed_state, _sample(LATER_SNAPSHOT))
    later = _run(warehouse, _config(feed), "run-2", LATER_NOW)

    assert later.load is not None
    assert later.load.rows_written == first.load.rows_written
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot") == count

    _serve(feed_state, _sample(FIRST_SNAPSHOT))
    stale = _run(warehouse, _config(feed), "run-3", LATER_NOW)

    assert stale.load is not None
    assert stale.load.rows_written == 0


def test_the_next_day_adds_rows_and_keeps_the_history(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    _seed_products(warehouse, PRODUCTS)
    _run(warehouse, _config(feed), "run-1")
    count = _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot")

    _serve(feed_state, _sample(NEXT_DAY_SNAPSHOT))
    summary = _run(warehouse, _config(feed), "run-2", NEXT_DAY_NOW)

    assert summary.status is RunStatus.SUCCEEDED
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot") == 2 * count
    assert (
        _scalar(warehouse, "SELECT count(DISTINCT date_key) FROM warehouse.fact_inventory_snapshot")
        == 2
    )


def test_unknown_products_are_healed_when_the_catalog_arrives(
    warehouse: Pool, feed: MockFeed
) -> None:
    _seed_products(warehouse, PRODUCTS[:10])
    first = _run(warehouse, _config(feed), "run-1")
    assert first.load is not None
    unknown = _scalar(
        warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot WHERE product_key = -1"
    )
    assert unknown >= first.load.unknown_product_rows > 0

    _seed_products(warehouse, PRODUCTS[10:])
    second = _run(warehouse, _config(feed), "run-2")

    assert second.load is not None
    healed = unknown - _scalar(
        warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot WHERE product_key = -1"
    )
    assert healed == second.load.rows_written > 0


def test_a_temporary_outage_is_retried(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    feed_state.fail_next = 2

    summary = _run(warehouse, _config(feed))

    assert summary.status is RunStatus.SUCCEEDED
    assert feed_state.fail_next == 0
    assert len(feed_state.requests) > 2


def test_a_feed_that_changes_between_pages_is_read_again(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    second_page_reads = {"count": 0}
    original = feed_state.snapshot_at

    def snapshot_for_page(page: int) -> str:
        if page == 2:
            second_page_reads["count"] += 1
            if second_page_reads["count"] == 1:
                return "2026-11-14T06:05:00Z"
        return original

    feed_state.snapshot_for_page = snapshot_for_page

    summary = _run(warehouse, _config(feed))

    assert summary.status is RunStatus.SUCCEEDED
    assert second_page_reads["count"] == 2


def test_a_stale_snapshot_fails_the_run_and_loads_nothing(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    feed_state.snapshot_at = "2026-11-10T06:00:00Z"

    summary = _run(warehouse, _config(feed))

    assert summary.status is RunStatus.FAILED
    assert isinstance(summary.error, InvalidSnapshotError)
    assert (
        _scalar(warehouse, "SELECT failed_stage FROM operational.inventory_run_results")
        == "validation"
    )
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot") == 0


def test_a_wrong_token_fails_once_without_retrying_and_without_leaking_it(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    feed_state.token = "s3cret"  # noqa: S105

    summary = _run(warehouse, _config(feed, token="wrong-token"))  # noqa: S106

    assert summary.status is RunStatus.FAILED
    assert isinstance(summary.error, ExtractionError)
    assert len(feed_state.requests) == 1
    assert "wrong-token" not in str(summary.error)
    assert (
        _scalar(warehouse, "SELECT failed_stage FROM operational.inventory_run_results")
        == "extraction"
    )


def test_the_right_token_is_accepted(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    feed_state.token = "s3cret"  # noqa: S105

    assert _run(warehouse, _config(feed, token="s3cret")).status is RunStatus.SUCCEEDED  # noqa: S106


def test_a_wrong_path_fails_the_run(warehouse: Pool, feed: MockFeed) -> None:
    summary = _run(warehouse, _config(feed, path="/v2/stock"))

    assert summary.status is RunStatus.FAILED
    assert isinstance(summary.error, ExtractionError)


def test_a_feed_that_fails_the_quality_gate_loads_nothing(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    _serve(feed_state, _sample(bad=0.5))

    summary = _run(warehouse, _config(feed))

    assert summary.status is RunStatus.FAILED
    assert isinstance(summary.error, QualityThresholdExceededError)
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_inventory_snapshot") == 0


def test_an_empty_feed_is_a_valid_run(
    warehouse: Pool, feed: MockFeed, feed_state: FeedState
) -> None:
    feed_state.items = []

    summary = _run(warehouse, _config(feed))

    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load is not None
    assert summary.load.rows_attempted == 0


def test_an_unexpected_error_marks_the_run_failed_and_propagates(
    warehouse: Pool, feed: MockFeed, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(service_module, "extract_inventory", broken)

    with pytest.raises(RuntimeError, match="bug"):
        _run(warehouse, _config(feed))

    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "failed"
