"""agent_install.py — facade binding AGENT_BINDING + dispatching adapters."""
from __future__ import annotations

import pytest


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
    assert _AGENT_SYNTHETIC_NAMES == frozenset({"general-agent"})


def test_plan_shim_passes_no_universal_bundle_link(tmp_path, monkeypatch):
    """Agents have no universal-bundle concept; the facade injects None."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import plan
    p = plan(slug="test", scope="global", target_agents=())
    assert p.slug == "test"
    assert p.scope == "global"
    assert p.add_agents == ()
    assert p.remove_agents == ()


@pytest.mark.xfail(
    strict=False,
    reason="requires subagent_mechanism literals set in Task 11",
)
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
    result = apply(plan_obj)
    expected = tmp_path / ".claude" / "agents" / "test-agent.md"
    assert expected in result.created
    assert expected.exists()


@pytest.mark.xfail(
    strict=False,
    reason="requires subagent_mechanism literals set in Task 11",
)
def test_apply_skips_unsupported_harness(tmp_path, monkeypatch):
    """A harness with subagent_mechanism='none' is recorded as skipped."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir("test-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "test-agent.md").write_text("---\nname: test-agent\n---\nbody\n")

    plan_obj = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("amp",),  # amp has subagent_mechanism="none"
        remove_agents=(),
    )
    result = apply(plan_obj)
    assert "amp" in result.skipped


@pytest.mark.xfail(
    strict=False,
    reason="requires real adapter behaviour from Tasks 8-11",
)
def test_uninstall_is_idempotent(tmp_path, monkeypatch):
    """uninstall() called twice with same slug doesn't error."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import uninstall

    uninstall(
        slug="nonexistent-slug", scope="global",
        home=None, project=None, harnesses=("claude-code",),
    )
    uninstall(
        slug="nonexistent-slug", scope="global",
        home=None, project=None, harnesses=("claude-code",),
    )
