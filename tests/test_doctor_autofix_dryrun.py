"""Tests for doctor --fix --dry-run (PR 1: no writes happen)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _make_toolkit_root(tmp_path: Path) -> Path:
    """Seed a minimal valid toolkit root so resolve_toolkit_root accepts it."""
    root = tmp_path / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    schema_dir = root / "schemas"
    schema_dir.mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    )
    (schema_dir / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    return root


def _mutex_violation(toolkit_root: Path) -> None:
    skill_dir = toolkit_root / "skills" / "dup"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: inline.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    (toolkit_root / "skills" / "dup.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )


def test_dry_run_reports_but_writes_nothing(tmp_path: Path) -> None:
    toolkit_root = _make_toolkit_root(tmp_path)
    _mutex_violation(toolkit_root)
    sidecar = toolkit_root / "skills" / "dup.toolkit.yaml"
    body = toolkit_root / "skills" / "dup" / "SKILL.md"
    sidecar_before = sidecar.read_text()
    body_before = body.read_text()

    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "doctor", "--fix", "--dry-run", "--yes"],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    assert "Would " in output or "Refuse" in output  # find_fixables produced findings
    assert "dup" in output
    # Crucially: nothing changed on disk
    assert sidecar.read_text() == sidecar_before
    assert body.read_text() == body_before


def test_apply_fixable_raises_not_implemented_in_pr1() -> None:
    """Belt-and-braces: confirm apply_fixable still raises in PR 1."""
    from agent_toolkit_cli.doctor.autofix import Fixable, apply_fixable
    item = Fixable(kind="skill", slug="x", issue="mutex", action="x", target_path=Path("/tmp/x"))
    try:
        apply_fixable(item)
        assert False, "expected NotImplementedError"
    except NotImplementedError as e:
        assert "PR 3" in str(e)
