"""`bundle validate <ref>` — resolve every member, write nothing."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import bundle_install
from agent_toolkit_cli.bundle_manifest import ManifestError, load


@click.command(help="Check a bundle manifest resolves, without installing.")
@click.argument("ref", type=click.Path(path_type=Path))
def validate_cmd(ref: Path) -> None:
    try:
        manifest = load(ref)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    report = bundle_install.run(manifest, scope="global", dry_run=True)
    for label in report.checked:
        click.echo(f"ok       {label}")
    for fail in report.failures:
        click.echo(f"FAIL     {fail}", err=True)
    if not report.ok:
        raise click.ClickException(
            f"bundle {manifest.name!r} did not validate "
            f"({len(report.failures)} member(s) failed)"
        )
    click.echo(f"valid    {manifest.name!r} ({len(manifest.members)} members)")
