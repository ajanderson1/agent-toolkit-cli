"""Table-alignment tests for `skill list` (issue #336)."""
from __future__ import annotations

import json as _json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _write_skill_lock(library_root: Path, skills: dict) -> None:
    """Write a minimal skills-lock.json adjacent to *library_root*.

    The global lock lives at <library_root>.parent/skills-lock.json per
    library_lock_path_for_kind in _paths_core.py.
    """
    library_root.mkdir(parents=True, exist_ok=True)
    lock_path = library_root.parent / "skills-lock.json"
    data = {"version": 1, "skills": skills}
    lock_path.write_text(_json.dumps(data))


def _skill_entry(source: str, ref: str | None = "main", sha: str | None = "abc1234") -> dict:
    # Use camelCase keys matching the on-disk v1 lock format (_entry_from_dict_v1).
    return {"source": source, "ref": ref, "upstreamSha": sha, "localSha": sha}


def test_skill_list_no_raw_tabs(tmp_path: Path, monkeypatch) -> None:
    """Human-readable output must contain no raw tab characters."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    _write_skill_lock(library_root, {
        "short-skill": _skill_entry("https://example.com/short"),
        "a-much-longer-skill-name": _skill_entry("https://example.com/longer"),
    })

    result = CliRunner().invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "\t" not in result.output, "raw tab found in skill list output"


def test_skill_list_columns_align(tmp_path: Path, monkeypatch) -> None:
    """Second column (source) must start at the same character offset in every row."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    _write_skill_lock(library_root, {
        "short": _skill_entry("https://example.com/short"),
        "a-much-longer-skill-name": _skill_entry("https://example.com/longer"),
    })

    result = CliRunner().invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.output

    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) >= 2, "expected at least 2 rows"

    # Find the first occurrence of "https://" in each line — that's the source
    # column start.  They must all be at the same character offset.
    positions: set[int] = set()
    for line in lines:
        pos = line.find("https://")
        assert pos != -1, f"source URL not found in line: {line!r}"
        positions.add(pos)

    assert len(positions) == 1, (
        f"source column starts at different offsets across rows "
        f"(positions {positions}):\n" + "\n".join(lines)
    )


def test_skill_list_no_trailing_whitespace(tmp_path: Path, monkeypatch) -> None:
    """No line of the human output ends with a space."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    _write_skill_lock(library_root, {
        "skill-a": _skill_entry("https://example.com/a"),
        "skill-bb": _skill_entry("https://example.com/bb"),
    })

    result = CliRunner().invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.output
    for line in result.output.splitlines():
        assert not line.endswith(" "), f"trailing whitespace in: {line!r}"


def test_skill_list_empty_state_unchanged(tmp_path: Path, monkeypatch) -> None:
    """Empty lock must still print the standard empty-state message."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    result = CliRunner().invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "(no skills installed)" in result.output


def test_skill_list_json_unchanged(tmp_path: Path, monkeypatch) -> None:
    """--json path must be unaffected by the table refactor."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    _write_skill_lock(library_root, {
        "my-skill": _skill_entry("https://example.com/skill"),
    })

    result = CliRunner().invoke(main, ["skill", "list", "-g", "--json"])
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert isinstance(payload, list)
    slugs = [r["slug"] for r in payload]
    assert "my-skill" in slugs
