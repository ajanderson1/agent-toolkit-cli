"""Four-step resolution order: --toolkit-repo flag > AGENT_TOOLKIT_REPO env > walk-up marker > default."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root


def make_toolkit_repo(root: Path) -> Path:
    (root / "schemas").mkdir(parents=True)
    (root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    return root


def test_explicit_flag_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag_repo = make_toolkit_repo(tmp_path / "flag")
    env_repo = make_toolkit_repo(tmp_path / "env")
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(env_repo))
    monkeypatch.chdir(tmp_path)
    assert resolve_toolkit_root(explicit=flag_repo) == flag_repo


def test_env_var_used_when_no_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_repo = make_toolkit_repo(tmp_path / "env")
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(env_repo))
    monkeypatch.chdir(tmp_path)
    assert resolve_toolkit_root(explicit=None) == env_repo


def test_walk_up_marker_when_no_flag_or_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_toolkit_repo(tmp_path / "repo")
    deep = repo / "skills" / "foo"
    deep.mkdir(parents=True)
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.chdir(deep)
    assert resolve_toolkit_root(explicit=None) == repo


def test_default_path_when_nothing_else(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    default = make_toolkit_repo(home / "GitHub" / "agent-toolkit")
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.setenv("HOME", str(home))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert resolve_toolkit_root(explicit=None) == default


def test_raises_when_nothing_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.setenv("HOME", str(home))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(RepoNotFoundError) as excinfo:
        resolve_toolkit_root(explicit=None)
    msg = str(excinfo.value)
    assert "agent-toolkit" in msg
    assert "uv tool install" in msg


def test_invalid_explicit_path_raises(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    with pytest.raises(RepoNotFoundError):
        resolve_toolkit_root(explicit=not_a_repo)


# CLI integration: each subcommand must honour the four-step order, not just
# the resolve_toolkit_root() function in isolation. A regression where a
# subcommand silently fell back to CWD would pass the unit tests above but
# fail these — see the bug introduced when commands set
# `toolkit_root = Path(".").resolve()` instead of calling the resolver.

def _populate_minimal_repo(root: Path) -> Path:
    """Build a toolkit repo with one valid asset for end-to-end CLI tests."""
    make_toolkit_repo(root)
    skill_dir = root / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: minimal test skill for resolution tests.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
        "# alpha\n"
    )
    return root


def test_cli_inventory_uses_env_var_when_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`agent-toolkit inventory` from a directory with no marker, no flag,
    and only $AGENT_TOOLKIT_REPO set must read from the env-var repo — not
    silently fall back to CWD and return an empty inventory."""
    from click.testing import CliRunner

    from agent_toolkit.cli import main

    repo = _populate_minimal_repo(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(repo))
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert '"slug": "alpha"' in result.output


def test_cli_check_uses_env_var_when_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`agent-toolkit check` from elsewhere with only $AGENT_TOOLKIT_REPO set
    must validate the env-var repo — not silently report '0 assets'."""
    from click.testing import CliRunner

    from agent_toolkit.cli import main

    repo = _populate_minimal_repo(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(repo))
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    result = runner.invoke(main, ["check", "--exit-code"])
    assert result.exit_code == 0, result.output
    assert "1 asset" in result.output


def test_cli_inventory_walk_up_finds_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With CWD inside a toolkit repo (deep subpath), no flag, no env, the
    CLI must walk up to the marker."""
    from click.testing import CliRunner

    from agent_toolkit.cli import main

    repo = _populate_minimal_repo(tmp_path / "repo")
    deep = repo / "skills" / "alpha"
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.chdir(deep)
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert '"slug": "alpha"' in result.output


def test_cli_inventory_errors_when_nothing_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no flag, no env, no marker walk-up, and no default repo, the CLI
    must error (not silently return an empty inventory)."""
    from click.testing import CliRunner

    from agent_toolkit.cli import main

    home = tmp_path / "empty-home"
    home.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "--format", "json"])
    assert result.exit_code != 0
    assert "Cannot find an agent-toolkit repo" in result.output
