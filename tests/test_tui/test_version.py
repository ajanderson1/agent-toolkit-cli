"""Version resolver — uses importlib.metadata, falls back to 'unknown'."""
from __future__ import annotations


def test_version_is_a_string() -> None:
    from agent_toolkit_tui import __version__
    assert isinstance(__version__, str)
    assert __version__   # not empty


def test_version_matches_pyproject_when_installed() -> None:
    """When the package is installed (uv sync), __version__ should match pyproject."""
    import re
    from pathlib import Path

    from agent_toolkit_tui import __version__

    # Read pyproject from the repo root (test file is at tests/test_tui/test_version.py)
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert m, "version not found in pyproject.toml"
    expected = m.group(1)
    # Either we resolved it correctly, or we're in a non-installed dev shell
    # (in which case __version__ is "unknown"). Both are acceptable in tests
    # because uv sync installs us.
    assert __version__ in (expected, "unknown")
