"""Command-line entry point for the AGPP platform."""

import argparse
import logging
import sys
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path

from agpp import __version__
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.extraction import extract_all
from agpp.pipelines.supplier_product.sample_data import generate_supplier_files
from agpp.pipelines.supplier_product.validation import validate_all
from agpp.shared.configuration.models import PlatformConfig
from agpp.shared.configuration.service import load_config, load_pipeline_config
from agpp.shared.database import create_pool
from agpp.shared.database.migrations import apply_migrations
from agpp.shared.dates.datetime_utils import utc_now
from agpp.shared.exceptions import AgppError, ConfigurationError
from agpp.shared.logging import configure_logging

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2


def _supplier_product_config(args: argparse.Namespace) -> SupplierProductConfig:
    return load_pipeline_config(
        args.config_dir, "supplier_product", SupplierProductConfig, env_file=args.env_file
    )


def _check_config(config: PlatformConfig, _args: argparse.Namespace) -> int:
    logger.info("Configuration is valid", extra={"environment": config.environment.value})
    return EXIT_OK


def _migrate(config: PlatformConfig, _args: argparse.Namespace) -> int:
    pool = create_pool(config.database)
    try:
        applied = apply_migrations(pool, Path(config.database.migrations_dir))
    finally:
        pool.close()
    logger.info("Migrations complete", extra={"applied": len(applied)})
    return EXIT_OK


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _ratio(text: str) -> float:
    value = float(text)
    if not 0 <= value <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return value


def _generate_sample_data(config: PlatformConfig, args: argparse.Namespace) -> int:
    pipeline_config = _supplier_product_config(args)
    summaries = generate_supplier_files(
        pipeline_config,
        rows_per_supplier=args.rows,
        bad_row_ratio=args.bad_ratio,
        seed=args.seed,
        now=utc_now(),
    )
    for summary in summaries:
        logger.info(
            "Generated supplier file",
            extra={
                "supplier_id": summary.supplier_id,
                "path": str(summary.path),
                "rows": summary.rows,
                "defective_rows": summary.defective_rows,
            },
        )
    return EXIT_OK


def _extract_supplier_products(config: PlatformConfig, args: argparse.Namespace) -> int:
    pipeline_config = _supplier_product_config(args)
    outcomes = extract_all(pipeline_config, run_id=uuid.uuid4().hex[:12])
    return EXIT_OK if all(outcome.succeeded for outcome in outcomes) else EXIT_ERROR


def _validate_supplier_products(config: PlatformConfig, args: argparse.Namespace) -> int:
    pipeline_config = _supplier_product_config(args)
    run_id = uuid.uuid4().hex[:12]
    extractions = extract_all(pipeline_config, run_id=run_id)
    validations = validate_all(pipeline_config, extractions, run_id=run_id, now=utc_now())
    return EXIT_OK if all(outcome.succeeded for outcome in validations) else EXIT_ERROR


COMMANDS: dict[str, Callable[[PlatformConfig, argparse.Namespace], int]] = {
    "check-config": _check_config,
    "migrate": _migrate,
    "generate-sample-data": _generate_sample_data,
    "extract-supplier-products": _extract_supplier_products,
    "validate-supplier-products": _validate_supplier_products,
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
    subcommands.add_parser(
        "extract-supplier-products",
        help="read every supplier source and report row counts (no loading yet)",
    )
    subcommands.add_parser(
        "validate-supplier-products",
        help="extract and validate every supplier file, then report (no loading yet)",
    )

    generate = subcommands.add_parser(
        "generate-sample-data", help="write synthetic supplier CSV files for development"
    )
    generate.add_argument("--rows", type=_positive_int, default=200, help="rows per supplier")
    generate.add_argument(
        "--bad-ratio", type=_ratio, default=0.05, help="share of deliberately bad rows"
    )
    generate.add_argument("--seed", type=int, default=42, help="seed for reproducible files")

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
        return COMMANDS[args.command](config, args)
    except AgppError:
        logger.exception("Command %s failed", args.command)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
