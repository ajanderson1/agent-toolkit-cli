"""`agent-toolkit-cli pi …` — unified Pi extension view + manage verbs.

This module owns the `pi` Click group. Inventory landed in commit 1.
`sync` lands in commit 2; `load`/`unload` land in commit 3.
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit_cli._allowlist import read_allowlist
from agent_toolkit_cli._pi_fetch import (
    PiNotFoundError,
    fetch_package,
    remove_package_fetched,
)
from agent_toolkit_cli._pi_inventory import (
    PiRecord,
    build_pi_inventory,
    slug_from_source,
)
from agent_toolkit_cli._pi_paths import PiPaths
from agent_toolkit_cli._pi_settings import (
    add_package,
    read_extensions_overrides,
    read_packages,
    remove_package,
    write_packages,
)
from agent_toolkit_cli.commands._yaml_edit import add_slug, remove_slug


def _read_node_modules_dir(d: Path) -> set[str]:
    if not d.is_dir():
        return set()
    return {p.name for p in d.iterdir() if p.is_dir() or p.is_symlink()}


def _gather_inventory(home: Path, project_root: Path) -> list[PiRecord]:
    pp = PiPaths(home=home, project_root=project_root)

    user_packages = read_packages(pp.user_settings_json)
    project_packages = read_packages(pp.project_settings_json)
    user_node_modules = _read_node_modules_dir(pp.user_node_modules_dir)
    project_node_modules = _read_node_modules_dir(pp.project_node_modules_dir)

    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    project_allow = read_allowlist(project_root / ".agent-toolkit.yaml")

    user_pi_exts = list(user_allow.get("pi_extensions", []) or [])
    project_pi_exts = list(project_allow.get("pi_extensions", []) or [])
    user_pi_pkgs = list(user_allow.get("pi_packages", []) or [])
    project_pi_pkgs = list(project_allow.get("pi_packages", []) or [])

    user_overrides = read_extensions_overrides(pp.user_settings_json)
    project_overrides = read_extensions_overrides(pp.project_settings_json)

    return build_pi_inventory(
        paths=pp,
        user_packages=user_packages,
        project_packages=project_packages,
        user_node_modules=user_node_modules,
        project_node_modules=project_node_modules,
        user_allowlist_pi_extensions=user_pi_exts,
        project_allowlist_pi_extensions=project_pi_exts,
        user_allowlist_pi_packages=user_pi_pkgs,
        project_allowlist_pi_packages=project_pi_pkgs,
        user_extensions_overrides=user_overrides,
        project_extensions_overrides=project_overrides,
    )


@click.group(name="pi")
def pi() -> None:
    """Pi: unified extension inventory and load/unload across both channels."""


@pi.command(name="inventory")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "both"]),
    default="both",
    help="Restrict view to user, project, or both (default).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "text"]),
    default="text",
)
@click.pass_context
def inventory_cmd(ctx: click.Context, scope: str, fmt: str) -> None:
    """Emit one record per extension Pi could load.

    Reads first-party auto-discovery dirs + third-party `settings.json` and
    `node_modules/` + the toolkit allowlist. Read-only.
    """
    home = Path.home()
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    records = _gather_inventory(home=home, project_root=project_root)

    # Optional scope filter — drop rows where the requested scope
    # has no loaded-or-intent presence.
    if scope == "user":
        records = [
            r
            for r in records
            if r.user_loaded or r.toolkit_intent in ("user", "both")
        ]
    elif scope == "project":
        records = [
            r
            for r in records
            if r.project_loaded or r.toolkit_intent in ("project", "both")
        ]

    if fmt == "json":
        click.echo(json.dumps([r.to_dict() for r in records], indent=2))
        return

    # text format — one row per record
    if not records:
        click.echo("(no Pi extensions found)")
        return
    click.echo(f"{'SLUG':<24} {'ORIGIN':<12} {'U':<3} {'P':<3} {'INTENT':<8} SOURCE")
    for r in records:
        click.echo(
            f"{r.slug:<24} {r.origin:<12} "
            f"{'✓' if r.user_loaded else '—':<3} "
            f"{'✓' if r.project_loaded else '—':<3} "
            f"{r.toolkit_intent:<8} {r.source}"
        )


@pi.command(name="sync")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "both"]),
    default="both",
    help="Reconcile user, project, or both allowlist files (default both).",
)
@click.pass_context
def sync_cmd(ctx: click.Context, scope: str) -> None:
    """Reconcile allowlist ``pi_packages:`` → settings.json ``packages[]``.

    Writes only. Does NOT invoke ``pi install`` (fetch step is part of
    ``pi load``). Use ``pi sync`` after manually editing the allowlist.
    Idempotent: a no-op when settings.json already matches the allowlist.
    """
    home = Path.home()
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    scopes = ("user", "project") if scope == "both" else (scope,)
    pp = PiPaths(home=home, project_root=project_root)

    for s in scopes:
        allow_path = (
            home / ".agent-toolkit.yaml"
            if s == "user"
            else project_root / ".agent-toolkit.yaml"
        )
        allow = read_allowlist(allow_path)
        desired = list(dict.fromkeys(allow.get("pi_packages", []) or []))
        settings_path = (
            pp.user_settings_json if s == "user" else pp.project_settings_json
        )

        current = read_packages(settings_path)
        if current == desired:
            continue
        write_packages(settings_path, desired)


def _allowlist_path(scope: str, home: Path, project_root: Path) -> Path:
    return (
        home / ".agent-toolkit.yaml"
        if scope == "user"
        else project_root / ".agent-toolkit.yaml"
    )


def _is_third_party_source(target: str) -> bool:
    """``npm:``/``git:`` prefix → third-party. Bare slug → first-party."""
    return target.startswith("npm:") or target.startswith("git:")


def _resolve_first_party_asset(
    slug: str, ctx: click.Context
) -> tuple[Path, Path] | None:
    """Return (toolkit_root, asset_dir) for a first-party pi-extension slug.

    Looks up the toolkit repo via the same resolution path as the rest of the
    CLI (``--toolkit-repo`` flag / ``AGENT_TOOLKIT_REPO`` env / walk-up). Returns
    None if the toolkit repo can't be resolved or the slug isn't present.
    """
    from agent_toolkit_cli._repo_resolution import (  # noqa: PLC0415
        RepoNotFoundError,
        resolve_toolkit_root,
    )
    from agent_toolkit_cli.commands._link_lib import (  # noqa: PLC0415
        _asset_harnesses,
    )
    from agent_toolkit_cli.walker import discover_assets  # noqa: PLC0415

    toolkit_root: Path | None = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(None)
        except RepoNotFoundError:
            return None
    for asset in discover_assets(toolkit_root):
        if asset.kind != "pi-extension" or asset.slug != slug:
            continue
        # Mirror `_link_lib.maybe_link`'s harness-declaration check: a
        # `pi-extension` asset that doesn't declare `pi` in `spec.harnesses`
        # would be refused by the linker, so refuse here too.
        if "pi" not in _asset_harnesses(asset.path, asset.kind):
            continue
        return toolkit_root, asset.path
    return None


@pi.command(name="load")
@click.argument("target")
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    required=True,
    help="Which scope to load into. Required (no implicit default).",
)
@click.pass_context
def load_cmd(ctx: click.Context, target: str, scope: str) -> None:
    """Make TARGET loaded in SCOPE.

    TARGET is either a bare slug (first-party pi-extension) or a
    ``npm:``/``git:`` source string (third-party). The toolkit writes its
    config (allowlist + settings.json for third-party) directly, then for
    third-party invokes ``pi install`` only to populate node_modules.
    """
    home = Path.home()
    project_root = (ctx.obj or {}).get("project_root")
    if project_root is None:
        project_root = Path.cwd()

    allow_path = _allowlist_path(scope, home, project_root)
    pp = PiPaths(home=home, project_root=project_root)

    if _is_third_party_source(target):
        settings_path = (
            pp.user_settings_json if scope == "user" else pp.project_settings_json
        )
        node_modules_dir = (
            pp.user_node_modules_dir
            if scope == "user"
            else pp.project_node_modules_dir
        )
        slug = slug_from_source(target)
        already_in_settings = target in read_packages(settings_path)
        already_fetched = (node_modules_dir / slug).is_dir()
        # Idempotency: if every artifact is already in place, ensure the
        # allowlist also lists it and stop — no `pi install` call.
        if already_in_settings and already_fetched:
            add_slug(allow_path, "pi_packages", target)
            return

        # 1. Toolkit writes its records first.
        add_slug(allow_path, "pi_packages", target)
        add_package(settings_path, target)
        # 2. Toolkit invokes `pi install` for the fetch only.
        try:
            fetch_package(
                target, scope=scope, home=home, project_root=project_root
            )
        except PiNotFoundError as exc:
            raise click.ClickException(
                "`pi` binary not on PATH — third-party fetch requires Pi installed."
            ) from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        return

    # First-party path: allowlist entry + symlink under
    # ~/.pi/agent/extensions/<slug>/ (user) or <project>/.pi/extensions/<slug>/
    # (project). We deliberately bypass `_link_lib.maybe_link` here to avoid
    # pulling in projection/translation machinery for the single-slug case.
    # `pi-extension` assets are non-translated, so a bare
    # `symlink_to(asset_path.parent)` reproduces the on-disk shape
    # `maybe_link` would have produced. We replicate `maybe_link`'s
    # harness-declaration check inline (see `_resolve_first_party_asset`).
    target_dir = (
        pp.user_extensions_dir if scope == "user" else pp.project_extensions_dir
    )
    slot_path = target_dir / target

    add_slug(allow_path, "pi_extensions", target)

    if slot_path.is_symlink():
        # Already linked — idempotent no-op.
        return
    if slot_path.exists():
        raise click.ClickException(
            f"{slot_path} already exists and is not a symlink — refusing to "
            "overwrite. Run `agent-toolkit-cli doctor` for context."
        )

    resolved = _resolve_first_party_asset(target, ctx)
    if resolved is None:
        raise click.ClickException(
            f"first-party pi-extension {target!r} not found in toolkit repo "
            "(checked --toolkit-repo / AGENT_TOOLKIT_REPO / walk-up)."
        )
    _toolkit_root, asset_path = resolved
    # discover_assets returns the asset's `extension.meta.yaml` file path for
    # pi-extension; the slot symlink should point at its parent directory.
    source_dir = asset_path.parent if asset_path.is_file() else asset_path
    target_dir.mkdir(parents=True, exist_ok=True)
    slot_path.symlink_to(source_dir)


@pi.command(name="unload")
@click.argument("target")
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    required=True,
    help="Which scope to unload from. Required (no implicit default).",
)
@click.pass_context
def unload_cmd(ctx: click.Context, target: str, scope: str) -> None:
    """Make TARGET not-loaded in SCOPE.

    Toolkit removes its config first, then for third-party invokes
    ``pi remove`` to purge node_modules. First-party removes the symlink
    (refusing to delete hand-authored real directories).
    """
    home = Path.home()
    project_root = (ctx.obj or {}).get("project_root")
    if project_root is None:
        project_root = Path.cwd()

    allow_path = _allowlist_path(scope, home, project_root)
    pp = PiPaths(home=home, project_root=project_root)

    if _is_third_party_source(target):
        settings_path = (
            pp.user_settings_json if scope == "user" else pp.project_settings_json
        )
        # 1. Toolkit removes its records first.
        try:
            remove_slug(allow_path, "pi_packages", target)
        except FileNotFoundError:
            pass
        remove_package(settings_path, target)
        # 2. Toolkit invokes `pi remove` to purge node_modules. Failure is
        # non-fatal: the config is gone; doctor will surface any drift.
        try:
            remove_package_fetched(
                target, scope=scope, home=home, project_root=project_root
            )
        except PiNotFoundError:
            pass
        except RuntimeError:
            pass
        return

    # First-party.
    target_dir = (
        pp.user_extensions_dir if scope == "user" else pp.project_extensions_dir
    )
    slot_path = target_dir / target

    # Check the slot BEFORE touching the allowlist so a refusal leaves no
    # drift between yaml ("unloaded") and disk (real dir still present).
    if (
        slot_path.exists()
        and not slot_path.is_symlink()
        and slot_path.is_dir()
    ):
        raise click.ClickException(
            f"{slot_path} is not a symlink — refusing to delete. "
            "Run `agent-toolkit-cli doctor` for context."
        )

    try:
        remove_slug(allow_path, "pi_extensions", target)
    except FileNotFoundError:
        pass

    if slot_path.is_symlink():
        slot_path.unlink()
    # Else: nothing on disk → no-op (allowlist entry already removed).
