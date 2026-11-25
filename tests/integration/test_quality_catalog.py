from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, LiteralString

import pytest

from agpp.pipelines.inventory.mock_feed import FeedState, MockFeed
from agpp.pipelines.inventory.sample_data import generate_feed
from agpp.pipelines.inventory.service import run_inventory
from agpp.shared.configuration.service import load_pipeline_config
from agpp.shared.database import Pool, connection
from agpp.shared.quality import (
    CheckResult,
    CheckStatus,
    QualityConfig,
    QualitySummary,
    run_quality_checks,
)
from agpp.shared.runs import RunStatus
from tests.integration.platform_setup import inventory_config, load_platform, no_sleep

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture
def catalog(tmp_path: Path) -> QualityConfig:
    env_file = tmp_path / "empty.env"
    env_file.write_text("", encoding="utf-8")
    return load_pipeline_config(CONFIG_DIR, "data_quality", QualityConfig, env_file=env_file)


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _by_name(summary: QualitySummary) -> dict[str, CheckResult]:
    return {result.check.name: result for result in summary.results}


def _scalar(pool: Pool, query: LiteralString) -> Any:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


def test_the_catalog_is_safe_on_an_empty_warehouse(warehouse: Pool, catalog: QualityConfig) -> None:
    summary = run_quality_checks(warehouse, catalog, run_id="run-1")

    assert not summary.failed
    assert summary.count(CheckStatus.NO_DATA) > 0


def test_a_loaded_platform_has_no_failing_check(
    warehouse: Pool, catalog: QualityConfig, tmp_path: Path
) -> None:
    load_platform(warehouse, tmp_path, _now())

    summary = run_quality_checks(warehouse, catalog, run_id="run-1")
    results = _by_name(summary)

    assert not summary.failed
    assert results["order_lines_unknown_product_share"].value == 0.0
    assert results["inventory_unknown_product_share"].value == 0.0
    assert results["products_with_invalid_price"].value == 0.0
    assert results["inventory_last_run_failed"].value == 0.0
    assert results["order_last_run_failed"].value == 0.0
    snapshot_age = results["inventory_snapshot_age_hours"].value
    assert snapshot_age is not None
    assert snapshot_age < 3


def test_a_failed_run_is_reported_as_a_failed_check(
    warehouse: Pool, catalog: QualityConfig, tmp_path: Path
) -> None:
    now = _now()
    product_ids = load_platform(warehouse, tmp_path, now)
    stale = generate_feed(
        product_ids,
        locations=1,
        coverage=1.0,
        bad_item_ratio=0.0,
        unknown_product_ratio=0.0,
        seed=1,
        snapshot_at=now - timedelta(days=5),
    )
    with MockFeed(FeedState(snapshot_at=stale.snapshot_at, items=stale.items)) as feed:
        failed_run = run_inventory(
            warehouse, inventory_config(feed.base_url), run_id="stale-run", now=now, sleep=no_sleep
        )
    assert failed_run.status is RunStatus.FAILED

    summary = run_quality_checks(warehouse, catalog, run_id="run-2")

    assert summary.failed
    assert _by_name(summary)["inventory_last_run_failed"].status is CheckStatus.FAIL


def test_the_latest_view_has_one_row_per_check(warehouse: Pool, catalog: QualityConfig) -> None:
    run_quality_checks(warehouse, catalog, run_id="run-1")
    run_quality_checks(warehouse, catalog, run_id="run-2")

    assert _scalar(warehouse, "SELECT count(*) FROM operational.quality_check_results") == 2 * len(
        catalog.checks
    )
    assert _scalar(warehouse, "SELECT count(*) FROM operational.quality_latest") == len(
        catalog.checks
    )
    assert _scalar(warehouse, "SELECT min(run_id) FROM operational.quality_latest") == "run-2"
