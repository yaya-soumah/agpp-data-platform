import pytest

from agpp.shared.exceptions import ExtractionError
from agpp.shared.runs import MAX_ERROR_MESSAGE, RunStatus, error_summary, run_status_for


@pytest.mark.parametrize(
    ("succeeded", "total", "expected"),
    [
        (3, 3, RunStatus.SUCCEEDED),
        (0, 0, RunStatus.SUCCEEDED),
        (0, 3, RunStatus.FAILED),
        (1, 3, RunStatus.PARTIAL),
        (2, 3, RunStatus.PARTIAL),
    ],
)
def test_run_status_from_counts(succeeded: int, total: int, expected: RunStatus) -> None:
    assert run_status_for(succeeded, total) is expected


def test_short_messages_are_kept() -> None:
    assert error_summary(ExtractionError("bad file")) == "bad file"


def test_long_messages_are_shortened() -> None:
    assert len(error_summary(ExtractionError("x" * 2000))) == MAX_ERROR_MESSAGE
