"""doctor.skill_shape reports advisory on legacy inline skills and drift states.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.result import Status
from agent_toolkit_cli.doctor.skill_shape import run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_skill_md(root: Path, slug: str, content: str) -> None:
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)


def _write_sidecar(root: Path, slug: str, content: str) -> None:
    sidecar_path = root / "skills" / f"{slug}.toolkit.yaml"
    sidecar_path.write_text(content)


_SIDECAR_CONTENT = (
    "apiVersion: agent-toolkit/v1alpha2\n"
    "metadata:\n  name: {slug}\n  description: CLI desc.\n  lifecycle: experimental\n"
    "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
)

_INLINE_CONTENT = (
    "---\n"
    "apiVersion: agent-toolkit/v1alpha2\n"
    "metadata:\n  name: {slug}\n  description: Legacy desc.\n  lifecycle: experimental\n"
    "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    "---\nbody\n"
)

_HARNESS_ONLY_FM = "---\nname: {slug}\ndescription: Harness desc.\n---\nbody\n"


# ---------------------------------------------------------------------------
# Tests: clean states
# ---------------------------------------------------------------------------

def test_new_shape_skill_is_clean(tmp_path: Path) -> None:
    """Sidecar + minimal harness frontmatter in SKILL.md = clean."""
    slug = "demo"
    _write_skill_md(tmp_path, slug, _HARNESS_ONLY_FM.format(slug=slug))
    _write_sidecar(tmp_path, slug, _SIDECAR_CONTENT.format(slug=slug))
    result = run(tmp_path)
    assert result.status == Status.OK, result.findings


def test_harness_only_skill_with_no_sidecar_is_clean(tmp_path: Path) -> None:
    """SKILL.md with plain harness-style frontmatter (no apiVersion, no sidecar) is clean."""
    slug = "plain"
    _write_skill_md(tmp_path, slug, _HARNESS_ONLY_FM.format(slug=slug))
    result = run(tmp_path)
    assert result.status == Status.OK, result.findings


def test_no_skills_dir_is_clean(tmp_path: Path) -> None:
    """If there is no skills/ directory, nothing to check — should be OK."""
    result = run(tmp_path)
    assert result.status == Status.OK


def test_skill_without_skill_md_is_skipped(tmp_path: Path) -> None:
    """A skills/<slug>/ dir with no SKILL.md should be ignored (not errored)."""
    skill_dir = tmp_path / "skills" / "empty"
    skill_dir.mkdir(parents=True)
    result = run(tmp_path)
    assert result.status == Status.OK


def test_pycache_skipped(tmp_path: Path) -> None:
    """Stray __pycache__ directories under skills/ must not be reported."""
    (tmp_path / "skills" / "__pycache__").mkdir(parents=True)
    result = run(tmp_path)
    assert result.status == Status.OK


# ---------------------------------------------------------------------------
# Tests: warning — legacy inline shape
# ---------------------------------------------------------------------------

def test_legacy_inline_skill_warns(tmp_path: Path) -> None:
    """SKILL.md with apiVersion wrapper but no sidecar => WARN mentioning migrate-skills."""
    slug = "legacy"
    _write_skill_md(tmp_path, slug, _INLINE_CONTENT.format(slug=slug))
    result = run(tmp_path)
    assert result.status == Status.WARN, result
    assert any("migrate" in f for f in result.findings), result.findings
    assert result.fix_hint is not None and "migrate" in result.fix_hint


def test_multiple_legacy_skills_all_warned(tmp_path: Path) -> None:
    """Two legacy inline skills => two warnings, still WARN status."""
    for slug in ("alpha", "beta"):
        _write_skill_md(tmp_path, slug, _INLINE_CONTENT.format(slug=slug))
    result = run(tmp_path)
    assert result.status == Status.WARN
    assert len(result.findings) == 2


# ---------------------------------------------------------------------------
# Tests: error — drift state (sidecar + v1alpha2 wrapper in SKILL.md)
# ---------------------------------------------------------------------------

def test_drift_sidecar_plus_v1alpha2_inline(tmp_path: Path) -> None:
    """Sidecar exists AND SKILL.md still has apiVersion wrapper => FAIL (drift)."""
    slug = "drift"
    _write_skill_md(tmp_path, slug, _INLINE_CONTENT.format(slug=slug))
    _write_sidecar(tmp_path, slug, _SIDECAR_CONTENT.format(slug=slug))
    result = run(tmp_path)
    assert result.status == Status.FAIL, result
    assert any("apiVersion" in f or slug in f for f in result.findings), result.findings
    assert any("migrate" in f for f in result.findings), result.findings


# ---------------------------------------------------------------------------
# Tests: error — sidecar present but SKILL.md has no frontmatter
# ---------------------------------------------------------------------------

def test_sidecar_with_no_skill_md_frontmatter(tmp_path: Path) -> None:
    """Sidecar present but SKILL.md has no frontmatter block => FAIL."""
    slug = "broken"
    _write_skill_md(tmp_path, slug, "no frontmatter here\n")
    _write_sidecar(tmp_path, slug, _SIDECAR_CONTENT.format(slug=slug))
    result = run(tmp_path)
    assert result.status == Status.FAIL, result
    assert any("frontmatter" in f for f in result.findings), result.findings


# ---------------------------------------------------------------------------
# Tests: error beats warning in combined result
# ---------------------------------------------------------------------------

def test_errors_take_precedence_over_warnings(tmp_path: Path) -> None:
    """When both legacy (warn) and drift (error) skills exist, status is FAIL."""
    _write_skill_md(tmp_path, "legacy", _INLINE_CONTENT.format(slug="legacy"))
    _write_skill_md(tmp_path, "drift", _INLINE_CONTENT.format(slug="drift"))
    _write_sidecar(tmp_path, "drift", _SIDECAR_CONTENT.format(slug="drift"))
    result = run(tmp_path)
    assert result.status == Status.FAIL


# ---------------------------------------------------------------------------
# Test: group is registered in the doctor command
# ---------------------------------------------------------------------------

def test_skill_shape_registered_in_doctor_groups() -> None:
    """The skill-shape group is wired into the doctor command."""
    from agent_toolkit_cli.commands.doctor import _GROUPS
    assert "skill-shape" in _GROUPS
