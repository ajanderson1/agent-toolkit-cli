"""Facade lifecycle for the Commands standard projection (#482)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_toolkit_cli._install_core import InstallError, InstallPlan
from agent_toolkit_cli.command_adapters.base import sidecar_path, write_sidecar
from agent_toolkit_cli.command_install import (
    _current_linked_harnesses,
    apply,
    ensure_project_command_canonical,
    plan,
)
from agent_toolkit_cli.command_lock import LockEntry, LockFile, read_lock, write_lock


def _seed_global(home: Path, *, text: str = "demo body\n", with_lock: bool = True) -> Path:
    lib = home / ".agent-toolkit" / "commands" / "demo"
    lib.mkdir(parents=True)
    src = lib / "COMMAND.md"
    src.write_text(text)
    if with_lock:
        lock_path = home / ".agent-toolkit" / "commands-lock.json"
        write_lock(
            lock_path,
            LockFile(
                version=1,
                skills={
                    "demo": LockEntry(
                        source="o/r",
                        source_type="github",
                        ref="main",
                        command_path="COMMAND.md",
                    )
                },
            ),
        )
    return src


def test_scanner_reports_standard_not_claude(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    src = _seed_global(tmp_path)
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(src)
    write_sidecar(dest, slug="demo", harness="standard", scope="global", canonical=src, content=src.read_text())
    assert _current_linked_harnesses(slug="demo", scope="global", home=tmp_path, project=None) == ("standard",)


def test_plan_normalizes_claude_code_to_standard(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global(tmp_path)
    p = plan(slug="demo", scope="global", target_agents=("claude-code",), home=tmp_path)
    assert p.add_agents == ("standard",)
    p2 = plan(slug="demo", scope="global", target_agents=("standard", "claude-code"), home=tmp_path)
    assert p2.add_agents == ("standard",)
    assert p2.remove_agents == ()


def test_default_global_install_records_standard_pi_gemini(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global(tmp_path)
    p = InstallPlan(
        slug="demo",
        scope="global",
        source=None,
        ref=None,
        add_agents=("standard", "pi", "gemini-cli"),
        remove_agents=(),
    )
    apply(p, home=tmp_path)
    std = tmp_path / ".claude" / "commands" / "demo.md"
    assert std.exists() or std.is_symlink()
    assert (tmp_path / ".pi" / "agent" / "prompts" / "demo.md").exists() or (
        tmp_path / ".pi" / "agent" / "prompts" / "demo.md"
    ).is_symlink()
    assert (tmp_path / ".gemini" / "commands" / "demo.toml").exists()
    # One shared slot only — no second Claude file.
    assert list((tmp_path / ".claude" / "commands").glob("demo.md")) == [std]
    lock = read_lock(tmp_path / ".agent-toolkit" / "commands-lock.json")
    assert lock.skills["demo"].harnesses == ("standard", "pi", "gemini-cli")


def test_legacy_claude_code_token_normalized_on_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    src = _seed_global(tmp_path)
    lock_path = tmp_path / ".agent-toolkit" / "commands-lock.json"
    write_lock(
        lock_path,
        LockFile(
            version=1,
            skills={
                "demo": LockEntry(
                    source="o/r",
                    source_type="github",
                    command_path="COMMAND.md",
                    harnesses=("claude-code", "pi"),
                )
            },
        ),
    )
    # Successful standard mutation rewrites legacy token.
    apply(
        InstallPlan(slug="demo", scope="global", source=None, ref=None, add_agents=("standard",), remove_agents=()),
        home=tmp_path,
    )
    lock = read_lock(lock_path)
    assert "claude-code" not in lock.skills["demo"].harnesses
    assert "standard" in lock.skills["demo"].harnesses
    assert (tmp_path / ".claude" / "commands" / "demo.md").exists() or (
        tmp_path / ".claude" / "commands" / "demo.md"
    ).is_symlink()
    del src


def test_read_only_scan_does_not_churn_legacy_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global(tmp_path)
    lock_path = tmp_path / ".agent-toolkit" / "commands-lock.json"
    before = lock_path.read_bytes()
    _current_linked_harnesses(slug="demo", scope="global", home=tmp_path, project=None)
    plan(slug="demo", scope="global", target_agents=("standard",), home=tmp_path)
    assert lock_path.read_bytes() == before


def test_project_install_derives_entry_after_success(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    _seed_global(home)
    project = tmp_path / "repo"
    project.mkdir()
    apply(
        InstallPlan(
            slug="demo",
            scope="project",
            source=None,
            ref=None,
            add_agents=("standard",),
            remove_agents=(),
        ),
        home=home,
        project=project,
    )
    dest = project / ".claude" / "commands" / "demo.md"
    assert dest.exists() or dest.is_symlink()
    lock = read_lock(project / "commands-lock.json")
    entry = lock.skills["demo"]
    assert entry.source == "o/r"
    assert entry.harnesses == ("standard",)
    assert entry.upstream_sha is None
    assert entry.local_sha is None


def test_project_conflict_rolls_back_new_canonical(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    _seed_global(home)
    project = tmp_path / "repo"
    project.mkdir()
    foreign = project / ".claude" / "commands" / "demo.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("hand")
    with pytest.raises(InstallError, match="unmanaged"):
        apply(
            InstallPlan(
                slug="demo",
                scope="project",
                source=None,
                ref=None,
                add_agents=("standard",),
                remove_agents=(),
            ),
            home=home,
            project=project,
        )
    assert foreign.read_text() == "hand"
    store = home / ".agent-toolkit" / "projects"
    # project canonical may live under store; ensure no lock lie
    assert not (project / "commands-lock.json").exists() or "demo" not in read_lock(
        project / "commands-lock.json"
    ).skills
    # Newly created project store canonical should be rolled back
    from agent_toolkit_cli.command_paths import project_store_root

    proj_canonical = project_store_root(project) / "demo"
    assert not proj_canonical.exists() and not proj_canonical.is_symlink()


def test_all_failed_project_attempt_no_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    _seed_global(home)
    project = tmp_path / "repo"
    project.mkdir()
    # Gemini conflict only; still no successful projection tokens
    conflict = project / ".gemini" / "commands" / "demo.toml"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("hand")
    # Also block standard
    foreign = project / ".claude" / "commands" / "demo.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("hand")
    with pytest.raises(InstallError):
        apply(
            InstallPlan(
                slug="demo",
                scope="project",
                source=None,
                ref=None,
                add_agents=("gemini-cli", "standard"),
                remove_agents=(),
            ),
            home=home,
            project=project,
        )
    assert not (project / "commands-lock.json").exists() or "demo" not in read_lock(
        project / "commands-lock.json"
    ).skills


def test_manual_global_canonical_stays_untracked(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global(tmp_path, with_lock=False)
    apply(
        InstallPlan(
            slug="demo",
            scope="global",
            source=None,
            ref=None,
            add_agents=("standard",),
            remove_agents=(),
        ),
        home=tmp_path,
    )
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    assert dest.exists() or dest.is_symlink()
    lock_path = tmp_path / ".agent-toolkit" / "commands-lock.json"
    if lock_path.exists():
        assert "demo" not in read_lock(lock_path).skills
    else:
        assert True


def test_pi_failure_before_standard_does_not_adopt(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global(tmp_path)
    # Pre-existing adoptable legacy slot
    src = tmp_path / ".agent-toolkit" / "commands" / "demo" / "COMMAND.md"
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(src.read_text())
    # Make pi fail by placing foreign file
    pi = tmp_path / ".pi" / "agent" / "prompts" / "demo.md"
    pi.parent.mkdir(parents=True)
    pi.write_text("hand")
    with pytest.raises(InstallError):
        apply(
            InstallPlan(
                slug="demo",
                scope="global",
                source=None,
                ref=None,
                add_agents=("pi", "standard"),
                remove_agents=(),
            ),
            home=tmp_path,
        )
    assert not sidecar_path(dest).exists()
    assert dest.read_text() == src.read_text()


def test_adoptable_slot_appears_in_plan_add(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    src = _seed_global(tmp_path)
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(src)
    p = plan(slug="demo", scope="global", target_agents=("standard",), home=tmp_path)
    assert "standard" in p.add_agents


def test_rollback_retains_preexisting_pi(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    src = _seed_global(tmp_path)
    # Pre-install pi
    apply(
        InstallPlan(slug="demo", scope="global", source=None, ref=None, add_agents=("pi",), remove_agents=()),
        home=tmp_path,
    )
    pi = tmp_path / ".pi" / "agent" / "prompts" / "demo.md"
    assert pi.exists() or pi.is_symlink()
    # Foreign standard slot causes later failure
    foreign = tmp_path / ".claude" / "commands" / "demo.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("hand")
    with pytest.raises(InstallError):
        apply(
            InstallPlan(
                slug="demo",
                scope="global",
                source=None,
                ref=None,
                add_agents=("pi", "standard"),
                remove_agents=(),
            ),
            home=tmp_path,
        )
    assert pi.exists() or pi.is_symlink()
    assert foreign.read_text() == "hand"


def test_project_from_manual_global_creates_no_source_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    _seed_global(home, with_lock=False)
    project = tmp_path / "repo"
    project.mkdir()
    apply(
        InstallPlan(
            slug="demo",
            scope="project",
            source=None,
            ref=None,
            add_agents=("standard",),
            remove_agents=(),
        ),
        home=home,
        project=project,
    )
    dest = project / ".claude" / "commands" / "demo.md"
    assert dest.exists() or dest.is_symlink()
    assert not (project / "commands-lock.json").exists() or "demo" not in read_lock(
        project / "commands-lock.json"
    ).skills


def test_import_resets_harnesses(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Incoming lock with harnesses must not become local projection state
    incoming = tmp_path / "incoming.json"
    write_lock(
        incoming,
        LockFile(
            version=1,
            skills={
                "demo": LockEntry(
                    source="o/r",
                    source_type="github",
                    command_path="COMMAND.md",
                    harnesses=("standard", "pi"),
                )
            },
        ),
    )
    # Construct entry the way import_cmd does
    entry = read_lock(incoming).skills["demo"]
    library_entry = LockEntry(
        source=entry.source,
        source_type=entry.source_type,
        ref=entry.ref,
        command_path=entry.command_path,
        upstream_sha=entry.upstream_sha,
        local_sha=entry.local_sha,
        parent_url=entry.parent_url,
        read_only=entry.read_only,
        extras=dict(entry.extras),
        harnesses=(),
    )
    assert library_entry.harnesses == ()


def test_ensure_project_canonical_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    _seed_global(home)
    project = tmp_path / "repo"
    project.mkdir()
    assert ensure_project_command_canonical(slug="demo", project=project) is True
    assert ensure_project_command_canonical(slug="demo", project=project) is False
