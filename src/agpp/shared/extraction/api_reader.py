"""Read a paginated JSON feed over HTTP (ADR-0011, ADR-0018)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from agpp.shared.exceptions import ExtractionError, SourceUnavailableError
from agpp.shared.extraction.config import ApiSource
from agpp.shared.extraction.records import RawRecord

MAX_PAGES = 1000


@dataclass(frozen=True)
class ApiContent:
    """The records of a feed and the top-level fields of each page (without the items)."""

    pages: tuple[Mapping[str, Any], ...]
    columns: tuple[str, ...]
    records: tuple[RawRecord, ...]


def read_api(
    source: ApiSource,
    *,
    client: httpx.Client | None = None,
    items_key: str = "items",
    next_key: str = "next_page",
    page_param: str = "page",
    size_param: str = "page_size",
    max_pages: int = MAX_PAGES,
    context: Mapping[str, object] | None = None,
) -> ApiContent:
    """Read every page of the feed and turn its items into raw records.

    A network failure, timeout, ``429`` or ``5xx`` raises ``SourceUnavailableError``
    (retryable). Any other failure status, invalid JSON, an unexpected page shape
    or a feed that never ends raises ``ExtractionError``. The token is sent as a
    bearer token and never appears in an error. A client passed in is not closed.
    """
    error_context: dict[str, object] = {
        **(context or {}),
        "base_url": source.base_url,
        "path": source.path,
    }
    http = client if client is not None else _build_client(source)
    try:
        return _read_pages(
            http, source, items_key, next_key, page_param, size_param, max_pages, error_context
        )
    finally:
        if client is None:
            http.close()


def _build_client(source: ApiSource) -> httpx.Client:
    return httpx.Client(base_url=source.base_url, timeout=source.timeout_seconds)


def _headers(source: ApiSource) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if source.token is not None:
        headers["Authorization"] = f"Bearer {source.token.get_secret_value()}"
    return headers


def _read_pages(
    http: httpx.Client,
    source: ApiSource,
    items_key: str,
    next_key: str,
    page_param: str,
    size_param: str,
    max_pages: int,
    context: Mapping[str, object],
) -> ApiContent:
    pages: list[Mapping[str, Any]] = []
    items: list[Any] = []
    page = 1
    while True:
        if len(pages) >= max_pages:
            raise ExtractionError(f"Feed has more than {max_pages} pages", context=context)
        payload = _get_json(http, source, {page_param: page, size_param: source.page_size}, context)
        if not isinstance(payload, dict):
            raise ExtractionError("Feed page is not a JSON object", context=context)
        page_items = payload.get(items_key)
        if not isinstance(page_items, list):
            raise ExtractionError(f"Feed page has no {items_key!r} list", context=context)
        pages.append({key: value for key, value in payload.items() if key != items_key})
        items.extend(page_items)

        next_page = payload.get(next_key)
        if next_page is None:
            break
        if not isinstance(next_page, int) or isinstance(next_page, bool) or next_page <= page:
            raise ExtractionError(
                f"Feed page {page} points at an invalid next page", context=context
            )
        page = next_page

    columns, records = _to_records(items)
    return ApiContent(tuple(pages), columns, records)


def _get_json(
    http: httpx.Client,
    source: ApiSource,
    params: Mapping[str, int],
    context: Mapping[str, object],
) -> Any:
    try:
        response = http.get(source.path, params=dict(params), headers=_headers(source))
    except httpx.InvalidURL as error:
        raise ExtractionError("The feed address is invalid", context=context) from error
    except httpx.TransportError as error:
        raise SourceUnavailableError(
            "Cannot reach the feed", context={**context, "error": type(error).__name__}
        ) from error

    status = response.status_code
    failure_context = {**context, "status": status}
    if status == 429 or status >= 500:
        raise SourceUnavailableError(f"Feed answered {status}", context=failure_context)
    if status >= 300:
        raise ExtractionError(f"Feed answered {status}", context=failure_context)
    try:
        return response.json()
    except ValueError as error:
        raise ExtractionError("Feed did not return valid JSON", context=context) from error


def _to_records(items: Sequence[Any]) -> tuple[tuple[str, ...], tuple[RawRecord, ...]]:
    """Turn JSON items into records; the line number is the item's 1-based position."""
    columns: dict[str, None] = {}
    records: list[RawRecord] = []
    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            records.append(RawRecord(position, {}, "item is not a JSON object"))
            continue
        values: dict[str, str] = {}
        problem: str | None = None
        for key, value in item.items():
            name = str(key).strip().lower()
            columns.setdefault(name)
            text = _scalar_text(value)
            if text is None:
                problem = problem or f"field {name!r} is not a plain value"
                continue
            values[name] = text
        records.append(RawRecord(position, values, problem))
    return tuple(columns), tuple(records)


def _scalar_text(value: Any) -> str | None:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float | str):
        return str(value)
    return None
