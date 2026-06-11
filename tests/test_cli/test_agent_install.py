"""agent_install.py — facade binding AGENT_BINDING + dispatching adapters."""
from __future__ import annotations



def test_agent_install_public_surface():
    from agent_toolkit_cli import agent_install
    public = {name for name in dir(agent_install) if not name.startswith("_")}
    expected = {
        "InstallError", "LockMismatchError", "DirtyCanonicalError",
        "InstallPlan", "InstallResult", "plan", "apply",
        "install", "uninstall",
    }
    for sym in expected:
        assert sym in public, f"agent_install missing public symbol: {sym}"


def test_agent_install_synthetic_names_constant():
    """The agent facade injects its own synthetic set into the core."""
    from agent_toolkit_cli.agent_install import _AGENT_SYNTHETIC_NAMES
    assert _AGENT_SYNTHETIC_NAMES == frozenset({"standard-agent"})


def test_plan_shim_passes_no_standard_bundle_link(tmp_path, monkeypatch):
    """Agents have no universal-bundle concept; the facade injects None."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import plan
    p = plan(slug="test", scope="global", target_agents=())
    assert p.slug == "test"
    assert p.scope == "global"
    assert p.add_agents == ()
    assert p.remove_agents == ()


def test_apply_dispatches_to_adapter_for_supported_harness(tmp_path, monkeypatch):
    """apply() invokes the symlink adapter for claude-code and writes the file.

    Will pass after Task 11 sets claude-code's mechanism to 'symlink'.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir("test-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "test-agent.md").write_text("---\nname: test-agent\n---\nbody\n")

    plan_obj = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("claude-code",), remove_agents=(),
    )
    result = apply(plan_obj, home=tmp_path)
    expected = tmp_path / ".claude" / "agents" / "test-agent.md"
    assert expected in result.created
    assert expected.exists()


