from datetime import UTC, datetime

import httpx
import pytest

from agpp.pipelines.inventory.config import InventoryConfig
from agpp.pipelines.inventory.extraction import extract_inventory
from agpp.pipelines.inventory.sample_data import SampleFeed, generate_feed
from agpp.pipelines.inventory.validation import validate_inventory
from agpp.pipelines.inventory.validation.schema import REQUIRED_COLUMNS

SNAPSHOT = datetime(2026, 11, 14, 6, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 14, 7, 0, tzinfo=UTC)
PRODUCTS = [f"SUP-001:S1-{number:05d}" for number in range(1, 11)]


def _feed(
    *,
    locations: int = 2,
    coverage: float = 1.0,
    bad: float = 0.0,
    unknown: float = 0.0,
    seed: int = 1,
    products: list[str] | None = None,
) -> SampleFeed:
    return generate_feed(
        PRODUCTS if products is None else products,
        locations=locations,
        coverage=coverage,
        bad_item_ratio=bad,
        unknown_product_ratio=unknown,
        seed=seed,
        snapshot_at=SNAPSHOT,
    )


def _config(max_reject_ratio: float = 1.0) -> InventoryConfig:
    return InventoryConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": max_reject_ratio,
                "max_snapshot_age_hours": 26,
                "future_tolerance_minutes": 5,
            },
            "source": {
                "type": "api",
                "base_url": "https://stock.test",
                "path": "/v1/stock",
                "page_size": 7,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
        }
    )


def _client(feed: SampleFeed) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        size = int(request.url.params["page_size"])
        start = (page - 1) * size
        return httpx.Response(
            200,
            json={
                "snapshot_at": feed.snapshot_at,
                "items": feed.items[start : start + size],
                "next_page": page + 1 if start + size < len(feed.items) else None,
            },
        )

    return httpx.Client(base_url="https://stock.test", transport=httpx.MockTransport(handler))


def _validate(feed: SampleFeed, max_reject_ratio: float = 1.0):  # type: ignore[no-untyped-def]
    config = _config(max_reject_ratio)
    extraction = extract_inventory(config, run_id="run-1", client=_client(feed))
    return validate_inventory(extraction, config.quality, run_id="run-1", now=NOW)


def test_every_location_stocks_every_product_at_full_coverage() -> None:
    assert len(_feed(locations=2).items) == 20


def test_a_lower_coverage_means_fewer_items() -> None:
    assert 0 < len(_feed(coverage=0.5).items) < 20


def test_the_snapshot_time_is_written_in_utc() -> None:
    assert _feed().snapshot_at == "2026-11-14T06:00:00Z"


def test_the_same_seed_gives_the_same_feed() -> None:
    assert _feed(seed=7).items == _feed(seed=7).items
    assert _feed(seed=7).items != _feed(seed=8).items


def test_items_carry_the_contract_fields_with_json_numbers() -> None:
    item = _feed().items[0]

    assert set(item) == set(REQUIRED_COLUMNS)
    assert all(isinstance(item[key], int) for key in ("on_hand", "reserved", "reorder_point"))


def test_a_clean_feed_passes_validation_completely() -> None:
    feed = _feed(locations=3, unknown=0.2)

    result = _validate(feed)

    assert len(result.valid) == len(feed.items)
    assert result.rejected == ()


def test_unknown_products_are_counted() -> None:
    feed = _feed(locations=4, unknown=0.3)

    unknown = [i for i in feed.items if i["product_id"].upper().startswith("SUP-999:")]

    assert len(unknown) == feed.unknown_product_items > 0
    assert _feed(unknown=0.0).unknown_product_items == 0


def test_defective_items_follow_the_ratio() -> None:
    assert _feed(locations=4, bad=0.1).defective_items == 4


def test_defects_are_caught_by_validation() -> None:
    feed = _feed(locations=4, bad=0.25)

    result = _validate(feed)

    assert 0 < len(result.rejected) <= feed.defective_items
    assert len(result.valid) + len(result.rejected) == len(feed.items)


@pytest.mark.parametrize(
    "arguments",
    [
        {"products": []},
        {"locations": 0},
        {"locations": 5},
        {"coverage": 0.0},
        {"coverage": 1.5},
        {"bad": -0.1},
        {"bad": 1.5},
        {"unknown": 1.5},
    ],
)
def test_invalid_arguments_are_rejected(arguments: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must"):
        _feed(**arguments)  # type: ignore[arg-type]
