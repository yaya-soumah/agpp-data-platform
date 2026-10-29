"""Versioned SQL migrations, applied in order and recorded in the database."""

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from psycopg import Connection
from psycopg.rows import TupleRow

from agpp.shared.database.pool import Pool
from agpp.shared.database.postgresql import connection
from agpp.shared.exceptions import MigrationError

logger = logging.getLogger(__name__)

_FILE_PATTERN = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")
_LOCK_ID = 7_243_001  # arbitrary application-wide advisory lock key


@dataclass(frozen=True)
class Migration:
    """One SQL file, identified by a four-digit version."""

    version: int
    name: str
    sql: str
    checksum: str


def discover_migrations(directory: Path) -> list[Migration]:
    """Read ``NNNN_description.sql`` files from ``directory`` in version order."""
    if not directory.is_dir():
        raise MigrationError(
            f"Migrations directory not found: {directory}",
            context={"directory": str(directory)},
        )
    found: dict[int, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_PATTERN.match(path.name)
        if match is None:
            raise MigrationError(
                f"Invalid migration file name: {path.name} (expected NNNN_description.sql)",
                context={"file": path.name},
            )
        version = int(match["version"])
        if version in found:
            raise MigrationError(
                f"Duplicate migration version {version:04d}", context={"file": path.name}
            )
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        found[version] = Migration(version, match["name"], sql, checksum)
    return [found[version] for version in sorted(found)]


def verify_applied(migrations: Sequence[Migration], applied: Mapping[int, str]) -> None:
    """Fail if an applied migration was edited or has disappeared from disk."""
    on_disk = {migration.version: migration for migration in migrations}
    for version, checksum in sorted(applied.items()):
        migration = on_disk.get(version)
        if migration is None:
            raise MigrationError(
                f"Applied migration {version:04d} is missing from disk",
                context={"version": version},
            )
        if migration.checksum != checksum:
            raise MigrationError(
                f"Migration {version:04d} was modified after being applied",
                context={"version": version, "name": migration.name},
            )


def apply_migrations(pool: Pool, directory: Path) -> list[Migration]:
    """Apply pending migrations in order and return the ones that ran.

    Each migration runs in its own transaction together with its bookkeeping
    row, under an advisory lock so two runners cannot apply the same file.
    Running it again applies nothing (idempotent).
    """
    migrations = discover_migrations(directory)
    applied_now: list[Migration] = []

    with connection(pool) as conn:
        conn.autocommit = True
        try:
            conn.execute("CREATE SCHEMA IF NOT EXISTS operational")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operational.schema_migrations (
                    version integer PRIMARY KEY,
                    name text NOT NULL,
                    checksum text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            rows = conn.execute(
                "SELECT version, checksum FROM operational.schema_migrations"
            ).fetchall()
            applied = {int(version): str(checksum) for version, checksum in rows}
            verify_applied(migrations, applied)

            for migration in migrations:
                if migration.version not in applied and _apply_one(conn, migration):
                    applied_now.append(migration)
        finally:
            if not conn.closed and not conn.broken:
                conn.autocommit = False

    if applied_now:
        logger.info("Applied %d migration(s)", len(applied_now))
    else:
        logger.info("No pending migrations")
    return applied_now


def _apply_one(conn: Connection[TupleRow], migration: Migration) -> bool:
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_ID,))
        already = conn.execute(
            "SELECT 1 FROM operational.schema_migrations WHERE version = %s",
            (migration.version,),
        ).fetchone()
        if already is not None:
            return False
        # Migration files are trusted repository content, not user input.
        conn.execute(migration.sql.encode("utf-8"))
        conn.execute(
            "INSERT INTO operational.schema_migrations (version, name, checksum)"
            " VALUES (%s, %s, %s)",
            (migration.version, migration.name, migration.checksum),
        )
    logger.info(
        "Applied migration %04d_%s",
        migration.version,
        migration.name,
        extra={"version": migration.version, "migration": migration.name},
    )
    return True
