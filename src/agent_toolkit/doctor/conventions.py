"""Doctor: conventions group — CONVENTIONS.md + conventions/<topic>.md sync."""
from __future__ import annotations

import os
from pathlib import Path

from agent_toolkit.doctor.result import GroupResult, Status


def run(repo_root: Path, *, harness: str = "claude") -> GroupResult:
    home = Path(os.environ.get("HOME", str(Path.home())))
    user_root = home / f".{harness}"

    findings: list[str] = []
    warns: list[str] = []

    repo_conv_md = repo_root / "CONVENTIONS.md"
    user_conv_md = user_root / "CONVENTIONS.md"

    if not repo_conv_md.exists():
        return GroupResult(
            name="conventions",
            status=Status.OK,
            summary="repo has no CONVENTIONS.md (skipped)",
        )

    if not user_conv_md.is_symlink():
        warns.append(f"{user_conv_md} is not a symlink to {repo_conv_md}")
    else:
        target = user_conv_md.resolve()
        if target != repo_conv_md.resolve():
            warns.append(f"{user_conv_md} points to {target}, expected {repo_conv_md}")
        else:
            findings.append(f"{user_conv_md.name} ↔ repo CONVENTIONS.md")

    repo_topics_dir = repo_root / "conventions"
    user_topics_dir = user_root / "conventions"
    if repo_topics_dir.is_dir():
        repo_topics = {p.name for p in repo_topics_dir.iterdir() if p.suffix == ".md"}
        user_topics = (
            {p.name for p in user_topics_dir.iterdir() if p.suffix == ".md"}
            if user_topics_dir.is_dir() else set()
        )
        missing = sorted(repo_topics - user_topics)
        extra = sorted(user_topics - repo_topics)
        for m in missing:
            warns.append(f"{user_topics_dir}/{m} missing")
        for e in extra:
            warns.append(f"{user_topics_dir}/{e} present but not in repo")
        findings.append(
            f"~/.{harness}/conventions/*.md ({len(user_topics & repo_topics)}/{len(repo_topics)}) linked"
        )

    if warns:
        return GroupResult(
            name="conventions",
            status=Status.WARN,
            summary=f"{len(warns)} convention sync issue(s)",
            findings=findings + warns,
            fix_hint=f"`bin/agent-toolkit link user {harness}` or check ~/.{harness}/ symlinks manually",
        )
    return GroupResult(
        name="conventions",
        status=Status.OK,
        summary="CONVENTIONS.md and topic files all linked",
        findings=findings,
    )
