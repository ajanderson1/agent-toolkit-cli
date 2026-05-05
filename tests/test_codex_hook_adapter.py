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


import shutil


FIXTURE = Path(__file__).parent / "_fixtures" / "codex_config_realistic_with_hooks.toml"


def _seed_home(tmp_path: Path, monkeypatch) -> Path:
    """Create $HOME/.codex/ and return tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    return tmp_path


def test_codex_hook_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No config.toml on disk → create-action with rendered TOML + create-action per script file."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    actions = a.diff("user", tmp_path, [entry])

    # One config.toml create + one script file create.
    paths = {act.path for act in actions}
    assert (home / ".codex" / "config.toml") in paths
    assert (home / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh") in paths
    for act in actions:
        assert act.op == "create"
        assert act.contents is not None


def test_codex_hook_diff_round_trip_byte_equal(monkeypatch, tmp_path):
    """link → write → re-diff should be empty."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    actions = a.diff("user", tmp_path, [entry])
    for act in actions:
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    # Re-diff should be empty.
    actions2 = a.diff("user", tmp_path, [entry])
    assert actions2 == []


def test_codex_hook_diff_unlink_byte_equal_to_original(monkeypatch, tmp_path):
    """link → write → unlink → write should restore byte-equality with the original."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    target = home / ".codex" / "config.toml"
    shutil.copy(FIXTURE, target)
    original = target.read_bytes()

    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    # Link.
    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    # Verify the user-owned hook is still intact in the file.
    after_link = target.read_text(encoding="utf-8")
    assert "/usr/local/bin/my-bash-guard.sh" in after_link
    assert "demo/check.sh" in after_link

    # Unlink.
    for act in a.diff("user", tmp_path, [], previously_allowed={"demo"}):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)
        elif act.op == "delete":
            try:
                act.path.unlink()
            except (FileNotFoundError, IsADirectoryError, PermissionError):
                # unlink() raises IsADirectoryError on Linux and PermissionError
                # on macOS when the path is a directory — skip; the test only
                # cares about byte-equality of config.toml after the operation.
                pass

    assert target.read_bytes() == original


def test_codex_hook_diff_preserves_hand_rolled_groups(monkeypatch, tmp_path):
    """A user-authored matcher-group whose command is not under script_root must survive a link."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    target = home / ".codex" / "config.toml"
    shutil.copy(FIXTURE, target)

    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    rendered = target.read_text(encoding="utf-8")
    # User-owned hook still present.
    assert "/usr/local/bin/my-bash-guard.sh" in rendered
    # Toolkit hook also present.
    assert "agent-toolkit-hooks/demo/check.sh" in rendered


def test_codex_hook_diff_multi_event_produces_one_group_per_event(monkeypatch, tmp_path):
    """An entry with events=(PreToolUse, Stop) appears under both event arrays."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(events=("PreToolUse", "Stop"), home=home)

    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    rendered = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[[hooks.PreToolUse]]" in rendered
    assert "[[hooks.Stop]]" in rendered


def test_codex_hook_entry_drift_detects_changed_script(monkeypatch, tmp_path):
    """Drift = on-disk script bytes differ from entry's rendered bytes."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False

    # Mutate the on-disk script.
    script_path = home / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    script_path.write_bytes(b"#!/usr/bin/env bash\necho TAMPERED\n")

    assert a.entry_drift("user", tmp_path, entry) is True


def test_codex_hook_diff_preserves_hand_rolled_unknown_event(monkeypatch, tmp_path):
    """A hand-rolled group under an unknown future event must survive a link+unlink cycle.

    The empty-[hooks] check at the end of _merge_hooks must inspect actual
    keys in the table, not just the six known events. Otherwise a future
    Codex event with user content would be silently destroyed.
    """
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    target = home / ".codex" / "config.toml"

    # Pre-existing config: only a hand-rolled hook under an UNKNOWN event.
    target.write_text(
        '[[hooks.FutureEvent]]\n'
        'matcher = "^Bash$"\n'
        '\n'
        '[[hooks.FutureEvent.hooks]]\n'
        'type = "command"\n'
        'command = "/usr/local/bin/future.sh"\n',
        encoding="utf-8",
    )
    original = target.read_bytes()

    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    # Link.
    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    rendered = target.read_text(encoding="utf-8")
    assert "[[hooks.FutureEvent]]" in rendered, "unknown-event hand-rolled group must survive link"
    assert "/usr/local/bin/future.sh" in rendered

    # Unlink.
    for act in a.diff("user", tmp_path, [], previously_allowed={"demo"}):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)
        elif act.op == "delete":
            try:
                act.path.unlink()
            except (FileNotFoundError, IsADirectoryError, PermissionError):
                pass

    after = target.read_bytes()
    # The unknown-event group must still be present after unlink.
    assert b"[[hooks.FutureEvent]]" in after
    assert b"/usr/local/bin/future.sh" in after
