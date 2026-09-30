"""Run the Python examples in the README and the documentation, so they cannot go stale."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```$", re.MULTILINE | re.DOTALL)


def python_blocks(page: Path) -> list[str]:
    return [str(match.group(1)) for match in PYTHON_BLOCK.finditer(page.read_text(encoding="utf-8"))]


PAGES = [page for page in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))] if python_blocks(page)]


def test_examples_are_found() -> None:
    assert ROOT / "README.md" in PAGES
    assert len(PAGES) >= 5


@pytest.mark.parametrize("page", PAGES, ids=[page.relative_to(ROOT).as_posix() for page in PAGES])
def test_page_examples_run(page: Path, tmp_path: Path) -> None:
    """Run a page's examples in order, in one fresh interpreter, like a reader pasting them."""
    script = "\n".join(python_blocks(page))
    result = subprocess.run(
        [sys.executable, "-W", "error", "-"],
        input=script,
        cwd=tmp_path,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
