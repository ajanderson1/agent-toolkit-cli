"""Pytest port of tests/bats/test_diff.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit.cli import main


SKILL_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""


def _seed_toolkit(tmp: Path) -> Path:
    """Create a minimal valid toolkit repo at `tmp/toolkit`."""
    root = tmp / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha1.json"
    )
    (root / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(schema_src.read_text())
    return root


def _seed_skill(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = _seed_toolkit(tmp_path)
    return {"home": home, "toolkit_root": toolkit_root}


def test_diff_shows_would_link(env):
    """Replaces tests/bats/test_diff.bats:40-44."""
    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "would-link" in result.output


def test_diff_previewing_header(env):
    """Replaces tests/bats/test_diff.bats:46-50."""
    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0
    assert "Previewing" in result.stderr
