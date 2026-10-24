import pytest

from agpp import __version__
from agpp.main import main


def test_vers_is_defined() -> None:
    assert __version__


def test_main_returns_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    assert __version__ in capsys.readouterr().out
