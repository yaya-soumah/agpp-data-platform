from pathlib import Path

import psycopg

from agpp.shared.configuration.service import load_config


def test_postgres_accepts_connections(project_root: Path) -> None:
    config = load_config(project_root / "config", env_file=project_root / ".env")
    database = config.database

    with psycopg.connect(
        host=database.host,
        port=database.port,
        dbname=database.name,
        user=database.user,
        password=database.password.get_secret_value(),
    ) as connection:
        row = connection.execute("SELECT 1;").fetchone()

    assert row == (1,)
