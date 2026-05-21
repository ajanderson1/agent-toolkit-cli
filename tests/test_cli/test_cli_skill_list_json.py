"""Tests for `skill list --json` and `skill list -a/--agent` filter.

Surface alignment with vercel-labs/skills npx surface — see #169.
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo(runner: CliRunner, upstream_path: Path, slug: str = "demo"):
    return runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", slug,
    ])


def _install_universal(runner: CliRunner, slug: str = "demo"):
    return runner.invoke(main, [
        "skill", "install", slug, "--agents", "universal",
    ])


# ── --json shape ──────────────────────────────────────────────────────────


def test_skill_list_json_empty_lock_emits_array(tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "list", "--json", "-g"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


def test_skill_list_json_shape_keys(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, ["skill", "list", "--json", "-g"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    obj = data[0]
    assert set(obj.keys()) == {
        "slug", "source", "ref", "upstream_sha", "local_sha", "scope",
    }
    assert obj["slug"] == "demo"
    assert obj["scope"] == "global"
    # source recorded as the git sandbox path (a local-path source).
    assert obj["source"]


def test_skill_list_json_full_sha_no_short_form(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, ["skill", "list", "--json", "-g"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)[0]
    # The human table shortens to 7 chars; JSON keeps the full SHA.
    if obj["upstream_sha"] is not None:
        assert len(obj["upstream_sha"]) > 7, (
            "JSON output must keep the full SHA, not the 7-char short form"
        )


def test_skill_list_json_sorted_by_slug(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream, "b-skill").exit_code == 0
    assert _add_demo(runner, git_sandbox.upstream, "a-skill").exit_code == 0

    result = runner.invoke(main, ["skill", "list", "--json", "-g"])
    assert result.exit_code == 0, result.output
    slugs = [obj["slug"] for obj in json.loads(result.output)]
    assert slugs == ["a-skill", "b-skill"]


# ── -a/--agent filter ─────────────────────────────────────────────────────


def test_skill_list_agent_filter_unknown_agent_errors(
    tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "list", "-g", "-a", "nonsense",
    ])
    assert result.exit_code != 0
    assert "unknown agent" in result.output


def test_skill_list_agent_filter_universal_token(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """A skill installed under --agents universal is visible to -a universal."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0
    assert _install_universal(runner).exit_code == 0

    result = runner.invoke(main, [
        "skill", "list", "-g", "-a", "universal", "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [obj["slug"] for obj in data] == ["demo"]


def test_skill_list_agent_filter_drops_unlinked(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """A skill in the library but linked to no claude-code agent is filtered out."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0
    assert _install_universal(runner).exit_code == 0

    # `universal` install does not create a claude-code symlink (only the
    # universal bundle), so the claude-code filter drops the skill.
    result = runner.invoke(main, [
        "skill", "list", "-g", "-a", "claude-code", "--json",
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


def test_skill_list_agent_filter_with_json_keeps_format(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """--agent + --json compose: filtered result is still a JSON array."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0
    assert _install_universal(runner).exit_code == 0

    result = runner.invoke(main, [
        "skill", "list", "-g", "-a", "universal", "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["slug"] == "demo"
    assert data[0]["scope"] == "global"
