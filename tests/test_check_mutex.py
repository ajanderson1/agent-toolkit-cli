"""Tests for the mutex-violation check (sidecar + inline both present)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _seed_toolkit_root(toolkit_root: Path) -> None:
    """Add the marker and schema files required by repo resolution."""
    (toolkit_root / ".agent-toolkit-source").touch()
    (toolkit_root / "schemas").mkdir(parents=True, exist_ok=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        src_schema.read_text()
    )


def _setup_mutex_violation(toolkit_root: Path) -> None:
    """Create skills/foo/ with BOTH inline frontmatter AND a sidecar."""
    _seed_toolkit_root(toolkit_root)
    skill_dir = toolkit_root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: inline.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    sidecar = toolkit_root / "skills" / "foo.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )


def test_check_fails_on_mutex_violation(tmp_path: Path) -> None:
    _setup_mutex_violation(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "check", "--exit-code"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2, f"expected exit 2, got {result.returncode}; output:\n{output}"
    assert "MutexViolation" in output
    assert "skills/foo" in output
    assert "foo.toolkit.yaml" in output
    assert "SKILL.md" in output
    # Fix 2: also assert the fix hint is present in the message
    assert "doctor --fix" in output


def test_check_passes_when_only_sidecar(tmp_path: Path) -> None:
    """Negative case: sidecar-only is fine, no mutex."""
    _seed_toolkit_root(tmp_path)
    skill_dir = tmp_path / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("body without frontmatter\n")
    sidecar = tmp_path / "skills" / "foo.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "check", "--exit-code"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    # Should NOT fail with MutexViolation (other check warnings may exist, that's fine)
    assert "MutexViolation" not in output
