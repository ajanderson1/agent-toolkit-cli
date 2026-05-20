"""One-shot content-repo migration: inline-shape skills -> sidecar shape.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import click
import yaml


@click.command("migrate-skills")
@click.option(
    "--content-repo",
    type=click.Path(file_okay=False, dir_okay=True, exists=True, path_type=Path),
    required=True,
    help="Path to the content repo (e.g. ~/GitHub/agent-toolkit).",
)
@click.option("--dry-run", is_flag=True, help="Print the plan without writing files.")
def migrate_skills(content_repo: Path, dry_run: bool) -> None:
    """Rewrite legacy inline-frontmatter skills into the new two-file shape."""
    skills_dir = content_repo / "skills"
    if not skills_dir.is_dir():
        raise click.UsageError(f"no skills/ directory under {content_repo}")

    migrated = 0
    skipped = 0
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        slug = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        sidecar = skills_dir / f"{slug}.toolkit.yaml"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end == -1:
            continue
        fm_yaml = text[4:end]
        body = text[end + 5:]
        fm = yaml.safe_load(fm_yaml) or {}

        if "apiVersion" not in fm:
            continue
        if sidecar.is_file():
            skipped += 1
            continue

        metadata = fm.get("metadata") or {}
        spec = fm.get("spec") or {}
        description = metadata.get("description", "")
        slug_from_fm = metadata.get("name", slug)

        notes = str(metadata.get("notes") or "")
        notes_lines = notes.splitlines()
        arg_hint: str | None = None
        remaining_notes_lines: list[str] = []
        for line in notes_lines:
            if arg_hint is None and line.lstrip().startswith("argument-hint:"):
                arg_hint = line.split(":", 1)[1].strip()
            else:
                remaining_notes_lines.append(line)
        cleaned_notes = "\n".join(remaining_notes_lines).strip()

        new_skill_md = (
            "---\n"
            f"name: {slug_from_fm}\n"
            f"description: {description}\n"
            "---\n"
            + body
        )
        new_sidecar = _render_sidecar(
            slug=slug_from_fm,
            description=description,
            lifecycle=metadata.get("lifecycle", "experimental"),
            notes=cleaned_notes,
            spec=spec,
            arg_hint=arg_hint,
        )

        verb = "would migrate" if dry_run else "migrated"
        click.echo(f"{verb} skills/{slug}/ (sidecar + harness-only SKILL.md frontmatter)")
        if not dry_run:
            skill_md.write_text(new_skill_md, encoding="utf-8")
            sidecar.write_text(new_sidecar, encoding="utf-8")
        migrated += 1

    suffix = " (dry-run)" if dry_run else ""
    if migrated == 0 and skipped == 0:
        click.echo(f"no skills to migrate{suffix}")
    else:
        click.echo(f"{migrated} migrated, {skipped} skipped{suffix}")


def _render_sidecar(
    *,
    slug: str,
    description: str,
    lifecycle: str,
    notes: str,
    spec: dict,
    arg_hint: str | None,
) -> str:
    """Render a sidecar via templated string assembly.

    We don't use yaml.safe_dump because it drops the `# TODO shorten` comment.
    The wrapper shape is small and known; the template is the source of truth.
    """
    lines: list[str] = []
    lines.append("apiVersion: agent-toolkit/v1alpha2")
    lines.append("metadata:")
    lines.append(f"  name: {slug}")
    lines.append(f"  description: {description}")
    lines.append(f"  lifecycle: {lifecycle}")
    lines.append("  # TODO shorten — currently the same as SKILL.md description")
    if notes:
        lines.append("  notes: |")
        for nline in notes.splitlines():
            lines.append(f"    {nline}")
    lines.append("spec:")
    lines.append(f"  origin: {spec.get('origin', 'first-party')}")
    lines.append(f"  vendored_via: {spec.get('vendored_via', 'none')}")
    lines.append("  harnesses:")
    for h in spec.get("harnesses", []):
        lines.append(f"    - {h}")
    if arg_hint is not None:
        lines.append("  per_harness:")
        lines.append("    pi:")
        lines.append(f"      argument_hint: {arg_hint}")
    return "\n".join(lines) + "\n"
