"""Extraction stage: read the order-lines file (ADR-0011, ADR-0016)."""

import time
from collections.abc import Callable
from pathlib import Path

from agpp.pipelines.customer_orders import PIPELINE_NAME
from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.shared.extraction import CsvContent, read_csv
from agpp.shared.logging import get_pipeline_logger
from agpp.shared.resilience.retry import call_with_retry


def extract_orders(
    config: CustomerOrdersConfig,
    *,
    run_id: str,
    sleep: Callable[[float], None] = time.sleep,
) -> CsvContent:
    """Read the configured file, retrying while it is unavailable.

    There is one file per run, so failures are raised, not collected: an
    unreadable file raises ``SourceUnavailableError`` once the attempts are used
    up, and malformed content raises ``ExtractionError``.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    source = config.source
    path = Path(source.path)
    log.info("Extraction started", extra={"source": str(path)})

    content = call_with_retry(
        lambda: read_csv(
            path,
            delimiter=source.delimiter,
            encoding=source.encoding,
            context={"pipeline": PIPELINE_NAME},
        ),
        config.extraction.policy(),
        sleep=sleep,
    )
    log.info(
        "Orders extracted",
        extra={
            "source": str(path),
            "rows": len(content.records),
            "columns": len(content.columns),
        },
    )
    return content
