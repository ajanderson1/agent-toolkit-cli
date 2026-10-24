"""CLI configuration and live browsing of the optional shared skill catalog."""
import json

import click

from agent_toolkit_cli.skill_catalog import configure_catalog, read_catalog


@click.group("catalog")
def catalog_cmd() -> None:
    """Subscribe to one shared Git catalog; no automatic skill activation."""


@catalog_cmd.command("subscribe")
@click.argument("url")
@click.option("--ref", default=None, help="Catalog branch, tag or commit (default: remote HEAD).")
def subscribe(url: str, ref: str | None) -> None:
    """Validate URL and save a user-global catalog subscription."""
    try:
        configure_catalog(url, ref)
    except (ValueError, RuntimeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Skill catalog subscribed; no skills downloaded or enabled.")


@catalog_cmd.command("unsubscribe")
def unsubscribe() -> None:
    """Remove subscription only; keep acquired skills and projections."""
    configure_catalog(None)
    click.echo("Skill catalog unsubscribed; library skills retained.")


@catalog_cmd.command("list")
@click.option("--json", "as_json", is_flag=True)
def list_catalog(as_json: bool) -> None:
    """Read the live catalog; never fall back to old listings."""
    snapshot = read_catalog()
    if snapshot is not None and snapshot.error:
        raise click.ClickException(snapshot.error)
    items = snapshot.skills if snapshot else ()
    if as_json:
        click.echo(json.dumps([{"key": i.key, "description": i.description, "source": i.source.url, "path": i.source.subpath, "ref": i.source.ref} for i in items]))
    elif not items:
        click.echo("(no catalog skills; subscribe with skills catalog subscribe URL)")
    else:
        for item in items:
            click.echo(f"{item.key} · {item.source.url} · {item.source.subpath} @ {item.source.ref or '(default)'}")
