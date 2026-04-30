"""Doctor: environment group — schema, AGENTS.md, git, gh, uv, repo-root, submodules."""
from __future__ import annotations

import shutil
from pathlib import Path

from agent_toolkit.doctor.result import GroupResult, Status


def run(repo_root: Path) -> GroupResult:
    findings: list[str] = []
    failures: list[str] = []

    schema = repo_root / "schemas" / "asset-frontmatter.v1alpha1.json"
    if not schema.exists():
        failures.append(f"schema missing at {schema}")
    else:
        findings.append(f"schema present at {schema.relative_to(repo_root)}")

    agents_md = repo_root / "AGENTS.md"
    if not agents_md.exists():
        failures.append("AGENTS.md missing")
    else:
        findings.append("AGENTS.md present")

    for tool in ("git", "gh", "uv"):
        if shutil.which(tool) is None:
            findings.append(f"{tool} NOT on PATH")
        else:
            findings.append(f"{tool} on PATH")

    if (repo_root / ".gitmodules").exists():
        findings.append(".gitmodules present")
    else:
        findings.append(".gitmodules absent (no submodules declared)")

    if failures:
        return GroupResult(
            name="environment",
            status=Status.FAIL,
            summary="; ".join(failures),
            findings=findings + failures,
        )

    if any("NOT on PATH" in f for f in findings):
        return GroupResult(
            name="environment",
            status=Status.WARN,
            summary="some tools not on PATH",
            findings=findings,
        )

    return GroupResult(
        name="environment",
        status=Status.OK,
        summary="schema, AGENTS.md, git, gh, uv, submodules all present",
        findings=findings,
    )
