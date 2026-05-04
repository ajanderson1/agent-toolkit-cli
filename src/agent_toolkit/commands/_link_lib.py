"""Pure helpers for link/unlink/diff subcommands.

No Click, no I/O orchestration — just projection algorithm, action counting,
output-string formatters, and the plan-mode line iterator. Each function is
unit-tested in tests/test_link_lib.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator

import click

from agent_toolkit._allowlist import kind_to_section, read_allowlist
from agent_toolkit.commands._list_json import _PROJECT_TARGETS, _USER_TARGETS
from agent_toolkit.walker import Asset, discover_assets, extract_frontmatter

ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")

HARNESS_HOMES: dict[str, str] = {
    "claude":   ".claude",
    "codex":    ".codex",
    "opencode": ".opencode",
    "pi":       ".pi",
}


def validate_harness(ctx: click.Context, harness: str) -> None:
    """Exit 2 with a clean error if `harness` is not one of ALL_HARNESSES."""
    if harness not in ALL_HARNESSES:
        click.echo(
            f"unknown harness '{harness}' — expected one of: "
            + " ".join(ALL_HARNESSES),
            err=True,
        )
        ctx.exit(2)


def harness_home_path(harness: str, home: Path | None = None) -> Path:
    """Return the absolute path to a harness's home directory under $HOME."""
    h = home if home is not None else Path(os.environ.get("HOME", ""))
    return h / HARNESS_HOMES[harness]


@dataclass
class LinkCounters:
    created: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    would_link: int = 0
    would_unlink: int = 0


def format_summary(c: LinkCounters, dry_run: bool) -> str:
    if dry_run:
        total = c.would_link + c.would_unlink
        if total == 0:
            return "Nothing to change."
        return (
            f"{total} changes pending ({c.would_link} to link, "
            f"{c.would_unlink} to remove). Re-run without --dry-run to apply."
        )
    changed = c.created + c.updated + c.removed
    if changed == 0:
        return f"Already in sync — {c.unchanged} assets linked, nothing to change."
    return (
        f"Linked {c.created} new, updated {c.updated}, removed "
        f"{c.removed} stale ({c.unchanged} already in sync)."
    )


MALFORMED = "__malformed__"


def iter_plan_lines(text: str) -> Iterator[tuple[str, str]]:
    """Yield (kind, slug) pairs from --plan stdin text.

    - Strips `#`-comments (anything from `#` to end-of-line).
    - Skips blank-after-strip lines.
    - For lines without a colon, yields (MALFORMED, raw_line) — the original
      pre-strip line, so callers can render the user's input verbatim in
      diagnostics. Caller should not re-parse it.
    """
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            yield (MALFORMED, raw)
            continue
        kind, _, slug = line.partition(":")
        yield (kind.strip(), slug.strip())


KINDS_FOR_PROJECTION: tuple[str, ...] = ("skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension")


def harness_target_dir(harness: str, kind: str, scope: str, project_root: Path) -> Path | None:
    """Mirror of bash harness_target_dir / project_target_dir."""
    if scope == "user":
        tmpl = _USER_TARGETS.get((harness, kind))
        if not tmpl:
            return None
        home = os.environ.get("HOME", "")
        return Path(tmpl.format(home=home))
    rel = _PROJECT_TARGETS.get((harness, kind))
    return (project_root / rel) if rel else None


def _expected_source(asset_path: Path, kind: str) -> Path:
    if kind in {"skill", "mcp", "plugin", "pi-extension"}:
        return asset_path.parent
    return asset_path


def _asset_harnesses(asset_path: Path, kind: str | None = None) -> list[str]:
    """Return spec.harnesses declared by the asset.

    For markdown-frontmatter kinds (skill/agent/command), parses `---` frontmatter.
    For pure-YAML kinds (hook/pi-extension), parses the whole file.
    For JSON manifest kinds (mcp/plugin), reads the agent_toolkit block.
    Falls back to markdown-frontmatter when kind is unknown (legacy callers).
    """
    fm: dict | None
    if kind in {"hook", "pi-extension"}:
        import yaml as _yaml
        fm = _yaml.safe_load(asset_path.read_text()) or {}
    elif kind in {"mcp", "plugin"}:
        import json as _json
        doc = _json.loads(asset_path.read_text())
        fm = doc.get("agent_toolkit") or {}
    else:
        fm = extract_frontmatter(asset_path) or {}
    spec = (fm or {}).get("spec") or {}
    return list(spec.get("harnesses") or [])


