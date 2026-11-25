"""Load all three pipelines into one warehouse, for end-to-end tests."""

from datetime import datetime, timedelta
from pathlib import Path

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
from agpp.shared.database import Pool
from agpp.shared.runs import RunStatus


def no_sleep(_seconds: float) -> None:
    return None


def inventory_config(base_url: str) -> InventoryConfig:
    return InventoryConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "max_snapshot_age_hours": 26,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "source": {
                "type": "api",
                "base_url": base_url,
                "path": "/v1/stock",
                "page_size": 40,
            },
        }
    )


def load_platform(pool: Pool, tmp_path: Path, now: datetime) -> list[str]:
    """Run the three pipelines, with all data dated relative to ``now``.

    Returns the product ids that were loaded.
    """
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
        supplier_config, rows_per_supplier=60, bad_row_ratio=0.0, seed=3, now=now
    )
    supplier = run_supplier_product(
        pool, supplier_config, run_id="supplier-run", now=now, sleep=no_sleep
    )
    assert supplier.status is RunStatus.SUCCEEDED
    product_ids = known_product_ids(pool)

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
        now=now,
    )
    orders = run_customer_orders(pool, orders_config, run_id="orders-run", now=now, sleep=no_sleep)
    assert orders.status is RunStatus.SUCCEEDED

    sample = generate_feed(
        product_ids,
        locations=3,
        coverage=0.8,
        bad_item_ratio=0.0,
        unknown_product_ratio=0.0,
        seed=5,
        snapshot_at=now - timedelta(hours=1),
    )
    with MockFeed(FeedState(snapshot_at=sample.snapshot_at, items=sample.items)) as feed:
        inventory = run_inventory(
            pool, inventory_config(feed.base_url), run_id="inventory-run", now=now, sleep=no_sleep
        )
    assert inventory.status is RunStatus.SUCCEEDED
    return product_ids
