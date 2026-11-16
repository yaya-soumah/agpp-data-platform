import logging
from typing import Any

import httpx
import pytest

from agpp.pipelines.inventory.config import InventoryConfig
from agpp.pipelines.inventory.extraction import extract_inventory
from agpp.shared.exceptions import ExtractionError, SourceUnavailableError

SNAPSHOT = "2026-11-13T06:00:00Z"


def _config(attempts: int = 3, delay: float = 0.5, token: str | None = None) -> InventoryConfig:
    source: dict[str, Any] = {
        "type": "api",
        "base_url": "https://stock.test",
        "path": "/v1/stock",
        "page_size": 2,
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
            "source": source,
            "extraction": {"max_attempts": attempts, "initial_delay_seconds": delay},
        }
    )


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(base_url="https://stock.test", transport=httpx.MockTransport(handler))


def _page(
    items: list[Any], snapshot: Any = SNAPSHOT, next_page: int | None = None
) -> httpx.Response:
    return httpx.Response(
        200, json={"snapshot_at": snapshot, "items": items, "next_page": next_page}
    )


def test_a_consistent_feed_is_read_across_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return _page([{"n": page}], next_page=2 if page == 1 else None)

    extraction = extract_inventory(_config(), run_id="run-1", client=_client(handler))

    assert extraction.snapshot_at == SNAPSHOT
    assert extraction.pages == 2
    assert extraction.columns == ("n",)
    assert [record.values["n"] for record in extraction.records] == ["1", "2"]


def test_the_source_id_is_the_address_without_query_or_credentials() -> None:
    extraction = extract_inventory(
        _config(token="s3cret"),  # noqa: S106
        run_id="run-1",
        client=_client(lambda _r: _page([])),
    )

    assert extraction.source_id == "https://stock.test/v1/stock"


def test_a_feed_that_changes_between_pages_is_read_again() -> None:
    reads = {"count": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 1:
            reads["count"] += 1
        snapshot = "2026-11-13T06:05:00Z" if reads["count"] == 1 and page == 2 else SNAPSHOT
        return _page([{"n": page}], snapshot=snapshot, next_page=2 if page == 1 else None)

    extraction = extract_inventory(
        _config(), run_id="run-1", sleep=sleeps.append, client=_client(handler)
    )

    assert reads["count"] == 2
    assert sleeps == [0.5]
    assert extraction.snapshot_at == SNAPSHOT


def test_a_temporary_failure_is_retried() -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500) if calls["count"] == 1 else _page([{"n": 1}])

    extraction = extract_inventory(
        _config(), run_id="run-1", sleep=sleeps.append, client=_client(handler)
    )

    assert len(extraction.records) == 1
    assert sleeps == [0.5]


def test_a_feed_that_stays_down_is_raised_after_the_attempts() -> None:
    sleeps: list[float] = []

    with pytest.raises(SourceUnavailableError) as info:
        extract_inventory(
            _config(),
            run_id="run-1",
            sleep=sleeps.append,
            client=_client(lambda _r: httpx.Response(503)),
        )

    assert sleeps == [0.5, 1.0]
    assert info.value.context["pipeline"] == "inventory"


def test_a_rejected_request_is_not_retried() -> None:
    sleeps: list[float] = []

    with pytest.raises(ExtractionError):
        extract_inventory(
            _config(),
            run_id="run-1",
            sleep=sleeps.append,
            client=_client(lambda _r: httpx.Response(404)),
        )

    assert sleeps == []


@pytest.mark.parametrize("snapshot", [None, "", "  ", 5])
def test_a_page_without_a_snapshot_time_is_an_extraction_error(snapshot: Any) -> None:
    sleeps: list[float] = []

    with pytest.raises(ExtractionError, match="snapshot_at"):
        extract_inventory(
            _config(),
            run_id="run-1",
            sleep=sleeps.append,
            client=_client(lambda _r: _page([], snapshot=snapshot)),
        )

    assert sleeps == []


def test_log_records_carry_the_run_context_and_never_the_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        extract_inventory(
            _config(token="s3cret"),  # noqa: S106
            run_id="run-5",
            client=_client(lambda _r: _page([])),
        )

    fields = [r.__dict__ for r in caplog.records if r.name.startswith("agpp.pipelines")]
    assert fields
    assert all(item["run_id"] == "run-5" for item in fields)
    assert "Inventory extracted" in caplog.text
    assert "s3cret" not in caplog.text
