"""Four-step resolution order: --toolkit-repo flag > AGENT_TOOLKIT_REPO env > walk-up marker > default."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root


def make_toolkit_repo(root: Path) -> Path:
    (root / "schemas").mkdir(parents=True)
    (root / "schemas" / "asset-frontmatter.v1alpha1.json").write_text("{}")
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
