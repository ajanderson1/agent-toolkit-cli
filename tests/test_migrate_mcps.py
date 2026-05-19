"""Tests for the migrate-mcps-to-sidecar one-shot script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _make_toolkit_root(toolkit_root: Path) -> None:
    """Seed the directory so resolve_toolkit_root accepts it."""
    (toolkit_root / ".agent-toolkit-source").touch()
    (toolkit_root / "schemas").mkdir(exist_ok=True)
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    )
    (toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        schema_src.read_text()
    )


def _make_mcp_with_readme_frontmatter(root: Path, slug: str) -> None:
    mcp_dir = root / "mcps" / slug
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type": "stdio", "command": "npx"}')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n  description: An MCP.\n"
        "  kind: mcp\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n    command: npx\n"
        f"  upstream: https://github.com/example/{slug}\n"
        "---\n\n"
        f"# {slug}\n\nDocumentation prose.\n"
    )


def _run_migrate(toolkit_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "migrate-mcps-to-sidecar", *extra],
        capture_output=True, text=True,
    )


class TestMigrateMcps:
    def test_emits_sidecar_and_strips_readme(self, tmp_path: Path) -> None:
        _make_toolkit_root(tmp_path)
        _make_mcp_with_readme_frontmatter(tmp_path, "context7")
        result = _run_migrate(tmp_path)
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "mcps" / "context7.toolkit.yaml"
        readme = tmp_path / "mcps" / "context7" / "README.md"
        assert sidecar.exists()
        meta = yaml.safe_load(sidecar.read_text())
        assert meta["metadata"]["name"] == "context7"
        assert "transport" in meta["spec"]["mcp"]
        # README should no longer have frontmatter
        readme_text = readme.read_text()
        assert not readme_text.startswith("---\n")
        assert readme_text.startswith("# context7")

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        _make_toolkit_root(tmp_path)
        _make_mcp_with_readme_frontmatter(tmp_path, "context7")
        readme_before = (tmp_path / "mcps" / "context7" / "README.md").read_text()
        result = _run_migrate(tmp_path, "--dry-run")
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "mcps" / "context7.toolkit.yaml"
        readme_after = (tmp_path / "mcps" / "context7" / "README.md").read_text()
        assert not sidecar.exists()
        assert readme_after == readme_before
        assert "Would write" in result.stdout

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running twice should not change anything the second time."""
        _make_toolkit_root(tmp_path)
        _make_mcp_with_readme_frontmatter(tmp_path, "context7")
        _run_migrate(tmp_path)
        readme_text = (tmp_path / "mcps" / "context7" / "README.md").read_text()
        sidecar_text = (tmp_path / "mcps" / "context7.toolkit.yaml").read_text()
        result = _run_migrate(tmp_path)
        assert result.returncode == 0
        assert (tmp_path / "mcps" / "context7" / "README.md").read_text() == readme_text
        assert (tmp_path / "mcps" / "context7.toolkit.yaml").read_text() == sidecar_text