def maybe_link(
    *,
    harness: str,
    kind: str,
    slug: str,
    asset_path: Path,
    target_dir: Path,
    toolkit_root: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout: IO[str],
) -> None:
    """Create/replace/skip a symlink for one asset; update counters.

    Direct port of bash _maybe_link in bin/lib/link.sh:430.
    """
    source_path = _expected_source(asset_path, kind)
    link_path = target_dir / slug
    declared = _asset_harnesses(asset_path, kind)
    if harness not in declared:
        if link_path.is_symlink():
            if dry_run:
                print(f"would-unlink: {link_path}", file=stdout)
                counters.would_unlink += 1
            else:
                link_path.unlink()
                counters.removed += 1
        return

    if link_path.is_symlink() and Path(os.readlink(link_path)) == source_path:
        counters.unchanged += 1
        return

    if dry_run:
        print(f"would-link: {link_path} -> {source_path}", file=stdout)
        counters.would_link += 1
        return

    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
        counters.updated += 1
    else:
        counters.created += 1
    link_path.symlink_to(source_path)


def project_from_file(
    *,
    scope: str,
    harness: str,
    toolkit_root: Path,
    project_root: Path,
    allowlist_path: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout: IO[str],
) -> None:
    """Walk every asset kind. Project allow-listed slugs, prune the rest."""
    allowed = read_allowlist(allowlist_path)
    by_kind: dict[str, list[Asset]] = {
        k: [] for k in KINDS_FOR_PROJECTION if k != "mcp"
    }
    for asset in discover_assets(toolkit_root):
        if asset.kind in by_kind:
            by_kind[asset.kind].append(asset)

    for kind in KINDS_FOR_PROJECTION:
        if kind == "mcp":
            section = kind_to_section(kind)
            allowed_slugs = list(allowed.get(section, []))
            if not allowed_slugs:
                continue
            slugs_csv = ", ".join(allowed_slugs)
            print(
                f"MCP install path for {harness} not yet implemented; "
                f"allow-list updated only ({slugs_csv}).",
                file=stdout,
            )
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            continue
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        section = kind_to_section(kind)
        allowed_slugs = set(allowed.get(section, []))
        discovered_slugs: set[str] = set()
        for asset in by_kind[kind]:
            discovered_slugs.add(asset.slug)
            if asset.slug in allowed_slugs:
                maybe_link(
                    harness=harness,
                    kind=kind,
                    slug=asset.slug,
                    asset_path=asset.path,
                    target_dir=target_dir,
                    toolkit_root=toolkit_root,
                    dry_run=dry_run,
                    counters=counters,
                    stdout=stdout,
                )
            else:
                _prune_if_into_repo(
                    target_dir / asset.slug, toolkit_root, dry_run, counters, stdout,
                )
        # Sweep orphan symlinks (slug in target dir but no asset in repo)
        if target_dir.is_dir():
            for entry in target_dir.iterdir():
                if not entry.is_symlink():
                    continue
                if entry.name in discovered_slugs:
                    continue
                _prune_if_into_repo(entry, toolkit_root, dry_run, counters, stdout)


def _prune_if_into_repo(
    link_path: Path,
    toolkit_root: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout: IO[str],
) -> None:
    if not link_path.is_symlink():
        return
    target = os.readlink(link_path)
    try:
        Path(target).resolve().relative_to(toolkit_root.resolve())
    except (ValueError, FileNotFoundError, OSError):
        return
    if dry_run:
        print(f"would-unlink: {link_path}", file=stdout)
        counters.would_unlink += 1
    else:
        link_path.unlink()
        counters.removed += 1
