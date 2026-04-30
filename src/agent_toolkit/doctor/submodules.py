"""Doctor: submodule-health group — declared submodules are initialised."""
from __future__ import annotations

import configparser
from pathlib import Path

from agent_toolkit.doctor.result import GroupResult, Status


def run(repo_root: Path) -> GroupResult:
    gm = repo_root / ".gitmodules"
    if not gm.exists():
        return GroupResult(
            name="submodule-health",
            status=Status.OK,
            summary="no .gitmodules — 0 submodules declared",
        )
    parser = configparser.ConfigParser()
    try:
        with gm.open() as f:
            parser.read_file(f)
    except (OSError, configparser.Error) as e:
        return GroupResult(
            name="submodule-health",
            status=Status.FAIL,
            summary=".gitmodules not loadable",
            findings=[f"{type(e).__name__}: {e}"],
            fix_hint="fix or remove .gitmodules",
        )
    findings: list[str] = []
    warns: list[str] = []
    sm_count = 0
    for sect in parser.sections():
        path_rel = parser[sect].get("path")
        if not path_rel:
            warns.append(f"{sect}: missing `path`")
            continue
        sm_count += 1
        sm_path = repo_root / path_rel
        if not sm_path.is_dir() or not any(sm_path.iterdir()):
            warns.append(f"{path_rel}: uninitialised (run `git submodule update --init --recursive`)")
            continue
        findings.append(f"{path_rel}: present")
    if warns:
        return GroupResult(
            name="submodule-health",
            status=Status.WARN,
            summary=f"{len(warns)} of {sm_count} submodules need attention",
            findings=findings + warns,
            fix_hint="git submodule update --init --recursive",
        )
    return GroupResult(
        name="submodule-health",
        status=Status.OK,
        summary=f"{sm_count} submodule(s), all initialised",
        findings=findings,
    )
