"""`mcp migrate` — explicitly adopt a legacy global MCP library."""
from __future__ import annotations

from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]

from agent_toolkit_cli.mcp_library import (
    library_root,
    load_mcp_asset,
    scan_entry_files,
)
from agent_toolkit_cli.mcp_manifest import (
    UnsafeMcpSpecError,
    assert_safe_entry,
    entry_from_materialisation,
    manifest_path,
    read_manifest,
    write_manifest,
)


@click.command("migrate")
def migrate_cmd() -> None:
    """Adopt legacy global MCP library entries into the manifest."""
    home = Path.home()
    library = library_root(home)
    path = manifest_path(home)
    try:
        original = read_manifest(path) if path.is_file() else {}
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    merged = dict(original)
    adopted: list[str] = []
    skipped: list[tuple[str, str]] = []

    for slug, (config_path, sidecar_path) in scan_entry_files(library).items():
        if slug in original:
            continue
        if config_path is None or sidecar_path is None:
            skipped.append(
                (slug, "incomplete materialisation; value redacted")
            )
            continue
        try:
            asset = load_mcp_asset(library, slug)
            entry = entry_from_materialisation(asset)
            assert_safe_entry(entry)
        except UnsafeMcpSpecError as exc:
            skipped.append(
                (slug, f"unsafe literal at {exc.field_path}; value redacted")
            )
            continue
        except (OSError, ValueError, yaml.YAMLError):
            # JSON/YAML parse errors and unknown/non-lossless historical shapes
            # can contain source snippets in their native exception messages.
            skipped.append(
                (slug, "materialisation cannot be adopted; value redacted")
            )
            continue
        merged[slug] = entry
        adopted.append(slug)

    if not path.is_file() or merged != original:
        try:
            write_manifest(path, merged)
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc

    for slug in adopted:
        click.echo(f"adopted {slug}")
    for slug, reason in skipped:
        click.echo(f"skipped {slug}: {reason}")
    click.echo(f"summary: {len(adopted)} adopted, {len(skipped)} skipped")
