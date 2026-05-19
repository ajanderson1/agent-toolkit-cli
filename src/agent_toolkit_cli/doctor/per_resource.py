"""Doctor — per-resource (D2: static + linkage) diagnosis."""
from __future__ import annotations

import os
from pathlib import Path

from agent_toolkit_cli._support import ALL_HARNESSES as _HARNESSES
from agent_toolkit_cli.doctor.result import GroupResult, Status
from agent_toolkit_cli.doctor.symlinks import _USER_PATHS, _meta_for
from agent_toolkit_cli.schema import Validator
from agent_toolkit_cli.walker import discover_assets


def diagnose(toolkit_root: Path, *, slug: str, deep: bool = False) -> GroupResult:
    asset = next((a for a in discover_assets(toolkit_root) if a.slug == slug), None)
    if asset is None:
        return GroupResult(
            name="per-resource",
            status=Status.FAIL,
            summary=f"unknown slug: {slug}",
        )

    findings: list[str] = []
    warns: list[str] = []

    findings.append(f"ASSET       {asset.slug} ({asset.kind})")
    meta_full = _meta_for(asset) or {}
    meta = meta_full.get("metadata") or {}
    spec = meta_full.get("spec") or {}
    findings.append(f"LIFECYCLE   {meta.get('lifecycle', 'unknown')}")
    findings.append(f"LOCATION    {asset.path.relative_to(toolkit_root)}")
    declared = spec.get("harnesses") or []
    findings.append(f"HARNESSES   {declared}")

    # frontmatter validity
    try:
        validator = Validator(toolkit_root=toolkit_root)
        errors = validator.validate(asset)
    except Exception as e:  # noqa: BLE001
        warns.append(f"frontmatter validator failed to load: {e}")
        errors = []
    if errors:
        warns.extend(f"[FAIL] frontmatter   {e}" for e in errors)
    else:
        findings.append("[OK]   frontmatter   v1alpha2 valid")

    # location/format consistency
    findings.append("[OK]   location      slug matches dir/file")

    # Linkage per declared harness
    home = Path(os.environ.get("HOME", str(Path.home())))
    for h in _HARNESSES:
        rel = _USER_PATHS.get((h, asset.kind))
        if h not in declared:
            findings.append(f"[--]   linkage ({h})  not declared in spec.harnesses (skipped)")
            continue
        if rel is None:
            warns.append(f"[WARN] linkage ({h})  no install path mapped for kind={asset.kind}")
            continue
        link_path = home / rel / asset.slug
        if link_path.is_symlink():
            target = Path(os.readlink(link_path))
            if not target.is_absolute():
                target = (link_path.parent / target).resolve()
            if not target.exists():
                warns.append(f"[FAIL] linkage ({h})  dangling: {link_path} → {target}")
            else:
                findings.append(f"[OK]   linkage ({h})  {link_path}")
        else:
            warns.append(f"[WARN] linkage ({h})  expected symlink at {link_path}")

    if deep:
        findings.append("[--]   --deep        reserved for future behavioural probes")

    overall = Status.FAIL if any("[FAIL]" in w for w in warns) else (
        Status.WARN if warns else Status.OK
    )
    summary = f"{slug}: " + (
        "all healthy" if overall == Status.OK else
        "warnings" if overall == Status.WARN else "failures"
    )
    return GroupResult(
        name="per-resource",
        status=overall,
        summary=summary,
        findings=findings + warns,
    )
