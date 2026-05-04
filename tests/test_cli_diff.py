"""Pytest port of tests/bats/test_diff.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit.cli import main


def test_diff_shows_would_link(env, seed_skill):
    """Replaces tests/bats/test_diff.bats:40-44."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "would-link" in result.output


def test_diff_previewing_header(env, seed_skill):
    """Replaces tests/bats/test_diff.bats:46-50."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0
    assert "Previewing" in result.stderr


# Issue #9 — diff inherits link's harness validation via ctx.invoke
def test_diff_unknown_harness_exits_2(env):
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(env["toolkit_root"]), "diff", "user", "banana"],
    )
    assert result.exit_code == 2
    assert "unknown harness 'banana'" in result.stderr


def test_diff_mcp_emits_no_op_message(tmp_path, monkeypatch):
    """diff against an allow-list containing an MCP shows the no-op projection message."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha1.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(schema_src.read_text())
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diff", "project", "claude",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    assert "MCP install path for claude not yet implemented" in result.output
