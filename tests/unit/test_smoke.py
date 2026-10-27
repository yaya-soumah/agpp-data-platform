import pytest

from agpp import __version__
from agpp.main import main


def test_version_is_defined() -> None:
    assert __version__


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out
