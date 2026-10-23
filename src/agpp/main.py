"""Command-line entry point for the AGPP platform."""

from agpp import __version__


def main() -> int:
    """Run the platform CLI. Pipelines are wired in from Phase 3."""
    print(f"AGPP Data Platform v{__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
