"""Table-alignment tests for `agent list` (issue #336)."""
from __future__ import annotations

import json as _json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _write_agent_lock(home: Path, agents: dict) -> None:
    """Write a minimal agents-lock.json at the global library lock path.

    The global agent lock lives at ~/.agent-toolkit/agents-lock.json per
    library_lock_path_for_asset_type with AGENT_BINDING in _paths_core.py.
    """
    lock_path = home / ".agent-toolkit" / "agents-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": 1, "skills": agents}
    lock_path.write_text(_json.dumps(data))


def _agent_entry(source: str = "https://github.com/example/agent") -> dict:
    return {
        "source": source,
        "sourceType": "github",
        "agentPath": "agent.md",
    }


def test_agent_list_no_raw_tabs(tmp_path: Path, monkeypatch) -> None:
    """Human-readable output must contain no raw tab characters."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_agent_lock(tmp_path, {
        "short-agent": _agent_entry(),
        "a-much-longer-agent-name": _agent_entry("https://github.com/example/long"),
    })

    result = CliRunner().invoke(main, ["agent", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "\t" not in result.output, "raw tab found in agent list output"


def test_agent_list_columns_align(tmp_path: Path, monkeypatch) -> None:
    """Marker (✔/☐) column and slug column must start at the same offsets across all rows."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_agent_lock(tmp_path, {
        "short": _agent_entry(),
        "a-much-longer-agent-name": _agent_entry("https://github.com/example/long"),
    })

    result = CliRunner().invoke(main, ["agent", "list", "-g"])
    assert result.exit_code == 0, result.output

    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) >= 2, "expected at least 2 rows"

    # The marker column (✔ or ☐) is column 0.  In the new aligned format the
    # slug (col 1) must start at the same character offset on every line.
    # Since the marker is always a single glyph (display_width=1), col 1 starts
    # at offset 3 (1 marker char + 2-space gutter).  Find "short" and
    # "a-much-longer-agent-name" in their respective lines and confirm offset.
    slug_positions: set[int] = set()
    for line in lines:
        # Skip the glyph (col 0) and the 2-space gutter to find col 1 start.
        # We search for the known slug strings.
        for slug in ("short", "a-much-longer-agent-name"):
            pos = line.find(slug)
            if pos != -1:
                slug_positions.add(pos)
                break

    assert len(slug_positions) == 1, (
        f"slug column starts at different offsets across rows "
        f"(positions {slug_positions}):\n" + "\n".join(lines)
    )


def test_agent_list_no_trailing_whitespace(tmp_path: Path, monkeypatch) -> None:
    """No line of the human output ends with a space."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_agent_lock(tmp_path, {
        "agent-a": _agent_entry(),
        "agent-bb": _agent_entry("https://github.com/example/bb"),
    })

    result = CliRunner().invoke(main, ["agent", "list", "-g"])
    assert result.exit_code == 0, result.output
    for line in result.output.splitlines():
        assert not line.endswith(" "), f"trailing whitespace in: {line!r}"


def test_agent_list_empty_state_unchanged(tmp_path: Path, monkeypatch) -> None:
    """No lock file must still print the standard 'no agents found' message."""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = CliRunner().invoke(main, ["agent", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "no agents found" in result.output


def test_agent_list_json_unchanged(tmp_path: Path, monkeypatch) -> None:
    """--json path must be unaffected by the table refactor."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_agent_lock(tmp_path, {
        "my-agent": _agent_entry(),
    })

    result = CliRunner().invoke(main, ["agent", "list", "-g", "--json"])
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert isinstance(payload, list)
    slugs = [r["slug"] for r in payload]
    assert "my-agent" in slugs
