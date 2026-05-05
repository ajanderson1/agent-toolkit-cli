"""Doctor: mcps group — drift, env-var presence, prerequisites, optional verify.

Read-only group. Reports findings; never writes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from agent_toolkit._allowlist import read_allowlist
from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries
from agent_toolkit.doctor.result import GroupResult, Status
from agent_toolkit.harness_adapters import get_adapter
from agent_toolkit.harness_adapters.base import UnimplementedAdapter


def run(
    toolkit_root: Path,
    *,
    harness: str,
    scope: str,
    project_root: Path,
    run_verify: bool = False,
) -> GroupResult:
    """For each allow-listed MCP under (harness, scope), report:
       - structural drift via adapter.entry_drift (warn-only)
       - env vars from spec.mcp.env present in current shell (warn on missing)
       - prerequisites from spec.mcp.prerequisites on PATH (warn on missing)
       - optional verify command exit code (only with run_verify=True)

    Skips silently with an OK finding when the harness has no adapter
    (UnimplementedAdapter — claude/opencode/pi until their PRs ship).
    """
    findings: list[str] = []
    warnings: list[str] = []

    adapter = get_adapter(harness)
    if isinstance(adapter, UnimplementedAdapter):
        findings.append(f"no MCP adapter for harness {harness} yet — skipped")
        return GroupResult(
            name="mcps",
            status=Status.OK,
            summary=f"no adapter for {harness} yet",
            findings=findings,
        )

    if scope == "user":
        allowlist_path = Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
    else:
        allowlist_path = project_root / ".agent-toolkit.yaml"
    allowed = read_allowlist(allowlist_path).get("mcps", [])
    if not allowed:
        findings.append(f"no allow-listed MCPs for {harness}/{scope}")
        return GroupResult(
            name="mcps",
            status=Status.OK,
            summary="no MCPs allow-listed",
            findings=findings,
        )

    entries = _build_mcp_entries(toolkit_root, allowed)
    installed_names = adapter.list_installed(scope, project_root)

    for entry in entries:
        if entry.name not in installed_names:
            findings.append(
                f"{entry.name}: allow-listed but not installed (run `agent-toolkit link`)"
            )
            continue

        if adapter.entry_drift(scope, project_root, entry):
            warnings.append(f"{entry.name}: drift — installed entry differs from template")
        else:
            findings.append(f"{entry.name}: installed and matches template")

        # env-var presence
        for var in (entry.mcp_spec or {}).get("env") or []:
            if not os.environ.get(var):
                warnings.append(f"{entry.name}: required env {var} not set")

        # prerequisites on PATH
        for tool in (entry.mcp_spec or {}).get("prerequisites") or []:
            if shutil.which(tool) is None:
                warnings.append(f"{entry.name}: prerequisite {tool} not on PATH")

        # verify gate (opt-in)
        verify = (entry.mcp_spec or {}).get("verify")
        if verify and run_verify:
            proc = subprocess.run(
                verify, shell=True, capture_output=True, text=True, check=False,
            )
            if proc.returncode == 0:
                findings.append(f"{entry.name}: verify exited 0")
            else:
                stderr_excerpt = proc.stderr.strip()[:200]
                warnings.append(
                    f"{entry.name}: verify exited {proc.returncode}: {stderr_excerpt}"
                )

    if warnings:
        status = Status.WARN
    else:
        status = Status.OK
    return GroupResult(
        name="mcps",
        status=status,
        summary=f"{len(entries)} MCPs checked, {len(warnings)} warnings",
        findings=findings + warnings,
    )
