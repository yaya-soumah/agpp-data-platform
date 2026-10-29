import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from agpp.shared.configuration.models import DatabaseConfig
from agpp.shared.database import Pool, connection, create_pool
from agpp.shared.database.migrations import apply_migrations
from agpp.shared.exceptions import DatabaseConnectionError, InfrastructureError, MigrationError


@pytest.fixture
def scratch_pool(scratch_database: DatabaseConfig) -> Iterator[Pool]:
    pool = create_pool(scratch_database)
    yield pool
    pool.close()


@pytest.fixture
def migrations_dir(project_root: Path) -> Path:
    return project_root / "sql" / "migrations"


def _schemas(pool: Pool) -> set[str]:
    with connection(pool) as conn:
        rows = conn.execute(
            "SELECT schema_name FROM information_schema.schemata"
            " WHERE schema_name IN ('operational', 'warehouse')"
        ).fetchall()
    return {row[0] for row in rows}


def test_real_migrations_create_both_schemas(scratch_pool: Pool, migrations_dir: Path) -> None:
    applied = apply_migrations(scratch_pool, migrations_dir)

    assert [migration.version for migration in applied] == [1]
    assert _schemas(scratch_pool) == {"operational", "warehouse"}


def test_rerunning_migrations_applies_nothing(scratch_pool: Pool, migrations_dir: Path) -> None:
    apply_migrations(scratch_pool, migrations_dir)

    assert apply_migrations(scratch_pool, migrations_dir) == []


def test_modified_migration_is_rejected(
    scratch_pool: Pool, migrations_dir: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "migrations"
    shutil.copytree(migrations_dir, copy)
    apply_migrations(scratch_pool, copy)
    first = copy / "0001_create_schemas.sql"
    first.write_text(first.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="modified"):
        apply_migrations(scratch_pool, copy)


def test_failed_migration_rolls_back_and_is_not_recorded(
    scratch_pool: Pool, tmp_path: Path
) -> None:
    (tmp_path / "0001_ok.sql").write_text("CREATE TABLE public.ok_table (id integer);")
    (tmp_path / "0002_broken.sql").write_text(
        "CREATE TABLE public.half_done (id integer);\nSELECT * FROM public.does_not_exist;"
    )

    with pytest.raises(InfrastructureError) as info:
        apply_migrations(scratch_pool, tmp_path)

    assert not isinstance(info.value, DatabaseConnectionError)
    assert info.value.context["sqlstate"] == "42P01"
    with connection(scratch_pool) as conn:
        ok = conn.execute("SELECT to_regclass('public.ok_table') IS NOT NULL").fetchone()
        half = conn.execute("SELECT to_regclass('public.half_done') IS NOT NULL").fetchone()
        versions = conn.execute(
            "SELECT version FROM operational.schema_migrations ORDER BY version"
        ).fetchall()
    assert ok == (True,)
    assert half == (False,)
    assert versions == [(1,)]
