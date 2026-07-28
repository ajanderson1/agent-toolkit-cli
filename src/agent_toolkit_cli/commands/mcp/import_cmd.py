"""`mcp import <file>` — reconstruct the global library from a manifest file.

Additive merge: only slugs absent locally are added (skip-if-exists is total).
Entries embedding local machine paths (--local) are hard-skipped. Unsafe specs
(secrets) are quarantined and skipped. Manifest persistence occurs after each
successful server addition to ensure crash-resume correctness.

The export artifact is just another machine's `mcps-library.json`.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.commands.mcp.update_cmd import _reresolve
from agent_toolkit_cli.mcp_library import library_root, materialize_entry, scan_entry_files
from agent_toolkit_cli.mcp_manifest import (
    UnsafeMcpSpecError,
    assert_safe_entry,
    manifest_path,
    read_manifest,
    write_manifest,
)

_NOTES = (
    "  • Imported servers are now in the global library but not installed.\n"
    "    Run `agent-toolkit-cli mcp install <slug> --harness <name>` to use them.",
)

def _print_notes() -> None:
    click.echo("\nNotes:")
    for note in _NOTES:
        click.echo(note)

@click.command("import", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp import ~/sync/mcps-library.json
  agent-toolkit-cli mcp import ~/sync/mcps-library.json --latest
""")
@click.argument("file", type=click.Path(path_type=Path), required=True)
@click.option("--latest", is_flag=True,
              help="Re-resolve versioned specs (npx/uvx) to their current upstream HEAD/version.")
@click.pass_context
def import_cmd(ctx: click.Context, file: Path, latest: bool) -> None:
    """Add MCP servers from another machine's manifest FILE into the global library."""
    if not file.exists():
        raise click.UsageError(f"import file not found: {file}")

    if file.name == "mcps-lock.json":
        raise click.ClickException(
            "mcps-lock.json records where servers are installed, not how they were built. "
            "You must import from mcps-library.json instead."
        )

    try:
        import json
        from agent_toolkit_cli.mcp_manifest import _entry_from_raw
        raw = json.loads(file.read_text(encoding="utf-8"))
        if raw.get("version") != 1 or not isinstance(raw.get("mcps"), dict):
            raise ValueError("Unsupported or malformed MCP library manifest")
        
        incoming_manifest = {}
        unsafe_entries = []
        for key, value in raw["mcps"].items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("Malformed entry")
            if value.get("slug") != key:
                raise ValueError("Slug does not match map key")
            try:
                entry = _entry_from_raw(value, path=file)
                incoming_manifest[key] = entry
            except UnsafeMcpSpecError as exc:
                unsafe_entries.append((key, exc))
    except (ValueError, Exception) as exc:
        raise click.ClickException(f"Invalid import file: {exc}") from exc

    home = Path.home()
    library = library_root(home)
    local_manifest_file = manifest_path(home)
    
    current_manifest = read_manifest(local_manifest_file) if local_manifest_file.is_file() else {}
    physical_slugs = set(scan_entry_files(library).keys())

    n = len(incoming_manifest)
    click.echo(f"importing from {file} ({n} server{'s' if n != 1 else ''})\n")

    added: list[tuple[str, str | None, bool]] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    # Pre-add unsafe entries as skipped so they are reported first or inline
    for slug, exc in unsafe_entries:
        skipped.append(slug)
        click.echo(f"  skipped  {slug}  ({exc})")

    for slug in sorted(incoming_manifest.keys()):
        entry = incoming_manifest[slug]

        if slug in current_manifest or slug in physical_slugs:
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (already present)")
            continue

        if entry.install_method == "local":
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (local paths cannot be imported)")
            continue



        if latest:
            try:
                entry_to_write, note = _reresolve(entry, slug)
                if note:
                    click.echo(note, err=True)
            except Exception as exc:
                failed.append((slug, str(exc)))
                click.echo(f"  failed   {slug}  ({exc})")
                continue
        else:
            entry_to_write = entry

        current_manifest[slug] = entry_to_write

        try:
            write_manifest(local_manifest_file, current_manifest)
            materialize_entry(library, entry_to_write, overwrite=False)
        except Exception as exc:
            failed.append((slug, str(exc)))
            click.echo(f"  failed   {slug}  ({exc})")
            continue

        version_display = entry_to_write.resolved_version or "floating"
        suffix = f"(latest: {version_display})" if latest else f"@ {version_display}"
        click.echo(f"  added    {slug}  <- {entry.source} {suffix}")
        added.append((slug, version_display, latest))

    click.echo(
        f"\nsummary: {len(added)} added, {len(skipped)} skipped, "
        f"{len(failed)} failed"
    )
    _print_notes()
    if failed:
        ctx.exit(1)
