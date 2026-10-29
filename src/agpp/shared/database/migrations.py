"""Versioned SQL migrations, applied in order and recorded in the database."""

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from agpp.shared.exceptions import MigrationError

logger = logging.getLogger(__name__)

_FILE_PATTERN = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")


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
