"""Render-from-frontmatter library for the `inventory` subcommand."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from agent_toolkit_cli.walker import AssetRecord, discover_assets, load_asset_record

_LIFECYCLE_ORDER = {"stable": 0, "experimental": 1, "deprecated": 2}
_KIND_ORDER = ("skill", "agent", "command", "hook", "mcp", "plugin", "pi-extension")


@dataclass(frozen=True)
class InventoryEntry:
    slug: str
    kind: str
    lifecycle: str
    origin: str
    harnesses: tuple[str, ...]
    location: str  # relative to repo root
    keywords: tuple[str, ...]
    description: str
    body_excerpt: str

    @classmethod
    def from_record(cls, record: AssetRecord, toolkit_root: Path) -> "InventoryEntry":
        meta = record.metadata.get("metadata") or {}
        spec = record.metadata.get("spec") or {}
        harnesses = tuple(spec.get("harnesses") or ())
        keywords = tuple(meta.get("keywords") or ())
        return cls(
            slug=record.asset.slug,
            kind=record.asset.kind,
            lifecycle=meta.get("lifecycle") or "experimental",
            origin=spec.get("origin") or "first-party",
            harnesses=harnesses,
            location=str(record.asset.path.relative_to(toolkit_root)),
            keywords=keywords,
            description=meta.get("description") or "",
            body_excerpt=record.body_excerpt,
        )


def collect_entries(toolkit_root: Path) -> list[InventoryEntry]:
    return [
        InventoryEntry.from_record(load_asset_record(a), toolkit_root)
        for a in discover_assets(toolkit_root)
    ]


def render_inventory(
    toolkit_root: Path,
    *,
    fmt: str = "md",
    kind: str | None = None,
    harness: str | None = None,
    origin: str | None = None,
    lifecycle: str | None = None,
) -> str:
    entries = collect_entries(toolkit_root)
    entries = _apply_filters(entries, kind=kind, harness=harness, origin=origin, lifecycle=lifecycle)
    if fmt == "json":
        return json.dumps([_entry_to_dict(e) for e in entries], indent=2)
    return _render_md(entries)


def render_asset_card(toolkit_root: Path, *, slug: str) -> str:
    for entry in collect_entries(toolkit_root):
        if entry.slug == slug:
            return _render_card(entry)
    raise KeyError(slug)


def _apply_filters(
    entries: Iterable[InventoryEntry],
    *,
    kind: str | None,
    harness: str | None,
    origin: str | None,
    lifecycle: str | None,
) -> list[InventoryEntry]:
    out: list[InventoryEntry] = []
    for e in entries:
        if kind and e.kind != kind:
            continue
        if harness and harness not in e.harnesses:
            continue
        if origin and e.origin != origin:
            continue
        if lifecycle and e.lifecycle != lifecycle:
            continue
        out.append(e)
    return out


def _entry_to_dict(e: InventoryEntry) -> dict:
    return {
        "slug": e.slug,
        "kind": e.kind,
        "lifecycle": e.lifecycle,
        "origin": e.origin,
        "harnesses": list(e.harnesses),
        "location": e.location,
        "keywords": list(e.keywords),
        "description": e.description,
        "body_excerpt": e.body_excerpt,
    }


def _render_md(entries: list[InventoryEntry]) -> str:
    if not entries:
        return "(no assets matched)\n"
    grouped: dict[str, list[InventoryEntry]] = {k: [] for k in _KIND_ORDER}
    for e in entries:
        grouped.setdefault(e.kind, []).append(e)
    # Iterate known kinds first, then any unknown kinds in insertion order, so
    # an unexpected kind appears in the output rather than being silently dropped.
    ordered_kinds = list(_KIND_ORDER) + [k for k in grouped if k not in _KIND_ORDER]
    parts: list[str] = []
    for k in ordered_kinds:
        bucket = grouped.get(k) or []
        if not bucket:
            continue
        bucket.sort(key=lambda x: (_LIFECYCLE_ORDER.get(x.lifecycle, 99), x.slug))
        parts.append(f"## {k}s")
        parts.append("")
        for e in bucket:
            parts.append(_render_card(e))
            parts.append("")
    return "\n".join(parts)


def _render_card(e: InventoryEntry) -> str:
    desc = e.description or "(no description)"
    long_desc = f"{desc}\n    {e.body_excerpt}" if e.body_excerpt else desc
    keywords = ", ".join(e.keywords) if e.keywords else "(none)"
    harnesses = ", ".join(e.harnesses) if e.harnesses else "(none)"
    return (
        "NAME\n"
        f"    {e.slug} — {desc}\n"
        "\n"
        f"KIND        {e.kind}\n"
        f"LIFECYCLE   {e.lifecycle}\n"
        f"ORIGIN      {e.origin}\n"
        f"HARNESSES   {harnesses}\n"
        f"LOCATION    {e.location}\n"
        f"KEYWORDS    {keywords}\n"
        "\n"
        "DESCRIPTION\n"
        f"    {long_desc}\n"
        "\n"
        "QUICKSTART — link this asset\n"
        + _quickstart_for(e)
    )


def _quickstart_for(e: InventoryEntry) -> str:
    if not e.harnesses:
        return "    (no compatible harnesses declared)\n"
    lines: list[str] = []
    primary = e.harnesses[0]
    lines.append(f"    User scope:    agent-toolkit link user {primary} {e.kind}:{e.slug}")
    lines.append(f"    Project scope: agent-toolkit link project {primary} {e.kind}:{e.slug}")
    if len(e.harnesses) > 1:
        others = ", ".join(e.harnesses[1:])
        lines.append(f"    Other harnesses supported: {others}")
    return "\n".join(lines) + "\n"
