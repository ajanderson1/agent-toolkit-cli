"""Round-trip + idempotency + foreign-file-guard tests for agent_install.

Two regressions are guarded here:

1. PR #268 (orphaned projections): agent_install.uninstall() relied on the
   skill-centric scan which always returned () for the agent asset type, so projected
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


# ── Test 1c: remove() at PROJECT scope — drops lock, KEEPS external canonical ─

def test_remove_project_scope_preserves_external_canonical(tmp_path, monkeypatch):
    """`remove(scope="project")` drops the project lock entry but PRESERVES the
    external canonical (dirty-work survival; doctor's orphan sweep reclaims it).

    Distinct from global `remove()` (which rmtrees the canonical) and from
    project `uninstall()` (which keeps the lock). Guards the project branch of
    the contract split that has no CLI surface yet (agent remove is global-only).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply, remove
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
            add_agents=("claude-code",), remove_agents=(),
        ),
        project=project,
    )
    cc = project / ".claude" / "agents" / "rt-agent.md"
    lock_path = lock_file_path(scope="project", project=project)
    assert cc.exists()
    assert "rt-agent" in read_lock(lock_path).skills

    remove(
        slug="rt-agent", scope="project", home=None, project=project,
        harnesses=("claude-code",),
    )

    assert not cc.exists(), "project remove must remove the projection"
    assert canonical.exists(), (
        "project-scope remove must PRESERVE the external canonical "
        "(matches skill remove; doctor reclaims orphans)"
    )
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "project remove must drop the project lock entry"
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


# ── #362: project installs (source=None, the real CLI/TUI shape) must write
#    a derived project lock entry ─────────────────────────────────────────────

def _write_global_lock_entry(slug="rt-agent", ref=None):
    """Write a global library lock entry (honours monkeypatched HOME)."""
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import library_lock_path

    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=f"x/{slug}", source_type="github", ref=ref,
        agent_path=f"{slug}.md",
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def _source_none_plan(slug="rt-agent", add=("claude-code", "gemini-cli")):
    from agent_toolkit_cli._install_core import InstallPlan

    return InstallPlan(
        slug=slug, scope="project", source=None, ref=None,
        add_agents=tuple(add), remove_agents=(),
    )


def test_project_install_source_none_writes_derived_lock_entry(
    tmp_path, monkeypatch,
):
    """#362 core: apply(source=None, project scope) derives the project lock
    entry from the global entry; full lifecycle: install → entry present →
    uninstall keeps it (#303) → remove drops it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply, remove, uninstall
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()
    _write_global_lock_entry(ref="main")
    _seed_project_canonical(project)

    result = apply(_source_none_plan(), project=project)

    lock_path = lock_file_path(scope="project", project=project)
    entry = read_lock(lock_path).skills.get("rt-agent")
    assert entry is not None, "#362: project install wrote NO project lock entry"
    assert entry.source == "x/rt-agent"
    assert entry.source_type == "github"
    assert entry.ref == "main"
    assert entry.agent_path == "rt-agent.md"
    assert entry.upstream_sha is None and entry.local_sha is None, (
        "project entries don't pin SHAs (skills precedent)"
    )
    assert result.lock_action == "added"

    uninstall(
        slug="rt-agent", scope="project", home=None, project=project,
        harnesses=("claude-code", "gemini-cli"),
    )
    assert "rt-agent" in read_lock(lock_path).skills, (
        "uninstall must KEEP the lock entry (#303)"
    )

    remove(
        slug="rt-agent", scope="project", home=None, project=project,
        harnesses=("claude-code", "gemini-cli"),
    )
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "remove must DROP the lock entry"
    )


def test_project_install_no_global_entry_fails_before_projection(
    tmp_path, monkeypatch,
):
    """No global lock entry → InstallError BEFORE any file is projected."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    import pytest as _pytest

    from agent_toolkit_cli.agent_install import InstallError, apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()  # canonical only — NO global lock entry
    _seed_project_canonical(project)

    with _pytest.raises(InstallError, match="no global lock entry"):
        apply(_source_none_plan(), project=project)

    assert not (project / ".claude" / "agents" / "rt-agent.md").exists(), (
        "fail-loud must come BEFORE projection (no orphaned files)"
    )
    assert not (project / ".gemini" / "agents" / "rt-agent.md").exists()
    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" not in read_lock(lock_path).skills


