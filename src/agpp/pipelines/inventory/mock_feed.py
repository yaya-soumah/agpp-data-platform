"""A small local stock feed for development, demos and tests (ADR-0018).

It serves ``GET <path>?page=N&page_size=M`` with the response shape of the contract.
This is development tooling, not a production server.
"""

import contextlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, cast
from urllib.parse import parse_qs, urlparse


@dataclass
class FeedState:
    """What the feed serves, and switches to misbehave on purpose.

    ``token`` (if set) must be sent as a bearer token. ``fail_next`` makes the next
    requests answer 503. ``snapshot_for_page`` lets a test change the reported
    snapshot between pages. ``requests`` records every request path.
    """

    snapshot_at: str
    items: list[Any]
    token: str | None = None
    fail_next: int = 0
    snapshot_for_page: Callable[[int], str] | None = None
    requests: list[str] = field(default_factory=list)


class FeedHttpServer(ThreadingHTTPServer):
    """The HTTP server holding the state it serves."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], *, state: FeedState, path: str) -> None:
        super().__init__(address, _Handler)
        self.state = state
        self.feed_path = path


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        server = cast(FeedHttpServer, self.server)
        state = server.state
        state.requests.append(self.path)
        parsed = urlparse(self.path)

        if parsed.path != server.feed_path:
            self._send(404, {"error": "not found"})
            return
        if state.token is not None and self.headers.get("Authorization") != f"Bearer {state.token}":
            self._send(401, {"error": "unauthorized"})
            return
        if state.fail_next > 0:
            state.fail_next -= 1
            self._send(503, {"error": "temporarily unavailable"})
            return

        query = parse_qs(parsed.query)
        try:
            page = int(query.get("page", ["1"])[0])
            size = int(query.get("page_size", ["500"])[0])
        except ValueError:
            self._send(400, {"error": "page and page_size must be integers"})
            return
        if page < 1 or size < 1:
            self._send(400, {"error": "page and page_size must be at least 1"})
            return

        start = (page - 1) * size
        snapshot = state.snapshot_for_page(page) if state.snapshot_for_page else state.snapshot_at
        self._send(
            200,
            {
                "snapshot_at": snapshot,
                "items": state.items[start : start + size],
                "next_page": page + 1 if start + size < len(state.items) else None,
            },
        )

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return None


class MockFeed:
    """A feed running in a background thread; use it as a context manager."""

    def __init__(
        self, state: FeedState, *, path: str = "/v1/stock", host: str = "127.0.0.1", port: int = 0
    ) -> None:
        self._host = host
        self._server = FeedHttpServer((host, port), state=state, path=path)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._started = False

    @property
    def base_url(self) -> str:
        """The address to put into ``source.base_url`` (the port is chosen by the system)."""
        return f"http://{self._host}:{self._server.server_port}"

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._server.shutdown()
            self._thread.join(timeout=5)
            self._started = False
        self._server.server_close()

    def __enter__(self) -> "MockFeed":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()


def serve(state: FeedState, *, host: str, port: int, path: str) -> None:
    """Serve the feed in the foreground until interrupted (Ctrl+C)."""
    server = FeedHttpServer((host, port), state=state, path=path)
    try:
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
    finally:
        server.server_close()
