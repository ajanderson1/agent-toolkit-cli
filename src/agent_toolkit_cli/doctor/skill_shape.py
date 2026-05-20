"""Skill-shape advisory.

Warns on legacy inline-frontmatter skills (no sidecar) and errors on
drift states (sidecar present + v1alpha2 wrapper in SKILL.md, or
sidecar present + missing SKILL.md frontmatter).

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.result import GroupResult, Status
from agent_toolkit_cli.walker import extract_frontmatter

_MIGRATE_CMD = "`agent-toolkit migrate-skills`"
_SPEC_REF = "docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md"

# Slugs that are not real skills (pycache, dot-dirs, etc.).
_SKIP_PREFIXES = (".", "__")


def run(toolkit_root: Path) -> GroupResult:
    """Inspect every skills/<slug>/SKILL.md for shape issues."""
    skills_dir = toolkit_root / "skills"
    warnings: list[str] = []
    errors: list[str] = []

    if skills_dir.is_dir():
        for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            slug = skill_dir.name
            if any(slug.startswith(prefix) for prefix in _SKIP_PREFIXES):
                continue

            skill_md = skill_dir / "SKILL.md"
            sidecar = skills_dir / f"{slug}.toolkit.yaml"

            if not skill_md.is_file():
                continue

            has_sidecar = sidecar.is_file()
            skill_md_fm = extract_frontmatter(skill_md)  # None if no frontmatter block
            has_fm = skill_md_fm is not None
            has_apiversion = has_fm and "apiVersion" in skill_md_fm

            if has_apiversion and not has_sidecar:
                # Legacy inline shape — nudge migration.
                warnings.append(
                    f"skills/{slug}/SKILL.md uses legacy inline frontmatter (no sidecar) — "
                    f"migrate to sidecar shape via {_MIGRATE_CMD} "
                    f"(see {_SPEC_REF})"
                )
                continue

            if has_apiversion and has_sidecar:
                # Drift: mid-migration corruption — both present.
                errors.append(
                    f"skills/{slug}/: drift — sidecar exists but SKILL.md still carries "
                    f"the v1alpha2 wrapper (apiVersion key). Remove the wrapper from "
                    f"SKILL.md or re-run {_MIGRATE_CMD} to complete migration."
                )
                continue

            if has_sidecar and not has_fm:
                # Broken: sidecar exists but SKILL.md has no top-level frontmatter.
                errors.append(
                    f"skills/{slug}/SKILL.md: has sidecar but no top-level frontmatter block — "
                    f"add a minimal frontmatter section (name, description) or re-run "
                    f"{_MIGRATE_CMD}."
                )
                continue

    if errors:
        return GroupResult(
            name="skill-shape",
            status=Status.FAIL,
            summary=f"{len(errors)} shape error(s), {len(warnings)} warning(s)",
            findings=errors + warnings,
            fix_hint=f"run {_MIGRATE_CMD} to migrate inline skills to sidecar shape",
        )
    if warnings:
        return GroupResult(
            name="skill-shape",
            status=Status.WARN,
            summary=f"{len(warnings)} legacy inline skill(s) — migration available",
            findings=warnings,
            fix_hint=f"run {_MIGRATE_CMD} to migrate inline skills to sidecar shape",
        )
    return GroupResult(
        name="skill-shape",
        status=Status.OK,
        summary="all skills use the expected sidecar or harness-only shape",
        findings=[],
    )
