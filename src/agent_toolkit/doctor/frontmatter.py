"""Doctor: frontmatter group — re-runs schema validation across all assets."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit.doctor.result import GroupResult, Status
from agent_toolkit.schema import Validator
from agent_toolkit.walker import discover_assets


def run(toolkit_root: Path) -> GroupResult:
    validator = Validator(toolkit_root=toolkit_root)
    errors: list[str] = []
    asset_count = 0
    for asset in discover_assets(toolkit_root):
        asset_count += 1
        errors.extend(validator.validate(asset))
    if not errors:
        return GroupResult(
            name="frontmatter",
            status=Status.OK,
            summary=f"{asset_count} asset(s) all valid",
            findings=[f"{asset_count} asset(s) validated"],
        )
    return GroupResult(
        name="frontmatter",
        status=Status.FAIL,
        summary=f"{len(errors)} validation error(s) across {asset_count} asset(s)",
        findings=errors,
        fix_hint="run `agent-toolkit check` for details, or `agent-toolkit fix` for drift",
    )
