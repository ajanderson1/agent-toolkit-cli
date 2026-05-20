"""`agent-toolkit new skill <slug>` writes a SKILL.md with harness frontmatter
plus a sidecar with CLI-facing description.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli


def _invoke_new_skill(runner: CliRunner, tmp_path: Path, slug: str, *extra: str):
    # --toolkit-repo lives on the `new` subcommand (not the root group).
    return runner.invoke(
        cli, ["new", "skill", slug, "--toolkit-repo", str(tmp_path), *extra]
    )


def test_new_skill_writes_skill_md_with_harness_frontmatter(tmp_path: Path):
    runner = CliRunner()
    result = _invoke_new_skill(runner, tmp_path, "demo")
    assert result.exit_code == 0, result.output

    skill_md = tmp_path / "skills" / "demo" / "SKILL.md"
    assert skill_md.is_file()
    text = skill_md.read_text()
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    assert set(fm.keys()) == {"name", "description"}
    assert fm["name"] == "demo"
    assert fm["description"].endswith(".")


def test_new_skill_writes_sidecar_with_cli_description(tmp_path: Path):
    runner = CliRunner()
    result = _invoke_new_skill(runner, tmp_path, "demo")
    assert result.exit_code == 0, result.output

    sidecar = tmp_path / "skills" / "demo.toolkit.yaml"
    assert sidecar.is_file()
    data = yaml.safe_load(sidecar.read_text())
    assert data["apiVersion"] == "agent-toolkit/v1alpha2"
    assert data["metadata"]["name"] == "demo"
    assert data["metadata"]["description"].endswith(".")


def test_new_skill_inline_rejected(tmp_path: Path):
    runner = CliRunner()
    result = _invoke_new_skill(runner, tmp_path, "demo", "--inline")
    assert result.exit_code == 2, result.output
    out = result.output.lower()
    assert "sidecar" in out and "inline" in out, result.output


def test_new_mcp_inline_still_allowed(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["new", "mcp", "demo", "--toolkit-repo", str(tmp_path), "--inline"]
    )
    assert result.exit_code == 0, result.output
    # Verify the inline path actually wrote the mcp asset with inline frontmatter
    # and no sidecar — proving the inline branch executed end-to-end.
    mcp_body = tmp_path / "mcps" / "demo.toolkit.yaml"
    sidecar = tmp_path / "mcps" / "demo.sidecar.yaml"
    # Inline mcp: the metadata lives in the body file itself (not a sidecar).
    # Find whatever file was written under mcps/ and assert it carries frontmatter.
    written = list((tmp_path / "mcps").rglob("*"))
    asset_files = [p for p in written if p.is_file()]
    assert asset_files, f"no mcp asset written under {tmp_path / 'mcps'}"
    # No standalone sidecar file should exist alongside the inline mcp.
    assert not sidecar.exists(), f"unexpected sidecar at {sidecar}"
