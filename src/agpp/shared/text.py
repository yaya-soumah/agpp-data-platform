"""Small text helpers shared by every pipeline (ADR-0017)."""


def collapse_whitespace(text: str) -> str:
    """Replace every run of whitespace with a single space."""
    return " ".join(text.split())
