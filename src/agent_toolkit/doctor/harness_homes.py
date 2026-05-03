"""Doctor: harness_homes group — checks ~/.{harness}/ exists per harness."""
from __future__ import annotations

from agent_toolkit.commands._link_lib import ALL_HARNESSES, harness_home_path
from agent_toolkit.doctor.result import GroupResult, Status


def run() -> GroupResult:
    findings: list[str] = []
    missing: list[str] = []
    for harness in ALL_HARNESSES:
        path = harness_home_path(harness)
        if path.is_dir():
            findings.append(f"{harness} home present at {path}")
        else:
            missing.append(
                f"{harness} home not present at {path} — install the harness "
                f"or stage symlinks anyway"
            )

    if missing:
        return GroupResult(
            name="harness-homes",
            status=Status.WARN,
            summary=f"{len(missing)} harness home(s) missing",
            findings=findings + missing,
            fix_hint="install the harness, or ignore — symlinks can be staged ahead of install",
        )

    return GroupResult(
        name="harness-homes",
        status=Status.OK,
        summary="all 4 harness homes present",
        findings=findings,
    )
