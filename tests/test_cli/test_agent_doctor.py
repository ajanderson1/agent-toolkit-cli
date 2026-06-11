"""Doctor standard-slot findings (#361).

The shared `.claude/agents/` dir is the standard agents slot AND the primary
place users hand-author Claude Code subagents. The ONLY per-file ownership
record there is the `.attk` sidecar sentinel — "no lock entry" must NEVER
imply an rm fix. Doctor distinguishes:

  - standard-slot-drift            slot differs from the SCOPE-APPROPRIATE canonical
  - standard-slot-orphan           sentineled (tool-written) slot file, no lock entry
  - standard-slot-unmanaged        sentinel-less file, no lock entry — report-only
  - standard-slot-dangling-sidecar sidecar without its slot file
  - cursor-shadow                  stale .cursor/agents copy shadowing the slot

Fixture conventions mirror test_cli_agent_group.py (library canonical at
~/.agent-toolkit/agents/<slug>/ + a global agents-lock entry, monkeypatched
HOME).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.agent_adapters import _sentinel_path
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTENT = "---\nname: demo-agent\ndescription: doctor test agent\n---\n\nBody.\n"
_DIVERGED = _CONTENT + "\nLocal edit that diverges from the canonical.\n"


def _seed_global_canonical(slug: str = "demo-agent", content: str = _CONTENT) -> Path:
    """Create a global canonical with content file, honoring monkeypatched HOME."""
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir(slug, scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(content)
    return canonical


def _seed_project_canonical(
    project: Path, slug: str = "demo-agent", content: str = _CONTENT,
) -> Path:
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir(slug, scope="project", project=project)
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(content)
    return canonical


def _write_lock(lock_path: Path, slug: str = "demo-agent") -> None:
    from agent_toolkit_cli.agent_lock import LockEntry, add_entry, read_lock, write_lock
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=f"https://github.com/test/{slug}",
        source_type="github",
        agent_path=f"{slug}.md",
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def _write_global_lock(slug: str = "demo-agent") -> None:
    from agent_toolkit_cli.agent_paths import library_lock_path
    _write_lock(library_lock_path(), slug)


def _write_project_lock(project: Path, slug: str = "demo-agent") -> None:
    from agent_toolkit_cli.agent_paths import lock_file_path
    _write_lock(lock_file_path(scope="project", project=project), slug)


def _write_slot(base: Path, slug: str = "demo-agent", content: str = _CONTENT,
                sentinel: bool = True) -> Path:
    """Write a standard-slot file under <base>/.claude/agents/."""
    slot = base / ".claude" / "agents" / f"{slug}.md"
    slot.parent.mkdir(parents=True, exist_ok=True)
    slot.write_text(content)
    if sentinel:
        _sentinel_path(slot).write_text("")
    return slot


def _by_type(findings: list, finding_type: str) -> list:
    return [f for f in findings if f.finding_type == finding_type]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset dev-shell env vars that would pollute destination paths."""
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


# ---------------------------------------------------------------------------
# standard-slot-drift
# ---------------------------------------------------------------------------


def test_doctor_flags_standard_slot_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locked slug whose slot diverges from the canonical → drift finding."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical()
    _write_global_lock()
    slot = _write_slot(tmp_path, content=_DIVERGED)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    drift = _by_type(findings, "standard-slot-drift")
    assert len(drift) == 1, [f.finding_type for f in findings]
    f = drift[0]
    assert f.slug == "demo-agent"
    assert f.path == slot
    # Review-mandated disclosure: the fix overwrites local edits.
    assert "DISCARDED" in f.detail
    assert f.fix_action is not None
    # Diff-first preview so the user can inspect before applying.
    assert f.fix_action.shell_preview.startswith("diff ")
    assert "cp " in f.fix_action.shell_preview

    # CLI surface names the finding.
    r = CliRunner().invoke(main, ["agent", "doctor", "-g", "--no-fix"])
    assert r.exit_code != 0, r.output
    assert "standard-slot-drift" in r.output

    # Applying the fix re-seeds the slot from the canonical.
    f.fix_action.apply()
    assert slot.read_text() == (canonical / "demo-agent.md").read_text()


