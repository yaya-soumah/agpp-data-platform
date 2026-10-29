from pathlib import Path

import pytest

from agpp.shared.database.migrations import Migration, discover_migrations, verify_applied
from agpp.shared.exceptions import MigrationError


def _write(directory: Path, name: str, sql: str = "SELECT 1;") -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def test_discovers_migrations_in_version_order(tmp_path: Path) -> None:
    _write(tmp_path, "0002_add_table.sql")
    _write(tmp_path, "0001_create_schemas.sql")

    migrations = discover_migrations(tmp_path)

    assert [(m.version, m.name) for m in migrations] == [(1, "create_schemas"), (2, "add_table")]


def test_checksum_changes_with_content(tmp_path: Path) -> None:
    _write(tmp_path, "0001_a.sql", "SELECT 1;")
    first = discover_migrations(tmp_path)[0].checksum

    _write(tmp_path, "0001_a.sql", "SELECT 2;")

    assert discover_migrations(tmp_path)[0].checksum != first


def test_empty_directory_has_no_migrations(tmp_path: Path) -> None:
    assert discover_migrations(tmp_path) == []


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(MigrationError, match="not found"):
        discover_migrations(tmp_path / "absent")


def test_invalid_file_name_raises(tmp_path: Path) -> None:
    _write(tmp_path, "init.sql")

    with pytest.raises(MigrationError, match="Invalid migration file name"):
        discover_migrations(tmp_path)


def test_duplicate_versions_raise(tmp_path: Path) -> None:
    _write(tmp_path, "0001_a.sql")
    _write(tmp_path, "0001_b.sql")

    with pytest.raises(MigrationError, match="Duplicate"):
        discover_migrations(tmp_path)


def test_verify_accepts_unchanged_migrations() -> None:
    migrations = [Migration(1, "a", "SELECT 1;", "abc")]

    verify_applied(migrations, {1: "abc"})


def test_verify_rejects_a_modified_migration() -> None:
    migrations = [Migration(1, "a", "SELECT 1;", "abc")]

    with pytest.raises(MigrationError, match="modified"):
        verify_applied(migrations, {1: "different"})


def test_verify_rejects_an_applied_migration_missing_from_disk() -> None:
    with pytest.raises(MigrationError, match="missing from disk"):
        verify_applied([], {5: "abc"})
