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

        # Best-effort heuristic: lift the first `argument-hint:` line from
        # metadata.notes into spec.per_harness.pi.argument_hint. The legacy
        # convention is to put it on a dedicated leading line; an
        # `argument-hint:` substring appearing mid-paragraph could be
        # misextracted, but no such usage exists in the content repo today.
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
            f"name: {_yaml_scalar(slug_from_fm)}\n"
            f"description: {_yaml_scalar(description)}\n"
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


def _yaml_scalar(value: object) -> str:
    """Render a single string-like value safely as a YAML scalar.

    PyYAML's safe_dump on a bare string emits a full YAML stream
    (`--- value\\n...\\n`) — we want just the scalar representation. Trick:
    dump a single-key dict and slice off the `k: ` prefix. This gets us
    correct quoting/escaping for all the bad cases (colons, hashes,
    YAML reserved words like `yes`/`no`/`null`, leading dashes, numerics-
    as-strings, etc.) without doing the rules by hand.

    The value is coerced to `str` defensively. Skills' name/description/
    lifecycle/harness scalars are single-line by convention; embedded
    newlines aren't supported by this helper.
    """
    out = yaml.safe_dump(
        {"k": str(value)}, default_flow_style=False, allow_unicode=True
    )
    # Slice off the "k: " prefix and the trailing newline.
    return out[len("k: ") :].rstrip("\n")


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

    We don't use yaml.safe_dump for the whole document because it drops the
    `# TODO shorten` comment we need to surface to authors. Instead we
    template the structure and route each user-supplied scalar through
    `_yaml_scalar` for correct quoting/escaping.
    """
    lines: list[str] = []
    lines.append("apiVersion: agent-toolkit/v1alpha2")
    lines.append("metadata:")
    lines.append(f"  name: {_yaml_scalar(slug)}")
    lines.append(f"  description: {_yaml_scalar(description)}")
    lines.append(f"  lifecycle: {_yaml_scalar(lifecycle)}")
    lines.append("  # TODO shorten — currently the same as SKILL.md description")
    if notes:
        lines.append("  notes: |")
        for nline in notes.splitlines():
            lines.append(f"    {nline}")
    lines.append("spec:")
    lines.append(f"  origin: {_yaml_scalar(spec.get('origin', 'first-party'))}")
    lines.append(f"  vendored_via: {_yaml_scalar(spec.get('vendored_via', 'none'))}")
    lines.append("  harnesses:")
    for h in spec.get("harnesses", []):
        lines.append(f"    - {_yaml_scalar(h)}")
    if arg_hint is not None:
        lines.append("  per_harness:")
        lines.append("    pi:")
        lines.append(f"      argument_hint: {_yaml_scalar(arg_hint)}")
    return "\n".join(lines) + "\n"
