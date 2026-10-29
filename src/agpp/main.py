"""Command-line entry point for the AGPP platform."""

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from agpp import __version__
from agpp.shared.configuration.models import PlatformConfig
from agpp.shared.configuration.service import load_config
from agpp.shared.database import create_pool
from agpp.shared.database.migrations import apply_migrations
from agpp.shared.exceptions import AgppError, ConfigurationError
from agpp.shared.logging import configure_logging

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2


def _check_config(config: PlatformConfig) -> int:
    logger.info("Configuration is valid", extra={"environment": config.environment.value})
    return EXIT_OK


def _migrate(config: PlatformConfig) -> int:
    pool = create_pool(config.database)
    try:
        applied = apply_migrations(pool, Path(config.database.migrations_dir))
    finally:
        pool.close()
    logger.info("Migrations complete", extra={"applied": len(applied)})
    return EXIT_OK


COMMANDS: dict[str, Callable[[PlatformConfig], int]] = {
    "check-config": _check_config,
    "migrate": _migrate,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agpp", description="AGPP Data Platform")
    parser.add_argument("--version", action="version", version=f"agpp {__version__}")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="directory holding base.yaml and the environment files (default: config)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="optional file with environment variables (default: .env)",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check-config", help="load and validate the configuration")
    subcommands.add_parser("migrate", help="apply pending database migrations")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the platform CLI and return the process exit code."""
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args.config_dir, env_file=args.env_file)
    except ConfigurationError as error:
        # Logging is not configured yet, so report on stderr.
        print(f"configuration error: {error}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    configure_logging(config.logging)

    try:
        return COMMANDS[args.command](config)
    except AgppError:
        logger.exception("Command %s failed", args.command)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
