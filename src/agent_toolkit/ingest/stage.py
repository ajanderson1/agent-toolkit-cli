"""Ingest stage 4 — STAGE: write to .agent-toolkit/staging/<slug>/."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from agent_toolkit.ingest.types import Proposal


def staging_root(repo_root: Path) -> Path:
    return repo_root / ".agent-toolkit" / "staging"


def stage_proposal(*, repo_root: Path, proposal: Proposal, snapshot_dir: Path) -> Path:
    """Copy snapshot_dir contents into the staging dir + write STAGE.md."""
    target = staging_root(repo_root) / proposal.slug
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for entry in snapshot_dir.iterdir():
        dest = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dest)
        else:
            shutil.copy2(entry, dest)

    _write_stage_md(target / "STAGE.md", proposal=proposal)
    _write_proposed_frontmatter(target / "PROPOSED_FRONTMATTER.yaml", proposal=proposal)
    return target


def abort_staging(*, repo_root: Path, slug: str) -> None:
    target = staging_root(repo_root) / slug
    if target.exists():
        shutil.rmtree(target)


def list_staging(repo_root: Path) -> list[str]:
    root = staging_root(repo_root)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def _write_stage_md(path: Path, *, proposal: Proposal) -> None:
    body = (
        "# Staged ingest — {slug}\n\n"
        "## Proposal\n\n"
        "- **slug:** `{slug}`\n"
        "- **kind:** {kind}\n"
        "- **origin:** {origin}\n"
        "- **harnesses:** {harnesses}\n"
        "- **lifecycle:** {lifecycle}\n"
        "- **target path:** `{target_path}`\n"
        "- **vendor via:** {vendor_via}\n"
        "- **upstream:** {upstream}\n"
        "- **fork:** {fork}\n"
    ).format(
        slug=proposal.slug,
        kind=proposal.kind,
        origin=proposal.origin,
        harnesses=", ".join(proposal.harnesses),
        lifecycle=proposal.lifecycle,
        target_path=proposal.target_path,
        vendor_via=proposal.vendor_via,
        upstream=proposal.upstream or "(none)",
        fork=proposal.fork or "(none)",
    )
    path.write_text(body)


def _write_proposed_frontmatter(path: Path, *, proposal: Proposal) -> None:
    payload = proposal.to_dict()
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
