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
from agent_toolkit._requires import RequiresUnsatisfied, parse_requires_entries
from agent_toolkit._support import (
    ALL_HARNESSES,
    UnsupportedPair,
    _PROJECT_TARGETS,
    _USER_TARGETS,
    is_supported,
)
from agent_toolkit._translators import TRANSLATORS
from agent_toolkit.walker import (
    Asset, AssetRecord, discover_assets, extract_frontmatter,
    frontmatter_path, load_asset_record, strip_frontmatter,
)

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


CACHE_DIR_NAME = ".agent-toolkit-cache"


def _scope_cache_root(harness: str, scope: str, project_root: Path) -> Path:
    """Return the per-scope cache root for a harness.

    user scope:    $HOME/<harness-home>/<CACHE_DIR_NAME>/
    project scope: <project_root>/<harness-home>/<CACHE_DIR_NAME>/

    The harness-home for opencode differs between scopes:
      - user:    .config/opencode/
      - project: .opencode/
    Mirrors the path conventions in _support.py (_USER_TARGETS / _PROJECT_TARGETS).
    """
    if harness != "opencode":
        # No other harness has a translate cell yet; defensively raise.
        raise ValueError(f"no cache layout defined for harness {harness!r}")
    if scope == "user":
        home = Path(os.environ.get("HOME", ""))
        return home / ".config" / "opencode" / CACHE_DIR_NAME
    return project_root / ".opencode" / CACHE_DIR_NAME


def _translated_slot_filename(slug: str, kind: str, harness: str) -> str:
    """Return the filename used for the slot symlink in this (harness, kind).

    OpenCode requires `.md` extension on agent and command slot files; Claude
    does not. Today only opencode has translate cells, so this is `<slug>.md`."""
    if harness == "opencode" and kind in {"agent", "command"}:
        return f"{slug}.md"
    return slug