def test_project_reinstall_source_none_is_idempotent(tmp_path, monkeypatch):
    """Second apply() succeeds: the entry written by the first run makes the
    slug tool-owned (overwrite=True), fixing the F3 re-install conflict."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply

    _seed_global_canonical()
    _write_global_lock_entry()
    _seed_project_canonical(project)

    r1 = apply(_source_none_plan(), project=project)
    assert r1.lock_action == "added"
    r2 = apply(_source_none_plan(), project=project)  # must not raise
    assert r2.lock_action == "unchanged"
    assert (project / ".gemini" / "agents" / "rt-agent.md").exists()


def test_project_first_install_still_refuses_foreign_file(
    tmp_path, monkeypatch,
):
    """Foreign pre-existing destination still refused on FIRST install
    (overwrite must stay False until the entry exists) — and the failed
    install writes NO lock entry."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    import pytest as _pytest

    from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()
    _write_global_lock_entry()
    _seed_project_canonical(project)
    foreign = project / ".gemini" / "agents" / "rt-agent.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("# user's own file\n")

    with _pytest.raises(AgentProjectionConflictError):
        apply(_source_none_plan(add=("gemini-cli",)), project=project)

    assert foreign.read_text() == "# user's own file\n", "foreign file clobbered"
    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "a FAILED install must not write a lock entry"
    )


def test_project_unlisted_entry_operable_without_global_entry(
    tmp_path, monkeypatch,
):
    """#360 'unlisted' contract: slug already in the PROJECT lock installs
    fine with NO global lock entry (the new fail-loud must be exempt), and a
    pure-remove plan never consults the global lock."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()  # NO global lock entry
    _seed_project_canonical(project)
    # Pre-existing project lock entry (the #360 unlisted shape).
    lock_path = lock_file_path(scope="project", project=project)
    write_lock(lock_path, add_entry(
        read_lock(lock_path), "rt-agent",
        LockEntry(source="x/rt-agent", source_type="github",
                  agent_path="rt-agent.md"),
    ))

    apply(_source_none_plan(add=("gemini-cli",)), project=project)  # no raise
    assert (project / ".gemini" / "agents" / "rt-agent.md").exists()

    # Pure-remove plan with NO lock entries anywhere: must not raise either.
    pure_remove = InstallPlan(
        slug="other-agent", scope="project", source=None, ref=None,
        add_agents=(), remove_agents=("gemini-cli",),
    )
    apply(pure_remove, project=project)


def test_project_install_all_skipped_writes_no_lock_entry(tmp_path, monkeypatch):
    """Critical-review G4: an install whose requested harnesses are ALL
    skipped as unsupported projects nothing — it must NOT write a project
    lock entry, or the zero-projection install claims tool ownership and
    flips overwrite=True for a later first REAL projection (guard bypass)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()
    _write_global_lock_entry()
    _seed_project_canonical(project)

    # codex is a real catalog entry with subagent_mechanism='none' → skipped.
    result = apply(_source_none_plan(add=("codex",)), project=project)

    assert result.skipped == ("codex",)
    assert result.lock_action == "unchanged"
    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "G4: zero-projection install must not claim ownership"
    )


def test_global_install_source_none_writes_no_global_entry(
    tmp_path, monkeypatch,
):
    """AC9: global installs never write lock entries (that is `agent add`'s
    job) — behaviour unchanged for canonical-only global slugs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path

    _seed_global_canonical()  # canonical only — NO lock entry

    result = apply(
        InstallPlan(
            slug="rt-agent", scope="global", source=None, ref=None,
            add_agents=("gemini-cli",), remove_agents=(),
        ),
        home=tmp_path,
    )
    assert result.lock_action == "unchanged"
    assert "rt-agent" not in read_lock(library_lock_path()).skills
