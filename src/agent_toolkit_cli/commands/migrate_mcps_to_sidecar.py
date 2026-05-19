"""One-shot migration: move MCP frontmatter from README.md to sidecar."""
from __future__ import annotations

from pathlib import Path

import click
import yaml

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._ui import header, summary
from agent_toolkit_cli.walker import extract_frontmatter


@click.command(
    name="migrate-mcps-to-sidecar",
    short_help="One-shot: move MCP frontmatter from README.md to sidecar files.",
)
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option("--dry-run", is_flag=True, help="Report what would change; write nothing.")
@click.pass_context
def migrate_mcps_to_sidecar(ctx: click.Context, toolkit_root: Path | None, dry_run: bool) -> None:
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            root = resolve_toolkit_root(explicit=None)
        except RepoNotFoundError as e:
            raise click.ClickException(str(e))
    else:
        try:
            root = resolve_toolkit_root(Path(toolkit_root).resolve())
        except RepoNotFoundError as e:
            raise click.ClickException(str(e))

    header("Migrate MCP metadata to sidecars")
    mcps_dir = root / "mcps"
    if not mcps_dir.is_dir():
        click.echo("No mcps/ directory found.")
        return

    moved = 0
    skipped = 0
    for mcp_dir in sorted(p for p in mcps_dir.iterdir() if p.is_dir()):
        slug = mcp_dir.name
        readme = mcp_dir / "README.md"
        sidecar = mcps_dir / f"{slug}.toolkit.yaml"

        if not readme.is_file():
            skipped += 1
            continue
        fm = extract_frontmatter(readme)
        if fm is None:
            # README has no toolkit frontmatter — nothing to migrate
            skipped += 1
            continue
        if sidecar.exists():
            # Sidecar already exists AND README has frontmatter — mutex case.
            # Let `check` flag it; don't migrate over an existing sidecar.
            skipped += 1
            continue

        # Strip frontmatter from README. The frontmatter is everything from
        # "---\n" at the start to the closing "\n---\n".
        text = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
        end = text.find("\n---\n", 4)
        if end == -1:
            skipped += 1
            continue
        new_readme = text[end + len("\n---\n") :].lstrip("\n")

        # Emit sidecar (bare YAML, no --- markers)
        sidecar_yaml = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)

        if dry_run:
            click.echo(f"  Would write {sidecar.relative_to(root)}")
            click.echo(f"  Would strip frontmatter from {readme.relative_to(root)}")
        else:
            sidecar.write_text(sidecar_yaml, encoding="utf-8")
            readme.write_text(new_readme, encoding="utf-8")
            click.echo(f"  Wrote {sidecar.relative_to(root)}")
            click.echo(f"  Stripped frontmatter from {readme.relative_to(root)}")
        moved += 1

    summary(f"Migrated {moved} MCP(s); skipped {skipped}.")
