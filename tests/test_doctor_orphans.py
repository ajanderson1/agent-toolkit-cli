"""Tests for the doctor 'orphans' group — orphan body directories."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.orphans import diagnose_orphans
from agent_toolkit_cli.doctor.result import Status


def _make_orphan_body(root: Path, slug: str) -> None:
    """skills/<slug>/SKILL.md exists, but no inline FM and no sidecar."""
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Orphan\n\nNo metadata anywhere.\n")


def test_orphan_body_is_advisory(tmp_path: Path) -> None:
    _make_orphan_body(tmp_path, "lonely")
    result = diagnose_orphans(tmp_path)
    assert result.status == Status.ADVISORY
    assert any("lonely" in finding for finding in result.findings)


def test_no_orphans_passes(tmp_path: Path) -> None:
    # skills/foo/ with inline frontmatter — not an orphan
    skill_dir = tmp_path / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: x.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    result = diagnose_orphans(tmp_path)
    assert result.status == Status.OK
    assert result.findings == []


def test_pycache_directory_not_reported_as_orphan(tmp_path: Path) -> None:
    """Stray non-slug directories under skills/ or mcps/ must not be reported."""
    (tmp_path / "skills" / "__pycache__").mkdir(parents=True)
    (tmp_path / "skills" / "__pycache__" / "junk.pyc").write_bytes(b"\x00\x01")
    result = diagnose_orphans(tmp_path)
    assert result.status == Status.OK
    assert result.findings == []


def test_sidecar_rescues_body_from_orphan(tmp_path: Path) -> None:
    """A body dir with a sidecar (and no inline frontmatter) is NOT an orphan."""
    skill_dir = tmp_path / "skills" / "vendored"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("upstream body without frontmatter\n")
    sidecar = tmp_path / "skills" / "vendored.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: vendored\n  description: x.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )
    result = diagnose_orphans(tmp_path)
    assert result.status == Status.OK
    assert result.findings == []
