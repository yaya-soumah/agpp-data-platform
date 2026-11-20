from datetime import UTC, datetime
from pathlib import Path
from typing import Any, LiteralString

from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.sample_data import generate_orders_file, known_product_ids
from agpp.pipelines.customer_orders.service import run_customer_orders
from agpp.pipelines.inventory.config import InventoryConfig
from agpp.pipelines.inventory.mock_feed import FeedState, MockFeed
from agpp.pipelines.inventory.sample_data import generate_feed
from agpp.pipelines.inventory.service import run_inventory
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.sample_data import generate_supplier_files
from agpp.pipelines.supplier_product.service import run_supplier_product
from agpp.shared.database import Pool, connection
from agpp.shared.runs import RunStatus

NOW = datetime(2026, 11, 14, 7, 0, tzinfo=UTC)
SNAPSHOT_AT = datetime(2026, 11, 14, 6, 0, tzinfo=UTC)


def _no_sleep(_seconds: float) -> None:
    return None


def _scalar(pool: Pool, query: LiteralString) -> Any:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


def test_three_pipelines_share_one_warehouse(warehouse: Pool, tmp_path: Path) -> None:
    supplier_config = SupplierProductConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.1,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_unit_price": 1000000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "loading": {"max_attempts": 1, "initial_delay_seconds": 0},
            "suppliers": [
                {
                    "supplier_id": "SUP-001",
                    "name": "Alpine Components",
                    "country": "LU",
                    "source": {"type": "csv", "path": str(tmp_path / "suppliers.csv")},
                }
            ],
        }
    )
    generate_supplier_files(
        supplier_config, rows_per_supplier=60, bad_row_ratio=0.0, seed=3, now=NOW
    )
    supplier = run_supplier_product(
        warehouse, supplier_config, run_id="supplier-run", now=NOW, sleep=_no_sleep
    )
    assert supplier.status is RunStatus.SUCCEEDED
    product_ids = known_product_ids(warehouse)
    assert len(product_ids) == 60

    orders_config = CustomerOrdersConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_line_amount": 1000000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "source": {"type": "csv", "path": str(tmp_path / "orders.csv")},
        }
    )
    generate_orders_file(
        orders_config,
        product_ids=product_ids,
        lines=150,
        bad_row_ratio=0.0,
        unknown_product_ratio=0.0,
        seed=4,
        now=NOW,
    )
    orders = run_customer_orders(
        warehouse, orders_config, run_id="orders-run", now=NOW, sleep=_no_sleep
    )
    assert orders.status is RunStatus.SUCCEEDED

    sample = generate_feed(
        product_ids,
        locations=3,
        coverage=0.8,
        bad_item_ratio=0.0,
        unknown_product_ratio=0.0,
        seed=5,
        snapshot_at=SNAPSHOT_AT,
    )
    with MockFeed(FeedState(snapshot_at=sample.snapshot_at, items=sample.items)) as feed:
        inventory_config = InventoryConfig.model_validate(
            {
                "quality": {
                    "max_reject_ratio": 0.05,
                    "max_snapshot_age_hours": 26,
                    "future_tolerance_minutes": 5,
                },
                "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
                "source": {
                    "type": "api",
                    "base_url": feed.base_url,
                    "path": "/v1/stock",
                    "page_size": 40,
                },
            }
        )
        inventory = run_inventory(
            warehouse, inventory_config, run_id="inventory-run", now=NOW, sleep=_no_sleep
        )
    assert inventory.status is RunStatus.SUCCEEDED

    assert _scalar(warehouse, "SELECT count(DISTINCT pipeline) FROM operational.pipeline_runs") == 3
    assert (
        _scalar(
            warehouse, "SELECT count(*) FROM operational.pipeline_runs WHERE status <> 'succeeded'"
        )
        == 0
    )
    assert (
        _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line WHERE product_key = -1")
        == 0
    )
    assert (
        _scalar(
            warehouse,
            "SELECT count(*) FROM warehouse.fact_inventory_snapshot WHERE product_key = -1",
        )
        == 0
    )
    ordered_and_stocked = _scalar(
        warehouse,
        "SELECT count(*) FROM warehouse.dim_product AS p WHERE p.product_key > 0"
        " AND EXISTS (SELECT 1 FROM warehouse.fact_order_line AS o"
        " WHERE o.product_key = p.product_key)"
        " AND EXISTS (SELECT 1 FROM warehouse.fact_inventory_snapshot AS s"
        " WHERE s.product_key = p.product_key)",
    )
    assert ordered_and_stocked > 0
