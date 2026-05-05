"""TUI integration test: link_plan → list_state shows linked-matches.

Exercises the full CLI subprocess + adapter pipeline to verify the TUI's
write path doesn't bypass the adapter (AC #10 of the MCP adapters spec).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


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
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    return {"home": home, "toolkit": toolkit, "project": project}


def test_tui_runner_link_plan_then_list_state_codex(tui_env, monkeypatch):
    """runner.link_plan → list_state shows linked-matches; unlink_plan reverses."""
    from agent_toolkit_tui.runner import CLIRunner

    monkeypatch.chdir(tui_env["project"])
    runner = CLIRunner(tui_env["toolkit"])

    # Allow-list and link via plan.
    plan = runner.link_plan(
        scope="user", harness="codex", entries=[("mcp", "context7")],
    )
    assert plan.failed == 0, plan.errors
    assert plan.ok == 1

    # Re-read state; codex/user cell for context7 is linked-matches.
    state = runner.list_state()
    mcps = [a for a in state["assets"] if a["kind"] == "mcp"]
    assert len(mcps) == 1
    user_codex = next(c for c in mcps[0]["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "linked-matches"

    # Unlink round-trip.
    plan2 = runner.unlink_plan(
        scope="user", harness="codex", entries=[("mcp", "context7")],
    )
    assert plan2.failed == 0, plan2.errors

    state2 = runner.list_state()
    mcps2 = [a for a in state2["assets"] if a["kind"] == "mcp"]
    user_codex2 = next(c for c in mcps2[0]["cells"]
                       if c["harness"] == "codex" and c["scope"] == "user")
    # After unlink: not allow-listed, not installed → either unsupported or
    # unlinked-allowlisted is acceptable. The plan removes context7 from the
    # YAML entirely, so it's not allowlisted any more.
    assert user_codex2["status"] in {"unsupported", "unlinked-allowlisted"}


def test_tui_package_does_not_import_adapters():
    """TUI must not import any harness_adapter module directly (AC #10)."""
    import importlib
    import pkgutil
    from pathlib import Path

    import agent_toolkit_tui

    forbidden = "agent_toolkit.harness_adapters"
    tui_path = Path(agent_toolkit_tui.__file__).parent

    for _finder, name, _ispkg in pkgutil.walk_packages(
        path=[str(tui_path)],
        prefix="agent_toolkit_tui.",
    ):
        mod = importlib.import_module(name)
        if mod.__file__ is None:
            continue
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert forbidden not in src, (
            f"{name} imports {forbidden} — TUI must go through CLIRunner only "
            "(per AC #10 of the MCP adapters spec)."
        )
