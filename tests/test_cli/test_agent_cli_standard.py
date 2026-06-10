"""CLI boundaries for the standard agents projection (#361).

Covers the four command-module seams:
  - install: `standard` token accepted, claude-code normalized to it,
    covered-aware default fan-out, synthetic catalog names rejected.
  - uninstall: same normalization/rejection; default stays MAXIMAL.
  - remove: `standard` prepended to the all-enabled set (no orphaned .attk).
  - status: the slot is reported ONCE as `standard`, never as claude-code.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main

# ---------------------------------------------------------------------------
# Helpers — same fixture patterns as test_cli_agent_group.py (library canonical
# at ~/.agent-toolkit/agents/<slug>/ + a global agents-lock entry).
# ---------------------------------------------------------------------------

_CONTENT = "---\nname: demo\ndescription: standard CLI test agent\n---\n\nBody.\n"


def _seed_global_canonical(slug: str = "demo") -> Path:
    """Create a global canonical with content file, honoring monkeypatched HOME."""
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir(slug, scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(_CONTENT)
    return canonical


def _write_global_lock(slug: str = "demo") -> None:
    """Write a minimal global lock entry so install treats the slug as known."""
    from agent_toolkit_cli.agent_lock import LockEntry, add_entry, read_lock, write_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=f"https://github.com/test/{slug}",
        source_type="github",
        agent_path=f"{slug}.md",
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset dev-shell env vars that would pollute destination paths."""
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


# ---------------------------------------------------------------------------
# install: token resolution + default fan-out
# ---------------------------------------------------------------------------


def test_resolve_harnesses_accepts_standard():
    from agent_toolkit_cli.commands.agent.install_cmd import _resolve_harnesses
    assert _resolve_harnesses("standard", "global") == ("standard",)


def test_resolve_harnesses_normalizes_claude_code():
    """claude-code names the same slot; normalizing prevents a dual-name
    delta where plan() removes one alias while installing the other."""
    from agent_toolkit_cli.commands.agent.install_cmd import _resolve_harnesses
    assert _resolve_harnesses("claude-code", "global") == ("standard",)
    assert _resolve_harnesses("claude-code,gemini-cli", "global") == ("standard", "gemini-cli")


def test_resolve_harnesses_dedupes_preserving_order():
    """standard + claude-code name ONE slot — resolve to a single token."""
    from agent_toolkit_cli.commands.agent.install_cmd import _resolve_harnesses
    assert _resolve_harnesses("standard,claude-code,pi", "global") == ("standard", "pi")


def test_default_fanout_standard_plus_noncovered():
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
    from agent_toolkit_cli.commands.agent.install_cmd import _default_harnesses
    got = _default_harnesses("global")
    assert got[0] == "standard"
    covered = agents_standard_covered("global")
    assert not (set(got[1:]) & covered)
    # Task 0 delta: cursor is covered at both scopes now — it must NOT
    # receive an individual default install; non-covered harnesses stay.
    assert "cursor" not in got
    assert "pi" in got and "gemini-cli" in got


def test_default_fanout_project_scope_excludes_devin():
    """devin reads the project-scope slot natively (covered) but NOT the
    global one — the covered filter must be per-scope."""
    from agent_toolkit_cli.commands.agent.install_cmd import _default_harnesses
    assert "devin" in _default_harnesses("global")
    assert "devin" not in _default_harnesses("project")


def test_synthetic_tokens_rejected():
    """AC7 (review-corrected): ALL synthetic catalog names get an explicit
    UsageError — previously a silent no-op. #350 aliases resolve first, so
    general-skill is rejected the same way."""
    import click
    from agent_toolkit_cli.commands.agent.install_cmd import _resolve_harnesses
    for tok in ("standard-agent", "standard-skill", "general-skill"):
        with pytest.raises(click.UsageError):
            _resolve_harnesses(tok, "global")


# ---------------------------------------------------------------------------
# uninstall: same normalization/rejection; default stays MAXIMAL
# ---------------------------------------------------------------------------


def test_uninstall_helper_rejects_synthetics():
    import click
    from agent_toolkit_cli.commands.agent.uninstall_cmd import (
        _resolve_harnesses_for_uninstall,
    )
    for tok in ("standard-agent", "standard-skill", "general-agent"):
        with pytest.raises(click.UsageError):
            _resolve_harnesses_for_uninstall(tok, "demo", "global", None, None)


def test_uninstall_helper_normalizes_claude_code():
    from agent_toolkit_cli.commands.agent.uninstall_cmd import (
        _resolve_harnesses_for_uninstall,
    )
    got = _resolve_harnesses_for_uninstall("claude-code", "demo", "global", None, None)
    assert got == ("standard",)


