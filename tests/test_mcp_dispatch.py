"""Dispatcher: apply_link orchestration, atomic write, loud-print contract."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest


def _seed_mcp(toolkit_root: Path, slug: str = "context7", *,
              transport: str = "stdio", command: str = "npx",
              args: list[str] | None = None) -> None:
    mcp_dir = toolkit_root / "mcps" / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    inner = {"type": transport, "command": command}
    if args:
        inner["args"] = args
    (mcp_dir / "config.json").write_text(json.dumps(inner) + "\n")
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} mcp.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - codex\n"
        "  mcp:\n"
        f"    transport: {transport}\n"
        "    install_method: npx\n"
        "---\n"
    )


def test_build_mcp_entries_resolves_slug_to_mcpentry(tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "context7"
    assert e.inner_config["command"] == "npx"
    assert e.mcp_spec["transport"] == "stdio"


def test_build_mcp_entries_skips_unknown_slug(tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries

    _seed_mcp(tmp_path, "context7")
    entries = _build_mcp_entries(tmp_path, ["context7", "does-not-exist"])
    assert len(entries) == 1
    assert entries[0].name == "context7"


def test_build_mcp_entries_skips_when_readme_missing(tmp_path):
    """A slug whose mcps/<slug>/README.md is missing is skipped (not an error)."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries

    mcp_dir = tmp_path / "mcps" / "incomplete"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"command":"npx"}\n')
    # No README.md.

    entries = _build_mcp_entries(tmp_path, ["incomplete"])
    assert entries == []


def test_apply_link_dry_run_prints_would_op_no_write(monkeypatch, tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    buf = io.StringIO()
    actions = apply_link(
        a, scope="user", project_root=tmp_path, entries=entries,
        dry_run=True, stdout=buf,
    )
    out = buf.getvalue()
    assert "would-create" in out
    assert str(target) in out
    assert not target.exists()
    assert len(actions) == 1
    assert actions[0].op == "create"


def test_apply_link_real_run_writes_atomically_and_prints_loud(monkeypatch, tmp_path):
    """Real run: writes bytes, prints `→ creating ...` then `✓ created ...`."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    buf = io.StringIO()
    actions = apply_link(
        a, scope="user", project_root=tmp_path, entries=entries,
        dry_run=False, stdout=buf,
    )
    out = buf.getvalue()
    assert "→ creating" in out
    assert "✓ created" in out
    assert str(target) in out
    assert target.is_file()
    text = target.read_text()
    assert "[mcp_servers.context7]" in text
    assert len(actions) == 1
    assert actions[0].op == "create"


def test_apply_link_update_prints_byte_delta(monkeypatch, tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"
    target.write_text("model_provider = \"openai\"\n")

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    buf = io.StringIO()
    apply_link(a, scope="user", project_root=tmp_path, entries=entries,
               dry_run=False, stdout=buf)
    out = buf.getvalue()
    assert "→ updating" in out
    assert "✓ updated" in out


def test_apply_link_unchanged_prints_nothing(monkeypatch, tmp_path):
    """When already in sync, no pre/post print, no write, mtime preserved."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    # First run: create.
    buf1 = io.StringIO()
    apply_link(a, scope="user", project_root=tmp_path, entries=entries,
               dry_run=False, stdout=buf1)
    mtime_before = target.stat().st_mtime_ns

    # Second run: should be no-op.
    buf2 = io.StringIO()
    actions = apply_link(a, scope="user", project_root=tmp_path, entries=entries,
                         dry_run=False, stdout=buf2,
                         previously_allowed={"context7"})
    assert buf2.getvalue() == ""
    assert actions == []
    assert target.stat().st_mtime_ns == mtime_before


def test_apply_link_unlink_uses_previously_allowed(monkeypatch, tmp_path):
    """Unlink semantics: empty entries + previously_allowed → adapter removes the entry."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    # Link.
    buf1 = io.StringIO()
    apply_link(a, scope="user", project_root=tmp_path, entries=entries,
               dry_run=False, stdout=buf1)
    assert "[mcp_servers.context7]" in target.read_text()

    # Unlink: no entries, but previously_allowed says we owned context7.
    buf2 = io.StringIO()
    actions = apply_link(a, scope="user", project_root=tmp_path, entries=[],
                         dry_run=False, stdout=buf2,
                         previously_allowed={"context7"})
    assert "→ updating" in buf2.getvalue() or "→ deleting" in buf2.getvalue()
    assert "[mcp_servers.context7]" not in target.read_text()
    assert len(actions) == 1


def test_apply_link_raises_on_cannot_install(monkeypatch, tmp_path):
    """Adapter.can_install raising CannotInstall propagates up; caller decides."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    _seed_mcp(tmp_path, "bad-mcp", transport="http")
    entries = _build_mcp_entries(tmp_path, ["bad-mcp"])
    a = get_adapter("codex")

    buf = io.StringIO()
    with pytest.raises(CannotInstall, match="stdio"):
        apply_link(a, scope="user", project_root=tmp_path, entries=entries,
                   dry_run=False, stdout=buf)


def test_apply_link_unimplemented_adapter_is_silent_noop(monkeypatch, tmp_path):
    """Unimplemented adapter returns []; caller is responsible for the skip-print
    (apply_link itself does nothing — caller should detect and print skip_message).

    Pi remains UnimplementedAdapter (Pi has no MCP support by design).
    """
    from agent_toolkit.commands._mcp_dispatch import apply_link
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.base import UnimplementedAdapter

    monkeypatch.setenv("HOME", str(tmp_path))

    a = get_adapter("pi")  # UnimplementedAdapter
    assert isinstance(a, UnimplementedAdapter), (
        "Test assumes pi remains unimplemented — update if pi MCP support is ever added."
    )

    buf = io.StringIO()
    actions = apply_link(a, scope="user", project_root=tmp_path, entries=[],
                         dry_run=False, stdout=buf)
    assert actions == []
    assert buf.getvalue() == ""


def test_atomic_write_uses_same_directory_temp_file(tmp_path):
    """Atomic-write helper writes via temp file in target.parent then replaces."""
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    target = tmp_path / "out.toml"
    payload = b"hello\n"
    _atomic_write_bytes(target, payload)
    assert target.read_bytes() == payload
    leftovers = [p for p in tmp_path.iterdir() if p.name != "out.toml"]
    assert leftovers == [], leftovers


def test_atomic_write_creates_parent_dirs(tmp_path):
    """_atomic_write_bytes creates parent dirs if missing."""
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    target = tmp_path / "deep" / "nested" / "out.toml"
    _atomic_write_bytes(target, b"x\n")
    assert target.read_bytes() == b"x\n"


def test_atomic_write_cleans_up_temp_on_failure(monkeypatch, tmp_path):
    """If os.replace raises, the temp file is cleaned up."""
    import os
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    target = tmp_path / "out.toml"

    real_replace = os.replace

    def boom(src, dst):
        raise OSError("simulated failure")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated failure"):
        _atomic_write_bytes(target, b"never lands\n")

    # No temp leftovers.
    leftovers = list(tmp_path.iterdir())
    assert leftovers == [], leftovers
