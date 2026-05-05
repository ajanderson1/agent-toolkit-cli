"""Doctor: symlink-integrity group — per-harness link health."""
from __future__ import annotations

import os
from pathlib import Path

from agent_toolkit._support import _USER_TARGETS
from agent_toolkit.commands._link_lib import _translated_slot_filename
from agent_toolkit.doctor.result import GroupResult, Status
from agent_toolkit.walker import discover_assets, extract_frontmatter, frontmatter_path

# Strip the "{home}/" template prefix to get a relative path under $HOME,
# matching this module's existing convention of joining with `home / rel`.
_USER_PATHS: dict[tuple[str, str], str] = {
    pair: tmpl.removeprefix("{home}/")
    for pair, tmpl in _USER_TARGETS.items()
}


def run(toolkit_root: Path, *, harness: str = "claude") -> GroupResult:
    home = Path(os.environ.get("HOME", str(Path.home())))

    findings: list[str] = []
    warns: list[str] = []

    expected: dict[tuple[str, str], Path] = {}
    for asset in discover_assets(toolkit_root):
        meta = _meta_for(asset)
        spec = meta.get("spec") or {}
        if harness not in (spec.get("harnesses") or []):
            continue
        rel = _USER_PATHS.get((harness, asset.kind))
        if rel is None:
            continue
        link_path = home / rel / _translated_slot_filename(asset.slug, asset.kind, harness)
        expected[(asset.kind, asset.slug)] = link_path

    for (kind, slug), link_path in expected.items():
        if not link_path.exists() and not link_path.is_symlink():
            warns.append(f"{kind}/{slug}: expected symlink {link_path} missing")
            continue
        if link_path.is_symlink():
            target = Path(os.readlink(link_path))
            if not target.is_absolute():
                target = (link_path.parent / target).resolve()
            if not target.exists():
                warns.append(f"{kind}/{slug}: dangling symlink → {target}")
            else:
                findings.append(f"{kind}/{slug}: linked")

    # Stale: a symlink under user dir that points into the repo for an asset that
    # does NOT declare this harness.
    declared_slugs = {(a.kind, a.slug): a for a in discover_assets(toolkit_root)}
    for (kind_dir_name, kind) in [
        ("skills", "skill"), ("agents", "agent"), ("commands", "command"),
        ("hooks", "hook"), ("plugins", "plugin"), ("extensions", "pi-extension"),
    ]:
        rel = _USER_PATHS.get((harness, kind))
        if rel is None:
            continue
        user_kind_dir = home / rel
        if not user_kind_dir.is_dir():
            continue
        for entry in user_kind_dir.iterdir():
            if not entry.is_symlink():
                continue
            target = Path(os.readlink(entry))
            if not target.is_absolute():
                target = (entry.parent / target).resolve()
            try:
                target.relative_to(toolkit_root)
            except ValueError:
                continue
            asset = declared_slugs.get((kind, entry.name))
            if asset is None:
                if not target.exists():
                    warns.append(
                        f"{kind}/{entry.name}: dangling symlink → {target} (no asset in repo)"
                    )
                else:
                    warns.append(f"{kind}/{entry.name}: stale link (no asset in repo)")
                continue
            meta = _meta_for(asset)
            spec = meta.get("spec") or {}
            if harness not in (spec.get("harnesses") or []):
                warns.append(
                    f"{kind}/{entry.name}: linked but {harness} not in spec.harnesses"
                )

    if warns:
        return GroupResult(
            name="symlink-integrity",
            status=Status.WARN,
            summary=f"{len(warns)} symlink issue(s) for harness={harness}",
            findings=findings + warns,
            fix_hint=f"`agent-toolkit link user {harness}` to reconcile",
        )
    return GroupResult(
        name="symlink-integrity",
        status=Status.OK,
        summary=f"{len(findings)} link(s) all healthy for harness={harness}",
        findings=findings,
    )


def _meta_for(asset) -> dict:
    if asset.kind in {"skill", "agent", "command"}:
        return extract_frontmatter(asset.path) or {}
    if asset.kind == "hook":
        import yaml
        return yaml.safe_load(asset.path.read_text()) or {}
    if asset.kind == "plugin":
        import json
        doc = json.loads(asset.path.read_text())
        return doc.get("agent_toolkit") or {}
    if asset.kind == "mcp":
        fm = frontmatter_path(asset.path, asset.kind)
        if not fm.is_file():
            return {}
        return extract_frontmatter(fm) or {}
    return {}
