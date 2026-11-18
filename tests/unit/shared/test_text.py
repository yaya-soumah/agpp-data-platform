from agpp.shared.text import collapse_whitespace


def test_runs_of_whitespace_become_one_space() -> None:
    assert collapse_whitespace("  Hex \t Bolt\n M8 ") == "Hex Bolt M8"


def test_text_without_extra_whitespace_is_unchanged() -> None:
    assert collapse_whitespace("Hex Bolt") == "Hex Bolt"


def test_blank_text_becomes_empty() -> None:
    assert collapse_whitespace(" \t\n ") == ""
