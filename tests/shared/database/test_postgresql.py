import pytest
from pydantic import SecretStr
from src.shared.configuration.models import DatabaseConfig
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.database.postgresql import PostgreSQLConfigFactory
from src.shared.exceptions import ConfigurationError


@pytest.fixture
def database_config() -> DatabaseConfig:
    return DatabaseConfig(
        port=5432,
        pool_size=10,
        connection_timeout=30,
    )


@pytest.fixture
def runtime_environment(monkeypatch: pytest.MonkeyPatch) -> RuntimeEnvironment:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "agpp")
    monkeypatch.setenv("POSTGRES_USER", "agpp_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    return RuntimeEnvironment()


def test_create_returns_postgresql_config(
    database_config: DatabaseConfig,
    runtime_environment: RuntimeEnvironment,
) -> None:
    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=runtime_environment,
    )

    config = factory.create()

    assert config.host == "localhost"
    assert config.port == 5432
    assert config.database == "agpp"
    assert config.user == "agpp_user"
    assert config.password == SecretStr("secret")
    assert config.pool_size == 10
    assert config.connection_timeout == 30


def test_create_uses_database_config_values(
    runtime_environment: RuntimeEnvironment,
) -> None:
    database_config = DatabaseConfig(
        port=5432,
        pool_size=25,
        connection_timeout=60,
    )

    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=runtime_environment,
    )

    config = factory.create()

    assert config.pool_size == 25
    assert config.connection_timeout == 60


def test_create_converts_port_to_integer(
    database_config: DatabaseConfig,
    runtime_environment: RuntimeEnvironment,
) -> None:
    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=runtime_environment,
    )

    config = factory.create()

    assert config.port == 5432
    assert isinstance(config.port, int)


def test_create_rejects_invalid_port(
    database_config: DatabaseConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "invalid")
    monkeypatch.setenv("POSTGRES_DB", "agpp")
    monkeypatch.setenv("POSTGRES_USER", "agpp_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=RuntimeEnvironment(),
    )

    with pytest.raises(
        ConfigurationError,
        match="PostgreSQL Port value must be an integer.",
    ):
        factory.create()


def test_create_rejects_missing_host(
    database_config: DatabaseConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "agpp")
    monkeypatch.setenv("POSTGRES_USER", "agpp_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=RuntimeEnvironment(),
    )

    with pytest.raises(
        ConfigurationError,
        match="POSTGRES_HOST",
    ):
        factory.create()


def test_create_rejects_missing_database(
    database_config: DatabaseConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "agpp_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=RuntimeEnvironment(),
    )

    with pytest.raises(
        ConfigurationError,
        match="POSTGRES_DB",
    ):
        factory.create()


def test_create_rejects_missing_user(
    database_config: DatabaseConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "agpp")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=RuntimeEnvironment(),
    )

    with pytest.raises(
        ConfigurationError,
        match="POSTGRES_USER",
    ):
        factory.create()


def test_create_rejects_missing_password(
    database_config: DatabaseConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "agpp")
    monkeypatch.setenv("POSTGRES_USER", "agpp_user")

    factory = PostgreSQLConfigFactory(
        database_config=database_config,
        runtime_environment=RuntimeEnvironment(),
    )

    with pytest.raises(
        ConfigurationError,
        match="POSTGRES_PASSWORD",
    ):
        factory.create()
