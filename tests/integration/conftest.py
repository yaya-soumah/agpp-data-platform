from pathlib import Path

import pytest

from agpp.shared.configuration.models import DatabaseConfig
from agpp.shared.configuration.service import load_config

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def database_config() -> DatabaseConfig:
    """Database settings for the local Docker Compose Postgres."""
    return load_config(_ROOT / "config", env_file=_ROOT / ".env").database
