"""Doctor: allowlist-audit group — slug-existence + cross-toolkit symlinks.

Two checks the existing `symlinks` group does not cover:

1. Allow-list slug existence — entries in user/project .agent-toolkit.yaml
   that name slugs not present in the toolkit repo are flagged as drift.
2. Cross-toolkit symlinks — symlinks under ~/.{harness}/... that point into
   a *different* toolkit repo (recognised by the .agent-toolkit-source
   marker) are flagged.

Broken-target detection stays in the `symlinks` group.
"""
from __future__ import annotations

import os
from pathlib import Path

from agent_toolkit._allowlist import read_allowlist, section_to_kind
from agent_toolkit._support import _USER_TARGETS
from agent_toolkit.doctor.result import GroupResult, Status
from agent_toolkit.walker import discover_assets


def _toolkit_root_for(p: Path) -> Path | None:
    """Return the toolkit root containing p (recognised by .agent-toolkit-source), or None."""
    cur = p.resolve()
    for ancestor in [cur, *cur.parents]:
        if (ancestor / ".agent-toolkit-source").is_file():
            return ancestor
    return None


def _check_allowlist(
    yaml_path: Path, source_label: str, declared_slugs: set[tuple[str, str]]
) -> list[str]:
    warns: list[str] = []
    if not yaml_path.is_file():
        return warns
    parsed = read_allowlist(yaml_path)
    for section, slugs in parsed.items():
        kind = section_to_kind(section)
        for slug in slugs:
            if (kind, slug) not in declared_slugs:
                warns.append(
                    f"allow-list {source_label} ({yaml_path}) references "
                    f"{kind}/{slug} which is not in the toolkit repo"
                )
    return warns


def _check_cross_toolkit_symlinks(toolkit_root: Path) -> list[str]:
    warns: list[str] = []
    home = Path(os.environ.get("HOME", str(Path.home())))
    seen_dirs: set[Path] = set()
    configured = toolkit_root.resolve()
    for (harness, _kind), tmpl in _USER_TARGETS.items():
        rel = tmpl.replace("{home}/", "")
        kind_dir = home / rel
        if kind_dir in seen_dirs or not kind_dir.is_dir():
            continue
        seen_dirs.add(kind_dir)
        for entry in kind_dir.iterdir():
            if not entry.is_symlink():
                continue
            target = Path(os.readlink(entry))
            if not target.is_absolute():
                target = (entry.parent / target).resolve()
            if not target.exists():
                continue  # symlinks group owns dangling-target detection
            tgt_root = _toolkit_root_for(target)
            if tgt_root is not None and tgt_root.resolve() != configured:
                warns.append(
                    f"{harness}/{entry.name}: symlink points into a different toolkit "
                    f"(target={target}, configured toolkit={toolkit_root})"
                )
    return warns


def run(toolkit_root: Path, *, project_root: Path | None = None) -> GroupResult:
    declared = {(a.kind, a.slug) for a in discover_assets(toolkit_root)}
    findings: list[str] = []
    warns: list[str] = []

    home = Path(os.environ.get("HOME", str(Path.home())))
    user_yaml = home / ".agent-toolkit.yaml"
    warns.extend(_check_allowlist(user_yaml, "user", declared))

    if project_root is not None:
        proj_yaml = project_root / ".agent-toolkit.yaml"
        if proj_yaml != user_yaml:
            warns.extend(_check_allowlist(proj_yaml, "project", declared))

    warns.extend(_check_cross_toolkit_symlinks(toolkit_root))

    if warns:
        return GroupResult(
            name="allowlist-audit",
            status=Status.WARN,
            summary=f"{len(warns)} drift issue(s)",
            findings=findings + warns,
            fix_hint="Edit ~/.agent-toolkit.yaml or re-link with the correct --toolkit-repo.",
        )

    findings.append(f"all allow-list entries resolve to assets in {toolkit_root}")
    findings.append("no cross-toolkit symlinks detected")
    return GroupResult(
        name="allowlist-audit",
        status=Status.OK,
        summary="allow-list and symlinks all reference current toolkit",
        findings=findings,
    )
