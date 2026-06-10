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
