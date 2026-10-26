"""One shared Git subscription, typed browsing and explicit per-kind operations."""
import json
from pathlib import Path

import click

from agent_toolkit_cli.skill_catalog import KINDS, configure_catalog, read_catalog


def list_entries(kind: str | None, as_json: bool) -> None:
    snapshot = read_catalog()
    if snapshot is not None and snapshot.error:
        raise click.ClickException(snapshot.error)
    items = (snapshot.for_kind(kind) if kind else snapshot.entries) if snapshot else ()
    if as_json:
        click.echo(json.dumps([item.as_dict() for item in items]))
    elif not items:
        click.echo("(no catalog entries; subscribe with catalog subscribe URL)")
    else:
        for item in items:
            source = item.npm_source if item.source_type == "npm" else f"{item.source.url} · {item.source.subpath} @ {item.source.ref or '(default)'}"
            click.echo(f"{item.kind}:{item.key} · {source}")


@click.group("catalog")
def catalog() -> None:
    """Manage one shared Git catalog for skills, agents, commands and Pi extensions."""


@catalog.command("subscribe")
@click.argument("url")
@click.option("--ref", default=None, help="Catalog branch, tag or commit (default: remote HEAD).")
def subscribe(url, ref):
    """Validate and save the single user-global subscription; no acquisition."""
    try:
        configure_catalog(url, ref)
    except (ValueError, RuntimeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Shared catalog subscribed; no assets downloaded or enabled.")


@catalog.command("unsubscribe")
def unsubscribe():
    """Stop catalog discovery; retain all acquired content and exposure."""
    configure_catalog(None)
    click.echo("Shared catalog unsubscribed; acquired assets retained.")


@catalog.command("list")
@click.option("--kind", type=click.Choice(tuple(KINDS)))
@click.option("--json", "as_json", is_flag=True)
def list_catalog(kind, as_json):
    """Read one live snapshot; never serve stale listings."""
    list_entries(KINDS[kind] if kind else None, as_json)


@catalog.command("validate")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--admission", is_flag=True, help="Check new/changed sources against required inspection evidence; may download source metadata/packages, never execute upstream code.")
@click.option("--base", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Previously accepted manifest; inspect only new/changed selectors.")
@click.option("--reviews", type=click.Path(file_okay=False, path_type=Path), help="Review record directory (default: reviews/ beside FILE).")
def validate(file, admission, base, reviews):
    """Validate local catalogue metadata, or require source-fit and curator admission checks."""
    import subprocess
    import tarfile
    from agent_toolkit_cli.catalog_admission import validate_catalog
    try:
        count, inspected = validate_catalog(file, admission=admission, base=base, reviews=reviews)
    except subprocess.SubprocessError as exc:
        raise click.ClickException("catalogue source inspection failed or timed out") from exc
    except (KeyError, TypeError, IndexError, tarfile.TarError) as exc:
        raise click.ClickException("invalid source inspection result; check package format and review evidence") from exc
    except (ValueError, OSError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    if admission:
        click.echo(f"Admission checks passed: {inspected} new/changed entries; {count} total. Quality approval relies on recorded curator evidence.")
    else:
        click.echo(f"Schema valid: {count} entries. Upstream sources and content quality were not inspected; use --admission before publishing.")


def check_command(kind: str) -> click.Command:
    @click.command("check")
    @click.argument("slugs", nargs=-1)
    @click.option("-g", "--global", "global_", is_flag=True)
    @click.option("-p", "--project", "project_flag", is_flag=True)
    @click.option("--json", "as_json", is_flag=True)
    @click.pass_context
    def command(ctx, slugs, global_, project_flag, as_json):
        """Check catalogue-associated Git revisions without updating content; npm uses native Pi."""
        from agent_toolkit_cli.asset_update_check import check_assets
        if kind == "agent":
            from agent_toolkit_cli.commands.agent._common import scope_and_roots
        elif kind == "command":
            from agent_toolkit_cli.commands.command._common import scope_and_roots
        else:
            from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
        scope, home, project, _ = scope_and_roots(global_, project_flag,
            (ctx.obj or {}).get("project_root"), **({"read_only": True} if kind != "command" else {}))
        rows = check_assets(kind, slugs, scope=scope, home=home or Path.home(), project=project)
        if as_json:
            click.echo(json.dumps(rows))
        elif not rows:
            click.echo("(no catalogue-associated Git assets in this scope)")
        else:
            for row in rows:
                click.echo(f"{row['slug']}: {row['status']} · checked {row['checked_at']}")
                if row["error"]:
                    click.echo(f"  {row['error']}")
        if any(row["status"] == "unknown" for row in rows):
            ctx.exit(1)
    return command


def kind_catalog(kind: str) -> click.Group:
    @click.group("catalog")
    def group():
        """Browse shared entries; configure the subscription with `catalog subscribe`."""

    @group.command("list")
    @click.option("--json", "as_json", is_flag=True)
    def list_kind(as_json):
        """Read this kind's entries from the live shared catalog."""
        list_entries(kind, as_json)

    @group.command("add")
    @click.argument("key")
    def add_kind(key):
        """Add one Git asset to the global library without enabling it."""
        from agent_toolkit_cli.asset_catalog_ops import resolve_catalog_entry, acquire_catalog_entry
        try:
            snapshot, item = resolve_catalog_entry(kind, key)
            slug = acquire_catalog_entry(item, catalog_url=snapshot.url, home=Path.home())
        except (ValueError, RuntimeError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"added {slug} from catalog; exposure unchanged")

    @group.command("enable")
    @click.argument("key")
    @click.option("--scope", type=click.Choice(("global", "project")), required=True)
    @click.option("--harnesses", required=kind != "pi-extension", hidden=kind == "pi-extension")
    @click.pass_context
    def enable_kind(ctx, key, scope, harnesses):
        """Acquire a Git asset if absent and enable only the explicit targets."""
        from agent_toolkit_cli.asset_catalog_ops import resolve_catalog_entry, enable_catalog_entry
        project = Path((ctx.obj or {}).get("project_root") or Path.cwd()) if scope == "project" else None
        try:
            snapshot, item = resolve_catalog_entry(kind, key)
            if kind == "agent":
                from agent_toolkit_cli.commands.agent._common import parse_harness_tokens
                targets = parse_harness_tokens(harnesses)
            elif kind == "command":
                from agent_toolkit_cli.commands.command._common import parse_harness_tokens
                targets = parse_harness_tokens(harnesses, scope=scope, slug=key, home=Path.home(), project=project)
            else:
                targets = tuple(harnesses.split(",")) if harnesses else ("pi",)
            slug = enable_catalog_entry(item, catalog_url=snapshot.url, targets=targets,
                scope=scope, home=Path.home(), project=project)
        except (ValueError, RuntimeError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"enabled {slug} [{scope}]")

    if kind == "pi-extension":
        @group.command("install")
        @click.argument("key")
        @click.option("--scope", type=click.Choice(("global", "project")), required=True)
        @click.option("--yes", is_flag=True, help="Confirm native npm installation and its possible side effects.")
        @click.pass_context
        def install_native(ctx, key, scope, yes):
            """Explicit native npm installation; may activate bundled resources."""
            from agent_toolkit_cli.asset_catalog_ops import resolve_catalog_entry, install_catalog_npm
            try:
                _, item = resolve_catalog_entry(kind, key)
                if item.source_type != "npm":
                    raise ValueError("use catalog add/enable for Git; catalog install is npm-only")
                click.echo(f"Install {item.npm_source} [{scope}] through native Pi.")
                click.echo("Package installation may execute lifecycle scripts and activate bundled resources.", err=True)
                if not yes:
                    click.confirm("Continue with native installation?", abort=True)
                project = Path((ctx.obj or {}).get("project_root") or Path.cwd()) if scope == "project" else None
                install_catalog_npm(item, scope=scope, home=Path.home(), project=project)
            except (ValueError, RuntimeError, OSError) as exc:
                raise click.ClickException(str(exc)) from exc
            click.echo(f"installed {item.npm_source} [{scope}] through Pi; no Toolkit npm lock written")

    return group
