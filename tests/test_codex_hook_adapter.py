"""CodexHookAdapter — ConfigFileFolderAdapter for ~/.codex/config.toml [hooks]."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_entry(name: str = "demo", *, events: tuple[str, ...] = ("PreToolUse",),
                command: str | None = None, matcher: str | None = None,
                timeout: int | None = None, async_: bool = False,
                status_message: str | None = None,
                script_files: dict[Path, bytes] | None = None,
                home: Path | None = None):
    from agent_toolkit.harness_adapters.base import HookEntry

    if home is None:
        home = Path("/tmp")  # tests pass home explicitly when relevant
    if command is None:
        command = str(home / ".codex" / "agent-toolkit-hooks" / name / "check.sh")
    if script_files is None:
        script_files = {Path(command): b"#!/usr/bin/env bash\necho hi\n"}
    return HookEntry(
        name=name, events=events, command=command, matcher=matcher,
        timeout=timeout, async_=async_, status_message=status_message,
        script_files=script_files,
    )


def test_codex_hook_adapter_basic_attrs():
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = CodexHookAdapter()
    assert a.name == "codex"
    assert a.strategy == "config_file+folder"


def test_codex_hook_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".codex" / "config.toml"


def test_codex_hook_user_script_root(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    assert a.script_root("user", tmp_path) == tmp_path / ".codex" / "agent-toolkit-hooks"


def test_codex_hook_project_scope_returns_none(tmp_path):
    """PR1 is user-scope only — project scope returns None to silently skip."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = CodexHookAdapter()
    assert a.config_target("project", tmp_path) is None
    assert a.script_root("project", tmp_path) is None


def test_codex_hook_can_install_accepts_known_events(tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = CodexHookAdapter()
    a.can_install(_make_entry(events=("PreToolUse", "Stop"), home=tmp_path))  # no exception


def test_codex_hook_can_install_refuses_unknown_event(tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = CodexHookAdapter()
    with pytest.raises(CannotInstall, match="unknown.*Boom"):
        a.can_install(_make_entry(events=("Boom",), home=tmp_path))


def test_codex_hook_can_install_refuses_empty_events(tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = CodexHookAdapter()
    with pytest.raises(CannotInstall, match="at least one event"):
        a.can_install(_make_entry(events=(), home=tmp_path))


def test_codex_hook_can_install_refuses_command_outside_script_root(monkeypatch, tmp_path):
    """can_install does a substring check for `.codex/agent-toolkit-hooks/<slug>/`
    in the command path. It does NOT anchor to $HOME — that's the dispatcher's
    job at write time, where scope/project_root are available. This test
    exercises the truly-bad case (no .codex segment at all)."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    bad = _make_entry(command="/usr/local/bin/some-script", home=tmp_path)
    with pytest.raises(CannotInstall, match="must live under"):
        a.can_install(bad)


def test_codex_hook_list_installed_returns_empty_when_root_missing(monkeypatch, tmp_path):
    """No ~/.codex/agent-toolkit-hooks/ directory → empty set."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_codex_hook_list_installed_returns_slug_dirs(monkeypatch, tmp_path):
    """list_installed returns the names of slug subdirectories under script_root."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    root = tmp_path / ".codex" / "agent-toolkit-hooks"
    root.mkdir(parents=True)
    (root / "alpha").mkdir()
    (root / "beta").mkdir()
    # A regular file at the root must be ignored — only directories count as slugs.
    (root / "stray.txt").write_text("noise", encoding="utf-8")

    a = CodexHookAdapter()
    assert a.list_installed("user", tmp_path) == {"alpha", "beta"}
