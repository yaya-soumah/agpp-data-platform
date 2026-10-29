from typing import ClassVar

import pytest
from psycopg_pool import PoolTimeout
from pydantic import SecretStr

import agpp.shared.database.pool as pool_module
from agpp.shared.configuration.models import DatabaseConfig
from agpp.shared.database.pool import build_conninfo, create_pool
from agpp.shared.exceptions import DatabaseConnectionError
from agpp.shared.resilience.retry import RetryPolicy

CONFIG = DatabaseConfig(
    host="db.local",
    port=5432,
    name="agpp",
    user="agpp",
    password=SecretStr("s3cret"),
    pool_min_size=1,
    pool_max_size=3,
)
POLICY = RetryPolicy(max_attempts=3, initial_delay=0.0)


class FakePool:
    """Stands in for psycopg_pool.ConnectionPool; no network is used."""

    created: ClassVar[list["FakePool"]] = []
    failures: ClassVar[int] = 0

    def __init__(self, conninfo: str, *, min_size: int, max_size: int, open: bool) -> None:
        self.conninfo = conninfo
        self.min_size = min_size
        self.max_size = max_size
        self.is_open = False
        self.closed = False
        FakePool.created.append(self)

    def open(self, *, wait: bool, timeout: float) -> None:
        if FakePool.failures > 0:
            FakePool.failures -= 1
            raise PoolTimeout("no connection")
        self.is_open = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch) -> type[FakePool]:
    FakePool.created = []
    FakePool.failures = 0
    monkeypatch.setattr(pool_module, "ConnectionPool", FakePool)
    return FakePool


def _no_sleep(_seconds: float) -> None:
    return None


def test_conninfo_contains_connection_settings() -> None:
    conninfo = build_conninfo(CONFIG)

    for part in ("host=db.local", "port=5432", "dbname=agpp", "user=agpp", "connect_timeout=10"):
        assert part in conninfo


def test_create_pool_opens_a_pool_with_configured_sizes(fake_pool: type[FakePool]) -> None:
    create_pool(CONFIG, retry_policy=POLICY, sleep=_no_sleep)

    assert len(fake_pool.created) == 1
    created = fake_pool.created[0]
    assert created.is_open
    assert (created.min_size, created.max_size) == (1, 3)


def test_create_pool_retries_a_failed_connection(fake_pool: type[FakePool]) -> None:
    fake_pool.failures = 1

    create_pool(CONFIG, retry_policy=POLICY, sleep=_no_sleep)

    assert len(fake_pool.created) == 2
    assert fake_pool.created[0].closed
    assert fake_pool.created[1].is_open


def test_create_pool_gives_up_with_a_safe_error(fake_pool: type[FakePool]) -> None:
    fake_pool.failures = 99

    with pytest.raises(DatabaseConnectionError) as info:
        create_pool(CONFIG, retry_policy=POLICY, sleep=_no_sleep)

    assert len(fake_pool.created) == 3
    assert all(pool.closed for pool in fake_pool.created)
    assert info.value.context == {"host": "db.local", "port": 5432, "database": "agpp"}
    assert "s3cret" not in str(info.value)