def test_uninstall_default_is_maximal():
    """The no-flag uninstall default keeps covered harnesses (asymmetric with
    the install default): pre-#361 installs wrote real own-dir files at
    kode/neovate/cortex which a covered-filtered default would orphan."""
    from agent_toolkit_cli.commands.agent.uninstall_cmd import (
        _resolve_harnesses_for_uninstall,
    )
    got = _resolve_harnesses_for_uninstall(None, "demo", "global", None, None)
    assert got[0] == "standard"
    for covered in ("kode", "neovate", "cortex", "cursor"):
        assert covered in got, f"maximal uninstall default must keep {covered}"


def test_default_uninstall_cleans_pre361_own_dir_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEFAULT uninstall (no --harnesses) after a pre-#361-style all-harness
    install leaves no projection files: the slot AND the covered harnesses'
    own-dir copies (kode/neovate/cortex) are all cleaned."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()

    runner = CliRunner()
    # Pre-#361 shape: explicit own-dir installs for covered harnesses plus
    # the slot itself (claude-code normalizes to standard on install).
    r_install = runner.invoke(
        main, ["agent", "install", "demo", "-g",
               "--harnesses", "claude-code,kode,neovate,cortex"],
    )
    assert r_install.exit_code == 0, r_install.output

    slot = tmp_path / ".claude" / "agents" / "demo.md"
    own_dir_files = [
        tmp_path / ".kode" / "agents" / "demo.md",
        tmp_path / ".neovate" / "agents" / "demo.md",
        tmp_path / ".snowflake" / "cortex" / "agents" / "demo.md",
    ]
    assert slot.exists(), "standard slot not created"
    for f in own_dir_files:
        assert f.exists(), f"own-dir projection not created: {f}"

    r_uninstall = runner.invoke(main, ["agent", "uninstall", "demo", "-g"])
    assert r_uninstall.exit_code == 0, r_uninstall.output

    assert not slot.exists(), "standard slot ORPHANED by default uninstall"
    sentinel = tmp_path / ".claude" / "agents" / ".demo.md.attk"
    assert not sentinel.exists(), "sentinel ORPHANED by default uninstall"
    for f in own_dir_files:
        assert not f.exists(), f"own-dir projection ORPHANED: {f}"


# ---------------------------------------------------------------------------
# remove: ("standard",) prepended — no orphaned .attk sidecar
# ---------------------------------------------------------------------------


def test_remove_after_standard_install_leaves_no_attk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()

    runner = CliRunner()
    r_install = runner.invoke(
        main, ["agent", "install", "demo", "-g", "--harnesses", "standard"],
    )
    assert r_install.exit_code == 0, r_install.output
    agents_dir = tmp_path / ".claude" / "agents"
    assert (agents_dir / "demo.md").exists()
    assert (agents_dir / ".demo.md.attk").exists()

    r_remove = runner.invoke(main, ["agent", "remove", "demo"])
    assert r_remove.exit_code == 0, r_remove.output
    assert not (agents_dir / "demo.md").exists()
    leftovers = list(agents_dir.glob("*.attk")) + list(agents_dir.glob(".*.attk"))
    assert leftovers == [], f"orphaned sentinel(s) after remove: {leftovers}"


# ---------------------------------------------------------------------------
# status: the slot is reported once, as `standard`
# ---------------------------------------------------------------------------


def test_projected_harnesses_reports_standard_once(tmp_path):
    from agent_toolkit_cli.commands.agent.status_cmd import _projected_harnesses
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    found = _projected_harnesses("demo", "global", tmp_path, None)
    assert "standard" in found
    assert "claude-code" not in found


def test_cli_status_reports_standard_after_claude_code_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: install via the claude-code spelling, status says standard."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()

    runner = CliRunner()
    r_install = runner.invoke(
        main, ["agent", "install", "demo", "-g", "--harnesses", "claude-code"],
    )
    assert r_install.exit_code == 0, r_install.output
    r = runner.invoke(main, ["agent", "status", "demo", "-g"])
    assert r.exit_code == 0, r.output
    assert "standard" in r.output
    assert "claude-code" not in r.output


# ---------------------------------------------------------------------------
# ownership contract through the CLI (PM review MINOR 6)
# ---------------------------------------------------------------------------


def test_cli_install_conflicts_on_foreign_slot_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI-layer pin for the ownership contract — a hand-authored,
    content-divergent ~/.claude/agents/<slug>.md must fail loud through
    `agent install`, even though the slug has a global lock entry (the
    facade's overwrite=True must not reach the guard)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()
    foreign = tmp_path / ".claude" / "agents" / "demo.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("hand-authored\n")
    r = CliRunner().invoke(main, ["agent", "install", "demo", "-g",
                                  "--harnesses", "standard"])
    assert r.exit_code != 0
    assert "refusing to overwrite" in r.output
    assert foreign.read_text() == "hand-authored\n"


def test_cli_install_refreshes_sentineled_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sentineled (tool-owned) slots refresh silently through the CLI."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("stale tool copy\n")
    _sentinel_path(slot).touch()
    r = CliRunner().invoke(main, ["agent", "install", "demo", "-g",
                                  "--harnesses", "standard"])
    assert r.exit_code == 0, r.output
    assert slot.read_text() == _CONTENT, "sentineled slot was not refreshed"