def _render_to_cache(
    *,
    harness: str,
    kind: str,
    slug: str,
    asset_path: Path,
    scope: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[Path, bytes]:
    """Render translated bytes for an asset and return the (cache_path, bytes).

    In dry_run, computes bytes in-memory and returns the would-be cache path
    without writing. Out of dry_run, writes the bytes atomically (tmp+rename),
    creating parent directories as needed.

    Raises if `(harness, kind)` has no translator.
    """
    translator = TRANSLATORS.get((harness, kind))
    if translator is None:
        raise RuntimeError(
            f"no translator registered for ({harness!r}, {kind!r}) — "
            "_render_to_cache should not be called for non-translated cells"
        )
    record = load_asset_record(Asset(kind=kind, slug=slug, path=asset_path))
    text = asset_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    body = strip_frontmatter(text)
    rendered = translator(record, body)

    cache_dir = _scope_cache_root(harness, scope, project_root) / kind
    cache_path = cache_dir / f"{slug}.md"
    if not dry_run:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        tmp.write_bytes(rendered)
        tmp.replace(cache_path)
    return cache_path, rendered


def _relative_to_toolkit(asset_path: Path, toolkit_root: Path) -> str:
    """Best-effort relative path for dry-run output. Falls back to absolute."""
    try:
        return str(asset_path.resolve().relative_to(toolkit_root.resolve()))
    except (ValueError, OSError):
        return str(asset_path)


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
    For mcp, reads markdown frontmatter from sibling README.md.
    For plugin (JSON manifest), reads the agent_toolkit block.
    Falls back to markdown-frontmatter when kind is unknown (legacy callers).
    """
    fm: dict | None
    if kind in {"hook", "pi-extension"}:
        import yaml as _yaml
        fm = _yaml.safe_load(asset_path.read_text()) or {}
    elif kind == "plugin":
        import json as _json
        doc = _json.loads(asset_path.read_text())
        fm = doc.get("agent_toolkit") or {}
    elif kind == "mcp" or asset_path.name == "config.json":
        fm_path = frontmatter_path(asset_path, "mcp")
        fm = (extract_frontmatter(fm_path) if fm_path.is_file() else None) or {}
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
    scope: str = "user",
    project_root: Path | None = None,
) -> None:
    """Create/replace/skip a symlink for one asset; update counters.

    For (harness, kind) pairs in TRANSLATORS, render to a per-scope cache
    file and point the slot symlink at the cache. Otherwise symlink the
    slot directly to the asset source.
    """
    if not is_supported(harness, kind):
        raise UnsupportedPair(harness, kind)

    declared = _asset_harnesses(asset_path, kind)
    is_translated = (harness, kind) in TRANSLATORS

    # Translated cells need a project_root to resolve project-scope cache paths.
    # The user-scope path doesn't actually consult project_root, but we accept
    # the default cwd here for the rare in-the-wild caller that omits it. Keep
    # this resolution at function entry so the behaviour is visible at a glance.
    if is_translated and project_root is None:
        project_root = Path.cwd()

    slot_filename = _translated_slot_filename(slug, kind, harness) if is_translated else slug
    link_path = target_dir / slot_filename

    if harness not in declared:
        if link_path.is_symlink():
            if dry_run:
                print(f"would-unlink: {link_path}", file=stdout)
                counters.would_unlink += 1
            else:
                link_path.unlink()
                counters.removed += 1
        return

    if is_translated:
        cache_path, rendered = _render_to_cache(
            harness=harness, kind=kind, slug=slug,
            asset_path=asset_path, scope=scope,
            project_root=project_root, dry_run=dry_run,
        )
        source_path = cache_path
        # Cache-staleness rule: if the cache exists and its bytes match the
        # rendered output, AND the slot symlink already points at the cache,
        # this is unchanged. Any drift counts as updated.
        cache_in_sync = cache_path.is_file() and cache_path.read_bytes() == rendered
        slot_correct = link_path.is_symlink() and Path(os.readlink(link_path)) == cache_path
        if slot_correct and cache_in_sync:
            counters.unchanged += 1
            return
        if dry_run:
            rel_asset = _relative_to_toolkit(asset_path, toolkit_root)
            print(
                f"would-link: {link_path} -> {cache_path} (translated from {rel_asset})",
                file=stdout,
            )
            counters.would_link += 1
            return
    else:
        source_path = _expected_source(asset_path, kind)
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
    previous_allowed: dict[str, list[str]] | None = None,
    enforce_requires: bool = False,
) -> None:
    """Walk every asset kind. Project allow-listed slugs, prune the rest.

    `previous_allowed` is an optional snapshot of the allow-list BEFORE this
    dispatch's mutation (for link/unlink). Used to compute the
    `previously_allowed` set passed to MCP adapters so they know which on-disk
    entries fall under our ownership. None means "use current allow-list as
    previous" — appropriate for --all snapshot or fix-style callers.

    When `enforce_requires` is True, raises RequiresUnsatisfied if an
    allow-listed asset declares spec.requires peers for `harness` that are not
    themselves in the allowlist.  Callers in link.py set this to True; unlink
    callers leave it False so removal is never blocked.
    """
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
            mcp_allowed_slugs = list(allowed.get(section, []))

            from agent_toolkit.commands._mcp_dispatch import (  # noqa: PLC0415
                _build_mcp_entries, apply_link,
            )
            from agent_toolkit.harness_adapters import get_adapter  # noqa: PLC0415
            from agent_toolkit.harness_adapters.base import (  # noqa: PLC0415
                CannotInstall, UnimplementedAdapter,
            )

            adapter = get_adapter(harness)
            if isinstance(adapter, UnimplementedAdapter):
                # Loud skip: only print if the user has anything allow-listed
                # for this harness — otherwise stay quiet.
                if mcp_allowed_slugs:
                    print(adapter.skip_message(), file=stdout)
                continue

            # Compute previously_allowed: explicit snapshot if provided,
            # otherwise fall back to current (= no deletions for adapters
            # whose allow-list hasn't changed in this dispatch).
            if previous_allowed is not None:
                prev_mcps = set(previous_allowed.get(section) or [])
            else:
                prev_mcps = set(mcp_allowed_slugs)

            entries = _build_mcp_entries(toolkit_root, mcp_allowed_slugs)
            try:
                apply_link(
                    adapter,
                    scope=scope,
                    project_root=project_root,
                    entries=entries,
                    dry_run=dry_run,
                    stdout=stdout,
                    previously_allowed=prev_mcps,
                )
            except CannotInstall as exc:
                # Per-entry refusal: print a warning and continue with siblings.
                print(f"warning: {exc}", file=stdout)
                continue
            continue
        if not is_supported(harness, kind):
            # Boundary: caller asked for a harness/kind pair we have no slot
            # for. Silent-skip is wrong (#30) but non-MCP kinds reach here
            # from a discovery loop, not user input — we honour the filter
            # rather than raise. Direct entrypoints (maybe_link) raise.
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            raise RuntimeError(
                f"is_supported({harness!r}, {kind!r}) is True but "
                f"harness_target_dir returned None — SSOT invariant broken"
            )
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        section = kind_to_section(kind)
        allowed_slugs = set(allowed.get(section, []))
        discovered_slugs: set[str] = set()
        for asset in by_kind[kind]:
            discovered_slugs.add(asset.slug)
            if asset.slug in allowed_slugs:
                if enforce_requires:
                    record = load_asset_record(asset)
                    _check_requires(record, harness, scope, allowed)
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
                    scope=scope,
                    project_root=project_root,
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


def _check_requires(
    record: AssetRecord,
    harness: str,
    scope: str,
    allowed: dict[str, list[str]],
) -> None:
    """Raise RequiresUnsatisfied if spec.requires peers for `harness` are absent.

    Called only when `enforce_requires=True` is set on project_from_file.
    Raises rather than calling ctx.exit so the projection loop stays pure;
    link.py callers catch the exception and call ctx.exit(2).
    """
    peers_raw = record.requires.get(harness) or []
    if not peers_raw:
        return

    missing: list[tuple[str, str]] = []
    for peer_kind, peer_slug in parse_requires_entries(peers_raw):
        if not peer_kind:
            missing.append(("", peer_slug))
            continue
        try:
            section = kind_to_section(peer_kind)
        except ValueError:
            missing.append((peer_kind, peer_slug))
            continue
        if peer_slug not in set(allowed.get(section) or []):
            missing.append((peer_kind, peer_slug))

    if missing:
        raise RequiresUnsatisfied(
            asset_slug=record.asset.slug,
            asset_kind=record.asset.kind,
            harness=harness,
            missing=missing,
        )


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
