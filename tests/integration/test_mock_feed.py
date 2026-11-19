import httpx
import pytest

from agpp.pipelines.inventory.mock_feed import FeedState, MockFeed
from agpp.shared.extraction import ApiSource, read_api

ITEMS = [{"n": index} for index in range(5)]
SNAPSHOT = "2026-11-14T06:00:00Z"


def _get(feed: MockFeed, path: str = "/v1/stock", **params: object) -> httpx.Response:
    return httpx.get(f"{feed.base_url}{path}", params=params or None)  # type: ignore[arg-type]


@pytest.fixture
def state() -> FeedState:
    return FeedState(snapshot_at=SNAPSHOT, items=list(ITEMS))


def test_the_feed_is_paginated(state: FeedState) -> None:
    with MockFeed(state) as feed:
        first = _get(feed, page=1, page_size=2).json()
        second = _get(feed, page=2, page_size=2).json()
        last = _get(feed, page=3, page_size=2).json()

    assert first == {"snapshot_at": SNAPSHOT, "items": ITEMS[0:2], "next_page": 2}
    assert second["next_page"] == 3
    assert last == {"snapshot_at": SNAPSHOT, "items": ITEMS[4:5], "next_page": None}


def test_other_paths_are_not_found(state: FeedState) -> None:
    with MockFeed(state) as feed:
        assert _get(feed, "/v2/stock").status_code == 404


def test_a_token_is_required_when_configured(state: FeedState) -> None:
    state.token = "s3cret"  # noqa: S105
    with MockFeed(state) as feed:
        anonymous = _get(feed)
        wrong = httpx.get(f"{feed.base_url}/v1/stock", headers={"Authorization": "Bearer nope"})
        right = httpx.get(f"{feed.base_url}/v1/stock", headers={"Authorization": "Bearer s3cret"})

    assert (anonymous.status_code, wrong.status_code, right.status_code) == (401, 401, 200)


def test_the_requested_number_of_failures_are_served_first(state: FeedState) -> None:
    state.fail_next = 2
    with MockFeed(state) as feed:
        statuses = [_get(feed).status_code for _ in range(3)]

    assert statuses == [503, 503, 200]


def test_the_snapshot_can_change_between_pages(state: FeedState) -> None:
    state.snapshot_for_page = lambda page: SNAPSHOT if page == 1 else "2026-11-14T06:05:00Z"
    with MockFeed(state) as feed:
        first = _get(feed, page=1, page_size=2).json()["snapshot_at"]
        second = _get(feed, page=2, page_size=2).json()["snapshot_at"]

    assert (first, second) == (SNAPSHOT, "2026-11-14T06:05:00Z")


@pytest.mark.parametrize("params", [{"page": "x"}, {"page": 0}, {"page_size": 0}])
def test_invalid_paging_parameters_are_rejected(
    state: FeedState, params: dict[str, object]
) -> None:
    with MockFeed(state) as feed:
        assert _get(feed, **params).status_code == 400  # type: ignore[arg-type]


def test_every_request_is_recorded(state: FeedState) -> None:
    with MockFeed(state) as feed:
        _get(feed, page=1, page_size=2)

    assert state.requests == ["/v1/stock?page=1&page_size=2"]


def test_the_shared_api_reader_can_read_it_over_real_http(state: FeedState) -> None:
    with MockFeed(state) as feed:
        source = ApiSource.model_validate(
            {"type": "api", "base_url": feed.base_url, "path": "/v1/stock", "page_size": 2}
        )

        content = read_api(source)

    assert len(content.pages) == 3
    assert [record.values["n"] for record in content.records] == ["0", "1", "2", "3", "4"]


def test_stopping_twice_is_harmless(state: FeedState) -> None:
    feed = MockFeed(state)
    feed.start()

    feed.stop()
    feed.stop()
