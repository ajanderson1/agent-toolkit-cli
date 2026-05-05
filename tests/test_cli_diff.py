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


def test_diff_mcp_claude_skips_loudly(tmp_path, monkeypatch):
    """diff against an allow-list containing an MCP for claude shows the loud-skip message."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
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
    assert "no MCP adapter for harness claude yet — skipping" in result.output


def test_diff_mcp_codex_shows_would_create(tmp_path, monkeypatch):
    """diff for an allow-listed MCP on codex prints would-create and writes nothing."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / "schemas").mkdir()
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

    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diff", "user", "codex",
         "--toolkit-repo", str(toolkit)],
    )
    assert result.exit_code == 0, result.output
    assert "would-create" in result.output
    target = home / ".codex" / "config.toml"
    assert not target.exists()
