"""Explicit package self-update command."""
from __future__ import annotations

import click

from agent_toolkit_cli import self_update


@click.command("update")
@click.option("check_only", "--check", is_flag=True, help="Check immediately without changing the installation.")
@click.option("use_main", "--main", is_flag=True, help="Use the newest canonical main commit instead of a stable release.")
def update(check_only: bool, use_main: bool) -> None:
    """Update the Toolkit package (both CLI and TUI), not managed assets."""
    try:
        if check_only:
            if use_main:
                latest = self_update.resolve_commit("main")
                current = self_update.installed_commit()
                if latest == current:
                    click.echo(f"Already at latest main commit: {latest}.")
                else:
                    click.echo(f"Latest main commit: {latest}; installed commit: {current or 'unknown'}. Run `atc update --main` to update.")
            else:
                release = self_update.latest_release(force=True)
                if self_update.is_newer(release):
                    click.echo(f"New update available: {self_update.installed_version()} → {release.version}. Run `atc update` to update.")
                else:
                    click.echo(f"No newer stable release (installed {self_update.installed_version()}, latest {release.version}).")
            return
        click.echo("Checking and updating Toolkit from canonical main..." if use_main else "Checking and updating Toolkit from the latest stable release...")
        receipt = self_update.perform_update(main=use_main)
        if receipt is None:
            click.echo("Already up to date; no changes made.")
        else:
            click.echo(f"Toolkit updated. Restart any running TUI. Source commit and wheel SHA-256: {receipt}")
    except (self_update.UpdateError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
