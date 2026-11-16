from collections.abc import Callable
from typing import Any

import httpx
import pytest

from agpp.shared.exceptions import ExtractionError, SourceUnavailableError
from agpp.shared.extraction import ApiSource, RawRecord, read_api
from agpp.shared.extraction.api_reader import _build_client

Handler = Callable[[httpx.Request], httpx.Response]


def _source(**overrides: object) -> ApiSource:
    return ApiSource.model_validate(
        {"type": "api", "base_url": "https://stock.test", "path": "/v1/stock", **overrides}
    )


def _client(handler: Handler) -> httpx.Client:
    return httpx.Client(base_url="https://stock.test", transport=httpx.MockTransport(handler))


def _page(items: list[Any], next_page: int | None = None, **extra: Any) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "snapshot_at": "2026-11-13T06:00:00Z",
            "items": items,
            "next_page": next_page,
            **extra,
        },
    )


def test_a_single_page_is_read() -> None:
    client = _client(lambda _request: _page([{"a": 1, "b": "x"}]))

    content = read_api(_source(), client=client)

    assert content.pages == ({"snapshot_at": "2026-11-13T06:00:00Z", "next_page": None},)
    assert content.columns == ("a", "b")
    assert content.records == (RawRecord(1, {"a": "1", "b": "x"}),)


def test_every_page_is_followed_and_line_numbers_continue() -> None:
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        requested.append((request.url.params["page"], request.url.params["page_size"]))
        items = [{"n": page * 10 + index} for index in range(2)]
        return _page(items, next_page=page + 1 if page < 3 else None)

    content = read_api(_source(page_size=2), client=_client(handler))

    assert requested == [("1", "2"), ("2", "2"), ("3", "2")]
    assert [record.line_number for record in content.records] == [1, 2, 3, 4, 5, 6]
    assert len(content.pages) == 3


def test_the_token_is_sent_as_a_bearer_token() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["accept"] = request.headers.get("accept")
        return _page([])

    read_api(_source(token="s3cret"), client=_client(handler))  # noqa: S106

    assert seen == {"authorization": "Bearer s3cret", "accept": "application/json"}


def test_without_a_token_no_authorization_is_sent() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return _page([])

    read_api(_source(), client=_client(handler))

    assert seen["authorization"] is None


def test_json_values_become_text() -> None:
    item = {"Name ": "Bolt", "count": 3, "price": 12.5, "active": True, "gone": False, "note": None}
    client = _client(lambda _request: _page([item]))

    content = read_api(_source(), client=client)

    assert content.records[0] == RawRecord(
        1,
        {
            "name": "Bolt",
            "count": "3",
            "price": "12.5",
            "active": "true",
            "gone": "false",
            "note": "",
        },
    )
    assert content.columns == ("name", "count", "price", "active", "gone", "note")


def test_nested_values_and_non_objects_are_flagged_on_the_record() -> None:
    items = [{"a": 1, "nested": {"x": 1}}, "not an object", {"a": 2, "list": [1]}, {"a": 3}]
    client = _client(lambda _request: _page(items))

    records = read_api(_source(), client=client).records

    assert records[0].problem == "field 'nested' is not a plain value"
    assert records[0].values == {"a": "1"}
    assert records[1].problem == "item is not a JSON object"
    assert records[2].problem == "field 'list' is not a plain value"
    assert records[3].problem is None


def test_the_columns_are_the_ordered_union_over_all_items() -> None:
    client = _client(lambda _request: _page([{"a": 1}, {"b": 2, "a": 3}, {"c": 4}]))

    assert read_api(_source(), client=client).columns == ("a", "b", "c")


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_temporary_failures_are_retryable(status: int) -> None:
    client = _client(lambda _request: httpx.Response(status))

    with pytest.raises(SourceUnavailableError) as info:
        read_api(_source(), client=client)

    assert info.value.retryable is True
    assert info.value.context["status"] == status


@pytest.mark.parametrize("status", [301, 400, 401, 403, 404])
def test_other_failures_are_not_retryable(status: int) -> None:
    client = _client(lambda _request: httpx.Response(status))

    with pytest.raises(ExtractionError) as info:
        read_api(_source(), client=client)

    assert not isinstance(info.value, SourceUnavailableError)
    assert info.value.retryable is False
    assert info.value.context["status"] == status


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("cut")],
)
def test_network_failures_and_timeouts_are_retryable(failure: httpx.TransportError) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise failure

    with pytest.raises(SourceUnavailableError) as info:
        read_api(_source(), client=_client(handler))

    assert info.value.retryable is True
    assert info.value.context["error"] == type(failure).__name__


def test_invalid_json_is_an_extraction_error() -> None:
    client = _client(lambda _request: httpx.Response(200, content=b"not json"))

    with pytest.raises(ExtractionError, match="valid JSON"):
        read_api(_source(), client=client)


@pytest.mark.parametrize("payload", [[], "text", {"snapshot_at": "x"}, {"items": "no"}])
def test_an_unexpected_page_shape_is_an_extraction_error(payload: object) -> None:
    client = _client(lambda _request: httpx.Response(200, json=payload))

    with pytest.raises(ExtractionError):
        read_api(_source(), client=client)


@pytest.mark.parametrize("next_page", [1, 0, "2", True])
def test_a_next_page_that_does_not_advance_is_an_extraction_error(next_page: object) -> None:
    client = _client(
        lambda _request: httpx.Response(200, json={"items": [], "next_page": next_page})
    )

    with pytest.raises(ExtractionError, match="invalid next page"):
        read_api(_source(), client=client)


def test_a_feed_that_never_ends_is_stopped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _page([], next_page=int(request.url.params["page"]) + 1)

    with pytest.raises(ExtractionError, match="more than 3 pages"):
        read_api(_source(), client=_client(handler), max_pages=3)


def test_the_token_never_appears_in_errors() -> None:
    client = _client(lambda _request: httpx.Response(500))

    with pytest.raises(SourceUnavailableError) as info:
        read_api(_source(token="s3cret"), client=client)  # noqa: S106

    assert "s3cret" not in str(info.value)
    assert "s3cret" not in repr(info.value.context)


def test_the_context_is_added_to_errors() -> None:
    client = _client(lambda _request: httpx.Response(404))

    with pytest.raises(ExtractionError) as info:
        read_api(_source(), client=client, context={"pipeline": "inventory"})

    assert info.value.context == {
        "pipeline": "inventory",
        "base_url": "https://stock.test",
        "path": "/v1/stock",
        "status": 404,
    }


def test_the_names_of_the_fields_and_parameters_can_be_changed() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"results": [{"a": 1}], "next": None})

    content = read_api(
        _source(page_size=7),
        client=_client(handler),
        items_key="results",
        next_key="next",
        page_param="p",
        size_param="size",
    )

    assert seen == {"p": "1", "size": "7"}
    assert len(content.records) == 1


def test_a_client_passed_in_is_not_closed() -> None:
    client = _client(lambda _request: _page([]))

    read_api(_source(), client=client)

    assert not client.is_closed
    client.close()


def test_the_client_built_from_the_source_uses_its_address_and_timeout() -> None:
    client = _build_client(_source(timeout_seconds=7))

    assert str(client.base_url).startswith("https://stock.test")
    assert client.timeout.read == 7
    client.close()
