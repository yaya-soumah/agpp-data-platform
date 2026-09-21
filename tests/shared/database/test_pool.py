from unittest.mock import patch

from pydantic import SecretStr
from src.shared.database import PostgreSQLConfig, create_postgresql_pool


def test_create_postgresql_pool_uses_configuration() -> None:
    config = PostgreSQLConfig(
        host="localhost",
        port=5432,
        database="agpp",
        user="agpp_user",
        password=SecretStr("secret"),
        pool_size=10,
        connection_timeout=30,
    )

    with patch("src.shared.database.pool.ConnectionPool") as connection_pool:
        create_postgresql_pool(config)

    connection_pool.assert_called_once_with(
        conninfo=(
            "host=localhost port=5432 dbname=agpp user=agpp_user password=secret"
        ),
        min_size=1,
        max_size=config.pool_size,
        timeout=config.connection_timeout,
        open=False,
    )