def test_apply_skips_unsupported_harness(tmp_path, monkeypatch):
    """A harness with subagent_mechanism='none' is recorded as skipped.

    Already works today because Task 5 set every cell's default to 'none';
    the test is the real assertion (no xfail) so a future regression where
    the skip branch stops firing fails loudly.
    """
    from agent_toolkit_cli.skill_agents import AGENTS
    assert AGENTS["amp"].subagent_mechanism == "none", (
        "amp must remain mechanism='none' for this test to be meaningful — "
        "swap to another by-design cell if amp gets re-classified."
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir("test-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "test-agent.md").write_text("---\nname: test-agent\n---\nbody\n")

    plan_obj = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("amp",),
        remove_agents=(),
    )
    result = apply(plan_obj)
    assert "amp" in result.skipped


def test_uninstall_nonexistent_slug_is_safe(tmp_path, monkeypatch):
    """uninstall() against a slug that never existed is a no-op, not an error.

    Stronger than 'idempotent' — exercises the structural early-return
    paths in uninstall(). The plan called this 'idempotent' but until
    Tasks 8-11 wire real adapters the second-call symmetry isn't meaningful;
    this test asserts what's actually true today (and remains true after).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import uninstall

    uninstall(
        slug="nonexistent-slug", scope="global",
        home=None, project=None, harnesses=("claude-code",),
    )
    # Second call must also be safe (true 'idempotent' once adapters land).
    uninstall(
        slug="nonexistent-slug", scope="global",
        home=None, project=None, harnesses=("claude-code",),
    )


# --- #361: standard slot ---------------------------------------------------


def test_get_adapter_standard_returns_adapter():
    from agent_toolkit_cli.agent_adapters import get_adapter
    a = get_adapter("standard")
    assert a.harness == "standard"


def test_linked_scan_reports_standard_once(tmp_path, monkeypatch):
    """The .claude/agents slot is reported as `standard` only — harnesses
    whose destination is the SAME file (claude-code globally; also kode
    project-side) are deduped, or plan() would compute a remove for
    claude-code that deletes the shared file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import _current_linked_agents
    linked = _current_linked_agents(
        slug="demo", scope="global", home=tmp_path, project=None,
    )
    assert "standard" in linked
    assert "claude-code" not in linked


def test_plan_standard_to_standard_is_noop(tmp_path, monkeypatch):
    """Re-installing standard over an existing slot computes an empty delta."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import plan
    p = plan(slug="demo", scope="global", target_agents=("standard",),
             home=tmp_path)
    assert "standard" not in p.add_agents
    assert "claude-code" not in p.remove_agents


def test_plan_normalizes_covered_target_tokens(tmp_path, monkeypatch):
    """plan(target=('claude-code',)) over an existing slot must compute an
    EMPTY delta, not add=claude-code + remove=standard — applying that delta
    would install then immediately delete the SAME shared file. Target tokens
    whose destination IS the slot are normalized to 'standard' before the
    delta is computed (#361)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import plan
    p = plan(slug="demo", scope="global", target_agents=("claude-code",),
             home=tmp_path)
    assert p.add_agents == ()
    assert p.remove_agents == ()


def test_linked_scan_dedupe_kode_project_scope(tmp_path):
    """kode's PROJECT cell IS {PROJECT}/.claude/agents/<slug>.md — the same
    file as the standard slot. Without project-scope dedupe the scan would
    double-report and a delta could delete the shared file (review finding)."""
    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    from agent_toolkit_cli.agent_install import _current_linked_agents
    linked = _current_linked_agents(
        slug="demo", scope="project", home=None, project=tmp_path,
    )
    assert "standard" in linked
    assert "kode" not in linked


def test_uninstall_covered_token_routes_to_standard_adapter(tmp_path, monkeypatch):
    """Destination-based normalization in the facade (review finding): the
    production deletion path is agent_install.uninstall()'s DIRECT adapter
    loop, not plan(). A covered token whose destination IS the slot (kode at
    project scope) must route to the standard adapter so the .attk sentinel
    is cleaned up with the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std
    from agent_toolkit_cli.agent_install import uninstall

    project = tmp_path / "proj"
    project.mkdir()
    canonical = tmp_path / "c"
    canonical.mkdir()
    content = canonical / "demo.md"
    content.write_text("x\n")
    std = _std()
    out = std.install("demo", content, scope="project", project=project)
    assert _sentinel_path(out).exists()
    uninstall(slug="demo", scope="project", home=None, project=project,
              harnesses=("kode",))
    assert not out.exists()
    assert not _sentinel_path(out).exists()


def test_uninstall_processes_standard_slot_once(tmp_path, monkeypatch):
    """harnesses=('standard', 'claude-code') normalize to the SAME token —
    the standard adapter's uninstall must run exactly once (seen-set), not
    once per alias of the slot."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.agent_adapters import standard as standard_mod
    from agent_toolkit_cli.agent_install import uninstall

    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")
    _sentinel_path(slot).write_text("")

    calls: list[str] = []
    orig = standard_mod._StandardAdapter.uninstall

    def counting(self, slug, **kwargs):
        calls.append(slug)
        return orig(self, slug, **kwargs)

    monkeypatch.setattr(standard_mod._StandardAdapter, "uninstall", counting)
    uninstall(slug="demo", scope="global", home=tmp_path, project=None,
              harnesses=("standard", "claude-code"))
    assert calls == ["demo"], f"standard uninstall ran {len(calls)}x, want 1"
    assert not slot.exists()
    assert not _sentinel_path(slot).exists()


def test_uninstall_preexisting_slot_content_match_detaches(tmp_path, monkeypatch):
    """Pre-#361 migration path through the FACADE: a sentinel-less slot file
    (e.g. written by an old `--harnesses claude-code` install) that byte-
    matches the scope canonical is recognised as tool-owned — the facade
    builds canonical_content from canonical_agent_dir and threads it to the
    standard adapter, which authorizes the detach by content equality."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.agent_install import uninstall
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir("demo", scope="global")
    canonical.mkdir(parents=True)
    (canonical / "demo.md").write_text("x\n")

    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("x\n")  # byte-equal to the canonical, NO sentinel
    assert not _sentinel_path(slot).exists()

    uninstall(slug="demo", scope="global", home=tmp_path, project=None,
              harnesses=("claude-code",))
    assert not slot.exists(), (
        "content-matched sentinel-less slot must detach via canonical_content"
    )


def test_uninstall_preexisting_slot_divergent_content_survives(tmp_path, monkeypatch):
    """Safety sibling: a sentinel-less slot whose content DIVERGES from the
    scope canonical is a user's hand-authored agent — the facade-threaded
    canonical_content must NOT authorize its removal."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import uninstall
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir("demo", scope="global")
    canonical.mkdir(parents=True)
    (canonical / "demo.md").write_text("x\n")

    slot = tmp_path / ".claude" / "agents" / "demo.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("USER AUTHORED — divergent\n")  # no sentinel either

    uninstall(slug="demo", scope="global", home=tmp_path, project=None,
              harnesses=("claude-code",))
    assert slot.exists(), "divergent sentinel-less slot must be left in place"
    assert slot.read_text() == "USER AUTHORED — divergent\n"


def test_install_kode_project_scope_routes_to_standard_adapter(tmp_path, monkeypatch):
    """PM review (MAJOR 3): kode's project cell IS the slot — installing it
    must go through the standard adapter (sentinel written, adopt logic)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    from agent_toolkit_cli import agent_install

    project = tmp_path / "proj"
    project.mkdir()
    canonical = canonical_agent_dir("demo", scope="project", project=project)
    canonical.mkdir(parents=True)
    (canonical / "demo.md").write_text("x\n")
    # #362: a project-scope source=None install now derives its project lock
    # entry from the global entry — seed one (the pre-fix setup relied on the
    # silently-broken no-lock-write path).
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import library_lock_path
    write_lock(library_lock_path(), add_entry(
        read_lock(library_lock_path()), "demo",
        LockEntry(source="x/demo", source_type="github", agent_path="demo.md"),
    ))
    p = InstallPlan(slug="demo", scope="project", source=None, ref=None,
                    add_agents=("kode",), remove_agents=())
    agent_install.apply(p, project=project)
    slot = project / ".claude" / "agents" / "demo.md"
    assert slot.exists()
    assert _sentinel_path(slot).exists()


def test_uninstall_collects_refusals_from_symlink_adapters(tmp_path, monkeypatch):
    """#368: facade uninstall() returns refusals from EVERY adapter, not just
    standard — a hand-authored file at a symlink-cell destination is left in
    place and reported."""
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli.agent_adapters import symlink
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    # A foreign file at cursor's GLOBAL destination (never installed by us).
    dest = symlink.adapter_for("cursor").destination(
        "test-agent", scope="global", home=home,
    )
    dest.parent.mkdir(parents=True)
    dest.write_text("# hand-authored\n")
    refusals = agent_install.uninstall(
        slug="test-agent", scope="global", home=home, project=None,
        harnesses=("cursor",),
    )
    assert refusals == (("cursor", dest),)
    assert dest.exists()
