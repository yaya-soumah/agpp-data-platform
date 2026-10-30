import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from agpp.shared.configuration.models import DatabaseConfig
from agpp.shared.configuration.service import load_config
from agpp.shared.database import Pool, create_pool
from agpp.shared.database.pool import build_conninfo

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def database_config() -> DatabaseConfig:
    """Database settings for the local Docker Compose Postgres."""
    return load_config(_ROOT / "config", env_file=_ROOT / ".env").database


@pytest.fixture
def scratch_database(database_config: DatabaseConfig) -> Iterator[DatabaseConfig]:
    """A throwaway database, so migration tests never touch the real one."""
    name = f"agpp_test_{uuid.uuid4().hex[:12]}"
    admin = build_conninfo(database_config.model_copy(update={"name": "postgres"}))
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield database_config.model_copy(update={"name": name})
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def scratch_pool(scratch_database: DatabaseConfig) -> Iterator[Pool]:
    pool = create_pool(scratch_database)
    yield pool
    pool.close()
