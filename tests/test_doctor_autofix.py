"""Tests for doctor --fix write path (PR 3)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_SCHEMA_SRC = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"


def _make_toolkit_root(toolkit_root: Path) -> None:
    """Seed minimal toolkit-root marker + schema so resolve_toolkit_root accepts it."""
    (toolkit_root / ".agent-toolkit-source").touch()
    (toolkit_root / "schemas").mkdir()
    shutil.copyfile(_SCHEMA_SRC, toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json")


def _mutex_first_party(toolkit_root: Path) -> tuple[Path, Path]:
    """First-party mutex: body not in submodule."""
    _make_toolkit_root(toolkit_root)
    skill_dir = toolkit_root / "skills" / "dup"
    skill_dir.mkdir(parents=True)
    body = skill_dir / "SKILL.md"
    body.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: inline.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    sidecar = toolkit_root / "skills" / "dup.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    )
    return sidecar, body


def _mutex_in_submodule(toolkit_root: Path) -> tuple[Path, Path]:
    """Mutex where the inline body is inside a submodule path."""
    _make_toolkit_root(toolkit_root)
    skill_dir = toolkit_root / "skills" / "vendored"
    skill_dir.mkdir(parents=True)
    body = skill_dir / "SKILL.md"
    body.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: vendored\n  description: upstream.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    (toolkit_root / ".gitmodules").write_text(
        '[submodule "skills/vendored"]\n  path = skills/vendored\n  url = x\n'
    )
    sidecar = toolkit_root / "skills" / "vendored.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: vendored\n  description: sidecar.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )
    return sidecar, body


def _run_fix(toolkit_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "doctor", "--fix", "--yes", *extra],
        capture_output=True, text=True,
    )


def test_first_party_mutex_strips_inline_keeps_sidecar(tmp_path: Path) -> None:
    sidecar, body = _mutex_first_party(tmp_path)
    sidecar_before = sidecar.read_text()
    _run_fix(tmp_path)
    # Sidecar unchanged; body's frontmatter stripped
    assert sidecar.read_text() == sidecar_before
    body_after = body.read_text()
    assert not body_after.startswith("---\n")
    assert "body" in body_after


def test_submoduled_body_mutex_refuses(tmp_path: Path) -> None:
    sidecar, body = _mutex_in_submodule(tmp_path)
    body_before = body.read_text()
    result = _run_fix(tmp_path)
    output = result.stdout + result.stderr
    # Body inside submodule must NOT be modified
    assert body.read_text() == body_before
    # User must see clear signal that the fix was refused
    assert "Skipped" in output
    assert "submodule" in output.lower()


def test_dry_run_still_writes_nothing(tmp_path: Path) -> None:
    sidecar, body = _mutex_first_party(tmp_path)
    body_before = body.read_text()
    subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "doctor", "--fix", "--dry-run", "--yes"],
        capture_output=True, text=True,
    )
    assert body.read_text() == body_before
