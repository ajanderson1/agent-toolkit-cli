"""Doctor: duplicates group — flag (kind, slug) collisions across the asset tree.

Two assets sharing the same (kind, slug) make `link`/`unlink` ambiguous and
cause ghost rows in the TUI. The walker is order-stable but does not dedup,
so this check surfaces the SSOT-side data drift the consumer can't fix.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from agent_toolkit.doctor.result import GroupResult, Status
from agent_toolkit.walker import discover_assets


def run(toolkit_root: Path) -> GroupResult:
    by_key: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for asset in discover_assets(toolkit_root):
        by_key[(asset.kind, asset.slug)].append(asset.path)

    asset_count = sum(len(paths) for paths in by_key.values())
    dupes = {k: paths for k, paths in by_key.items() if len(paths) > 1}

    if not dupes:
        return GroupResult(
            name="duplicates",
            status=Status.OK,
            summary=f"{asset_count} asset(s), no duplicate (kind, slug) pairs",
            findings=[f"{len(by_key)} unique (kind, slug) pair(s)"],
        )

    findings: list[str] = []
    for (kind, slug), paths in sorted(dupes.items()):
        rels = sorted(str(p.relative_to(toolkit_root)) for p in paths)
        findings.append(f"{kind}:{slug} appears {len(paths)}x: {', '.join(rels)}")

    return GroupResult(
        name="duplicates",
        status=Status.FAIL,
        summary=f"{len(dupes)} duplicate (kind, slug) pair(s) across {asset_count} asset(s)",
        findings=findings,
        fix_hint="dedupe in the toolkit repo: pick one canonical path per slug, "
                 "or rename slugs so they don't collide",
    )
