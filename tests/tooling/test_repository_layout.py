"""Relocated public documentation remains navigable from its actual location."""

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "tests" / "README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
]


class _ResourceLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.targets.append(value)


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_public_document_resources_resolve_after_relocation(document):
    body = document.read_text(encoding="utf-8")
    body = re.sub(r"(?ms)^```.*?^```[^\n]*", "", body)
    html = _ResourceLinks()
    html.feed(body)
    markdown = re.findall(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", body)
    for target in [*html.targets, *markdown]:
        target = target.split(' "', 1)[0].strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        resolved = document.parent / unquote(parsed.path)
        assert resolved.exists(), f"{document.relative_to(ROOT)} links to missing {target}"