def test_doctor_clean_when_slot_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Byte-equal slot (with sentinel) → NO standard-slot* findings."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()
    _write_slot(tmp_path, content=_CONTENT)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    standard = [f for f in findings if f.finding_type.startswith("standard-slot")]
    assert standard == [], [f.finding_type for f in findings]

    r = CliRunner().invoke(main, ["agent", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "clean" in r.output.lower()


# ---------------------------------------------------------------------------
# standard-slot-orphan vs standard-slot-unmanaged (sentinel-aware sweep)
# ---------------------------------------------------------------------------


def test_doctor_flags_sentineled_orphan_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rm fix ONLY for sentineled (tool-written) strays; user files are
    report-only — .claude/agents/ is where users hand-author subagents."""
    monkeypatch.setenv("HOME", str(tmp_path))
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    # Tool-written stray: sentinel present, lock entry gone.
    stray = agents_dir / "tool-stray.md"
    stray.write_text(_CONTENT)
    _sentinel_path(stray).write_text("")
    # Hand-authored agent: no sentinel, no lock entry.
    advisor = agents_dir / "my-advisor.md"
    advisor.write_text("# hand-authored advisor\n")

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)

    orphans = _by_type(findings, "standard-slot-orphan")
    assert [f.slug for f in orphans] == ["tool-stray"]
    assert orphans[0].fix_action is not None
    assert "rm" in orphans[0].fix_action.shell_preview

    unmanaged = _by_type(findings, "standard-slot-unmanaged")
    assert [f.slug for f in unmanaged] == ["my-advisor"]
    # NEVER offer rm for a user-authored file: report-only.
    assert unmanaged[0].fix_action is None

    # Applying the orphan fix removes the slot file AND its sidecar.
    orphans[0].fix_action.apply()
    assert not stray.exists()
    assert not _sentinel_path(stray).exists()
    assert advisor.exists(), "user-authored file must never be touched"


def test_doctor_sweep_skipped_when_slug_filtered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A targeted run (explicit slugs) does not sweep the standard dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "my-advisor.md").write_text("# hand-authored advisor\n")

    findings = _diagnose(
        slugs=("demo-agent",), scope="global", home=tmp_path, project=None,
    )
    assert _by_type(findings, "standard-slot-unmanaged") == []


# ---------------------------------------------------------------------------
# standard-slot-dangling-sidecar
# ---------------------------------------------------------------------------


def test_doctor_flags_dangling_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sidecar without its slot file → finding with rm-sidecar fix (a stale
    sentinel would authorize a future silent overwrite via _guard_foreign)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    side = agents_dir / ".ghost.md.attk"
    side.write_text("")

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    dangling = _by_type(findings, "standard-slot-dangling-sidecar")
    assert len(dangling) == 1, [f.finding_type for f in findings]
    assert dangling[0].path == side
    assert dangling[0].fix_action is not None

    dangling[0].fix_action.apply()
    assert not side.exists()


def test_doctor_sidecar_with_main_file_not_dangling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sidecar whose slot file exists is NOT dangling."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical()
    _write_global_lock()
    _write_slot(tmp_path, content=_CONTENT, sentinel=True)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert _by_type(findings, "standard-slot-dangling-sidecar") == []


# ---------------------------------------------------------------------------
# project scope: drift baseline is the PROJECT canonical
# ---------------------------------------------------------------------------


def test_doctor_project_drift_uses_project_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A project slot matching the PROJECT canonical is clean even when the
    global library holds a different version of the same slug."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    # Global library holds a DIVERGED version of the same slug.
    _seed_global_canonical(content=_DIVERGED)
    # Project canonical + project lock + slot seeded from the project canonical.
    _seed_project_canonical(project, content=_CONTENT)
    _write_project_lock(project)
    _write_slot(project, content=_CONTENT)

    findings = _diagnose(
        slugs=None, scope="project", home=None, project=project,
    )
    assert _by_type(findings, "standard-slot-drift") == [], (
        [f"{f.finding_type}: {f.detail}" for f in findings]
    )

    r = CliRunner().invoke(
        main, ["--project", str(project), "agent", "doctor", "-p"],
    )
    assert r.exit_code == 0, r.output
    assert "clean" in r.output.lower()


# ---------------------------------------------------------------------------
# cursor-shadow: .cursor/agents/<slug>.md wins name conflicts over the slot
# ---------------------------------------------------------------------------


def _seed_locked_slug_with_matching_slot(tmp_path: Path) -> Path:
    """Locked slug + byte-equal sentineled slot — clean baseline."""
    _seed_global_canonical()
    _write_global_lock()
    return _write_slot(tmp_path, content=_CONTENT)


def _write_cursor_file(tmp_path: Path, content: str, sentinel: bool) -> Path:
    cursor_dest = tmp_path / ".cursor" / "agents" / "demo-agent.md"
    cursor_dest.parent.mkdir(parents=True, exist_ok=True)
    cursor_dest.write_text(content)
    if sentinel:
        _sentinel_path(cursor_dest).write_text("")
    return cursor_dest


def test_doctor_cursor_shadow_sentineled_offers_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale tool-written cursor projection → finding WITH a removal fix."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_locked_slug_with_matching_slot(tmp_path)
    cursor_dest = _write_cursor_file(tmp_path, _DIVERGED, sentinel=True)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    shadows = _by_type(findings, "cursor-shadow")
    assert len(shadows) == 1, [f.finding_type for f in findings]
    f = shadows[0]
    assert f.slug == "demo-agent"
    assert f.path == cursor_dest
    assert "shadows" in f.detail, f.detail
    assert f.fix_action is not None

    f.fix_action.apply()
    assert not cursor_dest.exists()
    assert not _sentinel_path(cursor_dest).exists()


def test_doctor_cursor_shadow_sentinel_less_report_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sentinel-less divergent cursor file may be user-authored → report-only."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_locked_slug_with_matching_slot(tmp_path)
    cursor_dest = _write_cursor_file(tmp_path, _DIVERGED, sentinel=False)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    shadows = _by_type(findings, "cursor-shadow")
    assert len(shadows) == 1, [f.finding_type for f in findings]
    assert shadows[0].fix_action is None
    assert cursor_dest.exists()


def test_doctor_cursor_shadow_identical_copy_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cursor copy byte-equal to the canonical is a harmless duplicate."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_locked_slug_with_matching_slot(tmp_path)
    _write_cursor_file(tmp_path, _CONTENT, sentinel=True)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert _by_type(findings, "cursor-shadow") == [], (
        [f.finding_type for f in findings]
    )
