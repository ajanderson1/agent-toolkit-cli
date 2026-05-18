"""_hook_dispatch.apply_link — atomic writes, 0o755 chmod, dry-run prints."""
from __future__ import annotations

import io
import os
import stat
from pathlib import Path

import pytest


def _make_adapter():
    from agent_toolkit_cli.harness_adapters.codex_hook import CodexHookAdapter
    return CodexHookAdapter()


def _make_entry(home: Path, name: str = "demo"):
    from agent_toolkit_cli.harness_adapters.base import HookEntry

    script_path = home / ".codex" / "agent-toolkit-hooks" / name / "check.sh"
    return HookEntry(
        name=name,
        events=("PreToolUse",),
        command=str(script_path),
        script_files={script_path: b"#!/usr/bin/env bash\necho hi\n"},
    )


def test_apply_link_creates_script_with_executable_mode(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._hook_dispatch import apply_link

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    adapter = _make_adapter()
    entry = _make_entry(tmp_path)
    out = io.StringIO()

    apply_link(
        adapter,
        scope="user",
        project_root=tmp_path,
        entries=[entry],
        dry_run=False,
        stdout=out,
    )

    script = tmp_path / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    assert script.is_file()
    mode = script.stat().st_mode
    # Owner +x at minimum.
    assert mode & stat.S_IXUSR, f"expected +x on owner, got {oct(mode)}"


def test_apply_link_dry_run_prints_would_create(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._hook_dispatch import apply_link

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    adapter = _make_adapter()
    entry = _make_entry(tmp_path)
    out = io.StringIO()

    apply_link(
        adapter,
        scope="user",
        project_root=tmp_path,
        entries=[entry],
        dry_run=True,
        stdout=out,
    )

    output = out.getvalue()
    assert "would-create" in output
    # Nothing written.
    script = tmp_path / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    assert not script.exists()


def test_apply_link_propagates_cannot_install(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._hook_dispatch import apply_link
    from agent_toolkit_cli.harness_adapters.base import CannotInstall, HookEntry

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    adapter = _make_adapter()
    bad = HookEntry(
        name="bad",
        events=("Boom",),  # unknown event
        command=str(tmp_path / ".codex" / "agent-toolkit-hooks" / "bad" / "x.sh"),
        script_files={},
    )
    out = io.StringIO()

    with pytest.raises(CannotInstall, match="unknown"):
        apply_link(
            adapter,
            scope="user",
            project_root=tmp_path,
            entries=[bad],
            dry_run=False,
            stdout=out,
        )


def test_build_hook_entries_reads_meta_and_script(tmp_path, monkeypatch):
    """_build_hook_entries reads hooks/<slug>/.meta.yaml + the script file."""
    from agent_toolkit_cli.commands._hook_dispatch import _build_hook_entries

    monkeypatch.setenv("HOME", str(tmp_path))

    toolkit = tmp_path / "toolkit"
    hook_dir = toolkit / "hooks" / "demo"
    hook_dir.mkdir(parents=True)
    (hook_dir / ".meta.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: demo\n"
        "  description: A demo hook.\n"
        "  kind: hook\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [codex]\n"
        "  hook:\n"
        "    events: [PreToolUse]\n"
        "    command: check.sh\n"
        "    matcher: '^Bash$'\n"
        "    timeout: 10\n",
        encoding="utf-8",
    )
    (hook_dir / "check.sh").write_bytes(b"#!/usr/bin/env bash\necho hi\n")

    entries = _build_hook_entries(toolkit, ["demo"])
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "demo"
    assert e.events == ("PreToolUse",)
    assert e.matcher == "^Bash$"
    assert e.timeout == 10
    expected_script = tmp_path / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    assert e.command == str(expected_script)
    assert e.script_files[expected_script] == b"#!/usr/bin/env bash\necho hi\n"


def test_build_hook_entries_skips_missing_assets(tmp_path):
    from agent_toolkit_cli.commands._hook_dispatch import _build_hook_entries

    toolkit = tmp_path / "toolkit"
    (toolkit / "hooks").mkdir(parents=True)
    # Slug "ghost" has no directory.
    entries = _build_hook_entries(toolkit, ["ghost"])
    assert entries == []
