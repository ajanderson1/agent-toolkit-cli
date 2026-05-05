"""TUI integration test for codex hooks: link_plan → list_state shows linked-matches.

Mirrors test_tui_mcp_integration.py for the hook kind. Exercises the full
CLI subprocess + CodexHookAdapter pipeline to verify the TUI's write path
projects a hook asset to ~/.codex/config.toml [hooks] + the managed script
under ~/.codex/agent-toolkit-hooks/<slug>/.
"""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

import pytest


_HOOK_FIXTURE = (
    Path(__file__).resolve().parent / "_fixtures" / "hook_assets" / "codex-demo"
)


@pytest.fixture
def tui_env(tmp_path, monkeypatch):
    if shutil.which("agent-toolkit") is None:
        pytest.skip(
            "agent-toolkit CLI not on PATH; "
            "run `uv pip install -e .` from the project root first"
        )

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = (
        Path(__file__).resolve().parents[1] / "schemas"
        / "asset-frontmatter.v1alpha2.json"
    )
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        src_schema.read_text()
    )
    (toolkit / ".agent-toolkit-source").write_text("")

    # Copy the demo hook asset into the temp toolkit at hooks/codex-demo/.
    hook_dest = toolkit / "hooks" / "codex-demo"
    shutil.copytree(_HOOK_FIXTURE, hook_dest)

    project = tmp_path / "project"
    project.mkdir()
    return {"home": home, "toolkit": toolkit, "project": project}


def test_tui_runner_link_plan_codex_hook(tui_env, monkeypatch):
    """runner.link_plan(harness=codex, hook:codex-demo) writes config.toml + script with +x."""
    from agent_toolkit_tui.runner import CLIRunner

    monkeypatch.chdir(tui_env["project"])
    runner = CLIRunner(tui_env["toolkit"])

    plan = runner.link_plan(
        scope="user", harness="codex", entries=[("hook", "codex-demo")],
    )
    assert plan.failed == 0, plan.errors
    assert plan.ok == 1

    # State shows linked-matches for codex/user/hook.
    state = runner.list_state()
    hooks = [a for a in state["assets"] if a["kind"] == "hook"]
    assert len(hooks) == 1
    user_codex = next(
        c for c in hooks[0]["cells"]
        if c["harness"] == "codex" and c["scope"] == "user"
    )
    assert user_codex["status"] == "linked-matches"

    # Config file present and references the script path.
    config_path = tui_env["home"] / ".codex" / "config.toml"
    assert config_path.is_file()
    config_text = config_path.read_text(encoding="utf-8")
    assert "[[hooks.PreToolUse]]" in config_text
    assert "agent-toolkit-hooks/codex-demo/check.sh" in config_text

    # Deployed script exists with +x.
    script = (
        tui_env["home"] / ".codex" / "agent-toolkit-hooks"
        / "codex-demo" / "check.sh"
    )
    assert script.is_file()
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, f"expected +x on owner, got {oct(mode)}"

    # Unlink round-trip.
    plan2 = runner.unlink_plan(
        scope="user", harness="codex", entries=[("hook", "codex-demo")],
    )
    assert plan2.failed == 0, plan2.errors

    # After unlink, script is gone and config.toml no longer references it.
    assert not script.exists()
    if config_path.is_file():
        post = config_path.read_text(encoding="utf-8")
        assert "agent-toolkit-hooks/codex-demo/check.sh" not in post
