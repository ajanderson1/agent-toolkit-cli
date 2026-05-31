"""Round-trip + idempotency + foreign-file-guard tests for agent_install.

Two regressions are guarded here:

1. PR #268 (orphaned projections): agent_install.uninstall() relied on the
   skill-centric scan which always returned () for the agent kind, so projected
   real files were ORPHANED. Fixed by removing each requested harness's real
   file via its own adapter. The "projection GONE after uninstall" assertions
   below guard this.

2. #303 (destructive uninstall): uninstall() ALSO deleted the library canonical
   and dropped the lock entry — `remove` behaviour under the `uninstall` name,
   inverting its own CLI contract. `agent uninstall` must be NON-DESTRUCTIVE:
   projections gone, but canonical + lock entry KEPT (mirrors `skill uninstall`;
   the destructive path lives in `agent_install.remove()`). The "canonical
   PRESENT / lock PRESENT after uninstall" assertions below guard this.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Unset dev-shell env so expected destination paths are deterministic."""
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


_CONTENT = "---\nname: rt-agent\ndescription: round-trip\n---\n\nBody.\n"


def _seed_global_canonical(slug="rt-agent"):
    """Create the global canonical with a content file (under tmp HOME)."""
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir(slug, scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(_CONTENT)
    return canonical


def _seed_project_canonical(project, slug="rt-agent"):
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir(slug, scope="project", project=project)
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(_CONTENT)
    return canonical


# ── Test 1a: round-trip install → uninstall removes the real projected files ─

def test_roundtrip_global_removes_projected_files(tmp_path, monkeypatch):
    """Install ≥2 harnesses globally, then uninstall.

    Guards both regressions:
    - PR #268: the real projected files (claude-code .md, gemini-cli .md) are
      deleted, not orphaned.
    - #303: uninstall is NON-DESTRUCTIVE — the library canonical and the lock
      entry are KEPT (only `agent remove` deletes those).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply, uninstall
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.skill_source import ParsedSource

    canonical = _seed_global_canonical()
    # A lock entry is required for uninstall to know what to remove + to mark
    # the install as tool-owned. Use a non-git source so apply() writes a lock
    # entry without cloning.
    src = ParsedSource(
        type="github", url="https://github.com/x/rt-agent", owner_repo="x/rt-agent",
        ref=None, subpath=None,
    )
    apply(
        InstallPlan(
            slug="rt-agent", scope="global", source=src, ref=None,
            add_agents=("claude-code", "gemini-cli"), remove_agents=(),
        ),
        home=tmp_path,
    )

    cc = tmp_path / ".claude" / "agents" / "rt-agent.md"
    gem = tmp_path / ".gemini" / "agents" / "rt-agent.md"
    assert cc.exists(), "claude-code projection not created"
    assert gem.exists(), "gemini-cli projection not created"

    lock_path = lock_file_path(scope="global")
    assert "rt-agent" in read_lock(lock_path).skills

    uninstall(
        slug="rt-agent", scope="global", home=tmp_path, project=None,
        harnesses=("claude-code", "gemini-cli"),
    )

    assert not cc.exists(), "claude-code projection ORPHANED after uninstall"
    assert not gem.exists(), "gemini-cli projection ORPHANED after uninstall"
    assert canonical.exists(), "uninstall must KEEP the library canonical (#303)"
    assert "rt-agent" in read_lock(lock_path).skills, (
        "uninstall must KEEP the lock entry (#303)"
    )


# ── Test 1b: same round-trip at PROJECT scope ────────────────────────────────

def test_roundtrip_project_removes_projected_files(tmp_path, monkeypatch):
    """Project-scope round-trip: projected files gone, canonical + lock KEPT (#303)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply, uninstall
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.skill_source import ParsedSource

    canonical = _seed_project_canonical(project)
    src = ParsedSource(
        type="github", url="https://github.com/x/rt-agent", owner_repo="x/rt-agent",
        ref=None, subpath=None,
    )
    apply(
        InstallPlan(
            slug="rt-agent", scope="project", source=src, ref=None,
            add_agents=("claude-code", "gemini-cli"), remove_agents=(),
        ),
        project=project,
    )

    cc = project / ".claude" / "agents" / "rt-agent.md"
    gem = project / ".gemini" / "agents" / "rt-agent.md"
    assert cc.exists() and gem.exists()

    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" in read_lock(lock_path).skills

    uninstall(
        slug="rt-agent", scope="project", home=None, project=project,
        harnesses=("claude-code", "gemini-cli"),
    )

    assert not cc.exists(), "claude-code projection ORPHANED (project scope)"
    assert not gem.exists(), "gemini-cli projection ORPHANED (project scope)"
    assert canonical.exists(), "project uninstall must KEEP the canonical (#303)"
    assert "rt-agent" in read_lock(lock_path).skills, (
        "project uninstall must KEEP the lock entry (#303)"
    )


# ── Test 2: idempotency — second install of same targets does not error ──────

def test_double_install_is_safe_and_idempotent(tmp_path, monkeypatch):
    """Installing the same targets twice must not raise and must not duplicate.

    With Option A the facade marks a re-install of a tool-owned slug as
    allowed (overwrite). The destinations must still hold exactly the agent
    we wrote, with no error from re-clobbering our own files.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.skill_source import ParsedSource

    _seed_global_canonical()
    src = ParsedSource(
        type="github", url="https://github.com/x/rt-agent", owner_repo="x/rt-agent",
        ref=None, subpath=None,
    )

    def _do_install():
        return apply(
            InstallPlan(
                slug="rt-agent", scope="global", source=src, ref=None,
                add_agents=("claude-code", "gemini-cli"), remove_agents=(),
            ),
            home=tmp_path,
        )

    first = _do_install()
    assert len(first.created) == 2
    # Second install of our own tool-owned files must be allowed (no raise).
    second = _do_install()
    assert len(second.created) == 2
    cc = tmp_path / ".claude" / "agents" / "rt-agent.md"
    assert cc.exists()


def test_plan_after_install_yields_no_spurious_readd(tmp_path, monkeypatch):
    """plan() recomputed after install must not re-add already-installed agents.

    Proves the delta-computation half of the bug is fixed: with an
    agent-aware "currently linked" scanner, the previously-installed harnesses
    are recognised so target==current produces an empty add set.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply, plan
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.skill_source import ParsedSource

    _seed_global_canonical()
    src = ParsedSource(
        type="github", url="https://github.com/x/rt-agent", owner_repo="x/rt-agent",
        ref=None, subpath=None,
    )
    apply(
        InstallPlan(
            slug="rt-agent", scope="global", source=None, ref=None,
            add_agents=("claude-code", "gemini-cli"), remove_agents=(),
        ),
        home=tmp_path,
    )

    p = plan(
        slug="rt-agent", scope="global", source=src, ref=None,
        target_agents=("claude-code", "gemini-cli"), home=tmp_path,
    )
    assert p.add_agents == (), f"spurious re-add: {p.add_agents}"
    assert p.remove_agents == (), f"spurious remove: {p.remove_agents}"


# ── Test 3: foreign-file guard — refuses to clobber a user-authored file ─────

def test_install_refuses_foreign_file(tmp_path, monkeypatch):
    """A same-slug user-authored file at a destination is NOT clobbered.

    apply() must raise a clear error (an InstallError subclass), not a bare
    traceback, and the user's file content must remain intact.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli._install_core import InstallPlan

    _seed_global_canonical()

    # Pre-create a user-authored claude-code agent file with the same slug.
    foreign = tmp_path / ".claude" / "agents" / "rt-agent.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("USER AUTHORED — DO NOT CLOBBER\n")

    with pytest.raises(InstallError):
        apply(
            InstallPlan(
                slug="rt-agent", scope="global", source=None, ref=None,
                add_agents=("claude-code",), remove_agents=(),
            ),
            home=tmp_path,
        )

    assert foreign.read_text() == "USER AUTHORED — DO NOT CLOBBER\n", (
        "user-authored file was clobbered by install"
    )


# ── Test 4: tool-owned refresh — re-installing our own file is allowed ───────

def test_install_refresh_tool_owned_file_allowed(tmp_path, monkeypatch):
    """Re-installing a file WE previously wrote (lock entry present) succeeds.

    Distinguishes 'foreign file we'd clobber' (refuse) from 'our own file we're
    refreshing' (allow) — the second install updates content without raising.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.skill_source import ParsedSource

    canonical = _seed_global_canonical()
    src = ParsedSource(
        type="github", url="https://github.com/x/rt-agent", owner_repo="x/rt-agent",
        ref=None, subpath=None,
    )
    apply(
        InstallPlan(
            slug="rt-agent", scope="global", source=src, ref=None,
            add_agents=("claude-code",), remove_agents=(),
        ),
        home=tmp_path,
    )
    dest = tmp_path / ".claude" / "agents" / "rt-agent.md"
    assert dest.exists()

    # Change the canonical content, then re-install: our own file refreshes.
    (canonical / "rt-agent.md").write_text(
        "---\nname: rt-agent\ndescription: refreshed\n---\n\nNew body.\n"
    )
    result = apply(
        InstallPlan(
            slug="rt-agent", scope="global", source=src, ref=None,
            add_agents=("claude-code",), remove_agents=(),
        ),
        home=tmp_path,
    )
    assert dest in result.created
    assert "New body." in dest.read_text(), "refresh did not update our own file"
