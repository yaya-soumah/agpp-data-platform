from pathlib import Path

import pytest


def test_unit_tests_are_marked_automatically(request: pytest.FixtureRequest) -> None:
    assert request.node.get_closest_marker("unit") is not None


def test_project_root_fixture_points_at_repository(project_root: Path) -> None:
    assert (project_root / "pyproject.toml").is_file()
