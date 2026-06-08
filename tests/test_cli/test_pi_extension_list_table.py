"""Table-alignment tests for `pi-extension list` (issue #336)."""
from __future__ import annotations

import json as _json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed_npm_slugs(home: Path, slugs: list[str]) -> None:
    """Write a Pi settings file containing *slugs* as npm packages."""
    s = home / ".pi" / "agent" / "settings.json"
    s.parent.mkdir(parents=True, exist_ok=True)
    packages = [f"npm:{slug}" for slug in slugs]
    s.write_text(_json.dumps({"packages": packages}))


def test_pi_extension_list_no_raw_tabs(tmp_path: Path, monkeypatch) -> None:
    """Human-readable output must contain no raw tab characters."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_slugs(tmp_path, ["short", "a-much-longer-extension-slug"])

    result = CliRunner().invoke(main, ["pi-extension", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "\t" not in result.output, "raw tab found in pi-extension list output"


def test_pi_extension_list_columns_align(tmp_path: Path, monkeypatch) -> None:
    """All rows must have the second column starting at the same character offset.

    The second column in pi-extension list is the global-loaded glyph (✔ or ☐).
    Each line's first ✔ or ☐ character must be at the same position.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_slugs(tmp_path, ["short", "a-much-longer-extension-slug"])

    result = CliRunner().invoke(main, ["pi-extension", "list", "-g"])
    assert result.exit_code == 0, result.output

    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) >= 2, "expected at least 2 rows"

    # The second column is a glyph (✔ or ☐).  Find the position of the first
    # glyph character in each line — they must all match.
    import re as _re
    glyph_positions: set[int] = set()
    for line in lines:
        m = _re.search(r"[✔☐]", line)
        assert m is not None, f"no glyph found in line: {line!r}"
        glyph_positions.add(m.start())

    assert len(glyph_positions) == 1, (
        f"glyph (col 1) starts at different offsets across rows "
        f"(positions {glyph_positions}):\n" + "\n".join(lines)
    )


def test_pi_extension_list_no_trailing_whitespace(tmp_path: Path, monkeypatch) -> None:
    """No line of the human output ends with a space."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_slugs(tmp_path, ["slug-a", "slug-bb"])

    result = CliRunner().invoke(main, ["pi-extension", "list", "-g"])
    assert result.exit_code == 0, result.output
    for line in result.output.splitlines():
        assert not line.endswith(" "), f"trailing whitespace in: {line!r}"


def test_pi_extension_list_empty_state_unchanged(tmp_path: Path, monkeypatch) -> None:
    """Empty inventory must still print the standard 'no pi extensions found' message."""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = CliRunner().invoke(main, ["pi-extension", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "no pi extensions found" in result.output


def test_pi_extension_list_json_unchanged(tmp_path: Path, monkeypatch) -> None:
    """--json path must be unaffected by the table refactor."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_slugs(tmp_path, ["some-ext"])

    result = CliRunner().invoke(main, ["pi-extension", "list", "-g", "--json"])
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert isinstance(payload, list)
    slugs = [r["slug"] for r in payload]
    assert "npm:some-ext" in slugs or any("some-ext" in s for s in slugs)
