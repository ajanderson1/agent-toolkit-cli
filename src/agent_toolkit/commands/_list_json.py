"""Internal subcommand: emit list state as JSON for the TUI and other consumers.

Hidden from `--help` (mirrors `_yaml-edit`). Schema is documented in
`docs/agent-toolkit/cli.md` under the `--format=json` section.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import click

from agent_toolkit._allowlist import kind_to_section, read_allowlist
from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit.walker import discover_assets, load_asset_record

# Kept in lockstep with `_link_lib.ALL_HARNESSES` (defined there to avoid a
# circular import: `_link_lib` already imports `_USER_TARGETS`/`_PROJECT_TARGETS`
# from this module). If you add a harness, update both.
ALL_HARNESSES = ("claude", "codex", "opencode", "pi")
ALL_KINDS = ("skill", "agent", "command", "hook", "plugin", "pi-extension")  # mcp deliberately excluded

# Mirror of bin/lib/common.sh's harness_target_dir / project_target_dir.
# Kept in lockstep — if the bash table changes, this one MUST change too.
_USER_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       "{home}/.claude/skills",
    ("claude", "agent"):       "{home}/.claude/agents",
    ("claude", "command"):     "{home}/.claude/commands",
    ("claude", "hook"):        "{home}/.claude/hooks",
    ("claude", "plugin"):      "{home}/.claude/plugins",
    ("codex", "skill"):        "{home}/.codex/skills",
    ("opencode", "skill"):     "{home}/.config/opencode/skills",
    ("pi", "skill"):           "{home}/.pi/agent/skills",
    ("pi", "agent"):           "{home}/.pi/agent/agents",
    ("pi", "pi-extension"):    "{home}/.pi/agent/extensions",
}
_PROJECT_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       ".claude/skills",
    ("claude", "agent"):       ".claude/agents",
    ("claude", "command"):     ".claude/commands",
    ("claude", "hook"):        ".claude/hooks",
    ("claude", "plugin"):      ".claude/plugins",
    ("codex", "skill"):        ".codex/skills",
    ("opencode", "skill"):     ".opencode/skills",
    ("pi", "skill"):           ".pi/agent/skills",
    ("pi", "agent"):           ".pi/agent/agents",
    ("pi", "pi-extension"):    ".pi/agent/extensions",
}


def _slot_dir(harness: str, kind: str, scope: str, project_root: Path) -> Path | None:
    home = Path(os.environ.get("HOME", ""))
    if scope == "user":
        tmpl = _USER_TARGETS.get((harness, kind))
        return Path(tmpl.format(home=str(home))) if tmpl else None
    rel = _PROJECT_TARGETS.get((harness, kind))
    return (project_root / rel) if rel else None


def _expected_source(asset_path: Path, kind: str) -> Path:
    # Mirrors _maybe_link in bin/lib/link.sh.
    if kind in {"skill", "mcp", "plugin", "pi-extension"}:
        return asset_path.parent
    return asset_path


def _cell_status(
    harness: str,
    kind: str,
    slug: str,
    scope: str,
    expected_src: Path,
    toolkit_root_resolved: Path,
    project_root: Path,
) -> tuple[str, str | None]:
    slot = _slot_dir(harness, kind, scope, project_root)
    if slot is None:
        return ("unsupported", None)
    link_path = slot / slug
    if not link_path.is_symlink():
        return ("unlinked", None)
    target = os.readlink(str(link_path))
    target_path = Path(target)
    # Resolve a relative target against its parent symlink directory.
    if not target_path.is_absolute():
        target_path = (link_path.parent / target_path)
    # Resolve the target to its canonical form so prefix/equality checks line up
    # with `toolkit_root.resolve()` (e.g. `/tmp` → `/private/tmp` on macOS). If it
    # can't be resolved, the link points at something missing — treat as broken.
    try:
        resolved_target = target_path.resolve(strict=True)
    except (FileNotFoundError, RuntimeError, OSError):
        return ("broken", target)
    try:
        resolved_target.relative_to(toolkit_root_resolved)
        inside_repo = True
    except ValueError:
        inside_repo = False
    expected_resolved = expected_src.resolve() if expected_src.exists() else expected_src
    if not inside_repo or resolved_target != expected_resolved:
        return ("broken", target)
    # Emit the raw os.readlink string (same shape as the broken case) so
    # consumers see one consistent representation regardless of status.
    return ("linked", target)


def _build_inventory(
    toolkit_root: Path,
    project_root: Path,
    *,
    kind: str | None = None,
    harness: str | None = None,
) -> dict:
    """Pure data path: produce the inventory dict consumed by JSON output and `--report`.

    Sorts assets by (kind, slug) for stable, diffable output.
    """
    # Keep the user-facing `toolkit_root` string verbatim (e.g. `/tmp/...` not
    # `/private/tmp/...` on macOS) so callers comparing against their argv
    # see what they passed. Use a resolved copy internally for path checks.
    toolkit_root_resolved = toolkit_root.resolve()
    user_allow = read_allowlist(Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml")
    proj_allow = read_allowlist(project_root / ".agent-toolkit.yaml")

    assets_out: list[dict] = []
    for asset in discover_assets(toolkit_root):
        if asset.kind == "mcp":
            continue
        if kind and asset.kind != kind:
            continue
        record = load_asset_record(asset)
        meta = record.metadata or {}
        spec = meta.get("spec") or {}
        declared = list(spec.get("harnesses") or [])
        description = (
            (meta.get("metadata") or {}).get("description")
            or meta.get("description")
            or ""
        )
        origin = spec.get("origin") or "unknown"

        cells = []
        for h in ALL_HARNESSES:
            if harness and h != harness:
                continue
            section = kind_to_section(asset.kind)
            user_allowlisted = asset.slug in (user_allow.get(section) or [])
            proj_allowlisted = asset.slug in (proj_allow.get(section) or [])
            if h not in declared:
                cells.append({
                    "harness": h, "scope": "user",
                    "status": "unsupported", "target": None,
                    "allowlisted": user_allowlisted,
                })
                cells.append({
                    "harness": h, "scope": "project",
                    "status": "unsupported", "target": None,
                    "allowlisted": proj_allowlisted,
                })
                continue
            expected_src = _expected_source(asset.path, asset.kind)
            for scope, allowlisted in (
                ("user", user_allowlisted),
                ("project", proj_allowlisted),
            ):
                status, target = _cell_status(
                    h, asset.kind, asset.slug, scope, expected_src,
                    toolkit_root_resolved, project_root,
                )
                cells.append({
                    "harness": h, "scope": scope,
                    "status": status, "target": target,
                    "allowlisted": allowlisted,
                })

        assets_out.append({
            "kind": asset.kind,
            "slug": asset.slug,
            "origin": origin,
            "description": description,
            "path": str(asset.path),
            "declared_harnesses": declared,
            "cells": cells,
        })

    return {
        "toolkit_root": str(toolkit_root),
        "harnesses": list(ALL_HARNESSES),
        "assets": sorted(assets_out, key=lambda a: (a["kind"], a["slug"])),
    }


@click.command("_list-json", hidden=True)
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option(
    "--project",
    "project_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the consumer project (default: CWD).",
)
@click.option("--kind", type=click.Choice(ALL_KINDS), default=None)
@click.option("--harness", type=click.Choice(ALL_HARNESSES), default=None)
@click.pass_context
def list_json(
    ctx: click.Context,
    toolkit_root: Path | None,
    project_root: Path | None,
    kind: str | None,
    harness: str | None,
) -> None:
    """Emit list state as JSON. Hidden internal — consumed by `list --format=json`."""
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(explicit=None)
        except RepoNotFoundError as exc:
            raise click.ClickException(str(exc))
    else:
        toolkit_root = Path(toolkit_root)
    if project_root is None:
        project_root = Path(".").resolve()
    else:
        project_root = Path(project_root)

    out = _build_inventory(toolkit_root, project_root, kind=kind, harness=harness)
    click.echo(json.dumps(out, indent=2))
