"""Extraction stage: read the stock feed (ADR-0011, ADR-0018)."""

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from agpp.pipelines.inventory import PIPELINE_NAME
from agpp.pipelines.inventory.config import InventoryConfig
from agpp.shared.exceptions import ExtractionError, SourceUnavailableError
from agpp.shared.extraction import ApiSource, RawRecord, read_api
from agpp.shared.logging import get_pipeline_logger
from agpp.shared.resilience.retry import call_with_retry


@dataclass(frozen=True)
class InventoryExtraction:
    """The records of one consistent read of the feed.

    ``snapshot_at`` is the text the feed reported; validation parses and checks it.
    ``source_id`` is the feed address without query or credentials.
    """

    source_id: str
    snapshot_at: str
    pages: int
    columns: tuple[str, ...]
    records: tuple[RawRecord, ...]


def extract_inventory(
    config: InventoryConfig,
    *,
    run_id: str,
    sleep: Callable[[float], None] = time.sleep,
    client: httpx.Client | None = None,
) -> InventoryExtraction:
    """Read the whole feed, retrying while it is unavailable or changing.

    There is one feed per run, so failures are raised: ``SourceUnavailableError``
    once the attempts are used up, ``ExtractionError`` for a malformed feed. A
    ``client`` can be passed in to avoid real network access in tests.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    source = config.source
    source_id = f"{source.base_url.rstrip('/')}{source.path}"
    log.info("Extraction started", extra={"source": source_id})

    extraction = call_with_retry(
        lambda: _read_once(source, source_id, client), config.extraction.policy(), sleep=sleep
    )
    log.info(
        "Inventory extracted",
        extra={
            "source": source_id,
            "rows": len(extraction.records),
            "pages": extraction.pages,
            "snapshot_at": extraction.snapshot_at,
        },
    )
    return extraction


def _read_once(
    source: ApiSource, source_id: str, client: httpx.Client | None
) -> InventoryExtraction:
    content = read_api(source, client=client, context={"pipeline": PIPELINE_NAME})
    snapshots = [page.get("snapshot_at") for page in content.pages]
    if any(not isinstance(value, str) or not value.strip() for value in snapshots):
        raise ExtractionError(
            "Every feed page must report snapshot_at", context={"source": source_id}
        )
    distinct = sorted({str(value) for value in snapshots})
    if len(distinct) != 1:
        raise SourceUnavailableError(
            "The feed changed while it was being read",
            context={"source": source_id, "snapshots": distinct},
        )
    return InventoryExtraction(
        source_id=source_id,
        snapshot_at=distinct[0],
        pages=len(content.pages),
        columns=content.columns,
        records=content.records,
    )
