"""Keeps the documentation honest: every relative link must point at a real file."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\]\(([^)\s]+)\)")
EXTERNAL = ("http://", "https://", "mailto:", "#")
TEMPLATE = ROOT / "docs" / "adr" / "0000-template.md"
DOCUMENTS = sorted(
    {
        ROOT / "README.md",
        *ROOT.glob("CHANGELOG.md"),
        *ROOT.glob("docs/**/*.md"),
        *ROOT.glob("orchestration/**/README.md"),
    }
    - {TEMPLATE}
)


def _local_targets(document: Path) -> list[str]:
    targets = LINK.findall(document.read_text(encoding="utf-8"))
    return [target.split("#", 1)[0] for target in targets if not target.startswith(EXTERNAL)]


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_local_links_resolve(document: Path) -> None:
    missing = [t for t in _local_targets(document) if t and not (document.parent / t).exists()]

    assert missing == []


def test_the_documents_to_check_were_found() -> None:
    assert ROOT / "README.md" in DOCUMENTS
    assert any(path.parent.name == "adr" for path in DOCUMENTS)
