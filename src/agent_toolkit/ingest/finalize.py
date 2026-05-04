"""Ingest stage 6 — FINALISE: move staging → canonical path, check, auto-commit."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_toolkit.ingest.stage import staging_root
from agent_toolkit.ingest.types import Proposal


def _git_env() -> dict[str, str]:
    # Strip GIT_* vars so a parent git invocation (hook, test runner, harness)
    # can't redirect this commit into the parent's index/worktree. cwd= alone
    # is not enough — GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE override it.
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@dataclass
class FinalizeResult:
    target_path: Path
    committed: bool
    commit_sha: str | None


class FinalizeError(RuntimeError):
    pass


def finalize(
    *,
    toolkit_root: Path,
    proposal: Proposal,
    security_overall: str = "GREEN",
    skip_check: bool = False,
    skip_commit: bool = False,
) -> FinalizeResult:
    staging_dir = staging_root(toolkit_root) / proposal.slug
    if not staging_dir.exists():
        raise FinalizeError(f"no staging dir at {staging_dir}")

    target = toolkit_root / proposal.target_path
    if target.exists():
        raise FinalizeError(f"target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    # Copy primary asset file from staging to target. For dir-shaped kinds
    # (skill/mcp/plugin), copy the whole directory; for single-file kinds, copy
    # the matching file.
    primary = _primary_in_staging(staging_dir, proposal.kind)
    if primary is None:
        raise FinalizeError(f"no recognisable {proposal.kind} payload in {staging_dir}")
    if proposal.kind in {"skill", "mcp", "plugin", "pi-extension"}:
        # Copy the directory containing the primary file (i.e., the staging dir's
        # contents — minus the staging metadata files) into target.parent.
        target_dir = target.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        for entry in staging_dir.iterdir():
            if entry.name in {"STAGE.md", "PROPOSED_FRONTMATTER.yaml"}:
                continue
            dest = target_dir / entry.name
            if entry.is_dir():
                shutil.copytree(entry, dest)
            else:
                shutil.copy2(entry, dest)
    else:
        shutil.copy2(primary, target)

    if proposal.vendor_via == "submodule" and proposal.upstream:
        _add_submodule(toolkit_root=toolkit_root, proposal=proposal)

    if not skip_check:
        result = subprocess.run(
            ["uv", "run", "agent-toolkit", "check", "--toolkit-repo", str(toolkit_root), "--exit-code"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FinalizeError(f"check failed:\n{result.stderr or result.stdout}")
        subprocess.run(
            ["uv", "run", "agent-toolkit", "fix", "--toolkit-repo", str(toolkit_root)],
            check=True,
        )

    # Clean up staging
    shutil.rmtree(staging_dir)

    commit_sha = None
    committed = False
    if not skip_commit:
        commit_sha = _auto_commit(toolkit_root=toolkit_root, proposal=proposal,
                                  security_overall=security_overall)
        committed = True

    return FinalizeResult(target_path=target, committed=committed, commit_sha=commit_sha)


def _primary_in_staging(staging_dir: Path, kind: str) -> Path | None:
    name = {
        "skill": "SKILL.md",
        "agent": None,           # any *.md
        "command": None,         # any *.md
        "hook": None,            # any *.meta.yaml
        "mcp": "mcp.json",
        "plugin": "marketplace.json",
        "pi-extension": "extension.meta.yaml",
    }.get(kind)
    if name:
        p = staging_dir / name
        return p if p.exists() else None
    if kind in {"agent", "command"}:
        for p in staging_dir.glob("*.md"):
            if p.name in {"STAGE.md", "README.md"}:
                continue
            return p
    if kind == "hook":
        for p in staging_dir.glob("*.meta.yaml"):
            return p
    return None


def _add_submodule(*, toolkit_root: Path, proposal: Proposal) -> None:
    subprocess.run(
        ["git", "submodule", "add", proposal.fork or proposal.upstream, proposal.target_path.split("/")[0] + "/" + proposal.slug],
        cwd=toolkit_root,
        check=True,
        env=_git_env(),
    )


def _auto_commit(*, toolkit_root: Path, proposal: Proposal, security_overall: str) -> str:
    msg = (
        f"chore(ingest): vendor {proposal.slug} as {proposal.kind} ({proposal.origin})\n"
        f"\n"
        f"Source: {proposal.upstream or '(local)'}\n"
        f"Harnesses: [{', '.join(proposal.harnesses)}]\n"
        f"Security review: {security_overall}\n"
        f"Vendor strategy: {proposal.vendor_via}\n"
    )
    env = _git_env()
    subprocess.run(["git", "add", "-A"], cwd=toolkit_root, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=toolkit_root, check=True, env=env)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=toolkit_root, check=True,
        capture_output=True, text=True, env=env,
    )
    return out.stdout.strip()
