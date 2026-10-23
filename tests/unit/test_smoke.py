from agpp import __version__
from agpp.main import main


def test_vers_is_defined() -> None:
    assert __version__


def test_main_returns_success(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main() == 0
    assert __version__ in capsys.readouterr().out
