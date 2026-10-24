"""Shared pytest configutation and fixtures."""

from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = _TESTS_ROOT.parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test with the layer (unit/integration) of the folder it lives in."""
    for item in items:
        layer = item.path.resolve().relative_to(_TESTS_ROOT).parts[0]
        if layer in {"unit", "integration"}:
            item.add_marker(getattr(pytest.mark, layer))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the repository root."""
    return PROJECT_ROOT
