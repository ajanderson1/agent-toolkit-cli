"""CLI configuration and live browsing of the optional shared skill catalog."""
import json
from pathlib import Path

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


@catalog_cmd.command("add")
@click.argument("key")
def add_catalog(key: str) -> None:
    """Acquire one catalog skill into the library, without enabling it."""
    from agent_toolkit_cli.skill_catalog_ops import resolve_catalog_skill, acquire_catalog_skill
    try:
        snapshot, item = resolve_catalog_skill(key)
        slug = acquire_catalog_skill(item, catalog_url=snapshot.url)
    except (ValueError, RuntimeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"added {slug} from catalog; exposure unchanged")


@catalog_cmd.command("enable")
@click.argument("key")
@click.option("--scope", type=click.Choice(["global", "project"]), default="global", show_default=True)
@click.option("--agents", "agents_str", default="standard", show_default=True)
@click.pass_context
def enable_catalog(ctx: click.Context, key: str, scope: str, agents_str: str) -> None:
    """Acquire a catalog skill and enable selected harness exposure."""
    from agent_toolkit_cli.commands.skill import install_cmd, _resolve_agents
    from agent_toolkit_cli.skill_install import validate_projection_context
    from agent_toolkit_cli.skill_catalog_ops import resolve_catalog_skill, acquire_catalog_skill
    from agent_toolkit_cli.paperclip_paths import normalize_skill_project_root
    candidate = (ctx.obj.get("project_root") if ctx.obj else None) or Path.cwd()
    project = normalize_skill_project_root(candidate) if scope == "project" else None
    try:
        agents = _resolve_agents(agents_str, scope, project=project)
        if not agents:
            raise ValueError("no harness targets selected")
        snapshot, item = resolve_catalog_skill(key)
        validate_projection_context(slug=key, target_agents=agents, scope=scope, home=Path.home(), project=project)
        slug = acquire_catalog_skill(item, catalog_url=snapshot.url)
        ctx.invoke(install_cmd, slug=slug, source_filter=None, agents_str=agents_str,
                   scope=scope, project_flag=False, migrate_to_central=False)
    except (ValueError, RuntimeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
