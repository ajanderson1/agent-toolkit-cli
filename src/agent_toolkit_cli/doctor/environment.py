"""Doctor: environment group — schema, AGENTS.md, git, gh, uv, toolkit-root, submodules, PATH-shadowing."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from agent_toolkit_cli.doctor.result import GroupResult, Status

_UV_TOOLS_PREFIX = Path.home() / ".local" / "share" / "uv" / "tools" / "agent-toolkit"


def _cli_entries_on_path(cli_name: str) -> list[Path]:
    """Return all executables named *cli_name* found across $PATH, deduplicated by resolved path."""
    seen: set[Path] = set()
    found: list[Path] = []
    for dir_str in os.environ.get("PATH", "").split(os.pathsep):
        if not dir_str:
            continue
        p = Path(dir_str) / cli_name
        if not p.is_file():
            continue
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            found.append(p)
    return found


def _site_packages_for(python_exe: Path) -> Path | None:
    """Return purelib site-packages path for *python_exe*, or None on error."""
    try:
        out = subprocess.check_output(
            [str(python_exe), "-c",
             "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True, timeout=5, stderr=subprocess.DEVNULL,
        )
        return Path(out.strip())
    except Exception:
        return None


def _stale_editable_installs() -> list[tuple[str, str]]:
    """Return (description, fix_cmd) pairs for stale editable agent_toolkit_cli installs.

    An install is stale when direct_url.json points at a file:// path that no longer exists.
    """
    stale: list[tuple[str, str]] = []
    seen: set[Path] = set()
    for name in ("python3", "python"):
        py_str = shutil.which(name)
        if py_str is None:
            continue
        py = Path(py_str)
        try:
            resolved = py.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        site_pkgs = _site_packages_for(py)
        if site_pkgs is None or not site_pkgs.is_dir():
            continue
        for dist_info in site_pkgs.glob("agent_toolkit_cli-*.dist-info"):
            direct_url = dist_info / "direct_url.json"
            if not direct_url.exists():
                continue
            try:
                data = json.loads(direct_url.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            url: str = data.get("url", "")
            if not url.startswith("file://"):
                continue
            target = Path(url.removeprefix("file://"))
            if not target.exists():
                stale.append((
                    f"stale editable {dist_info.name}: source path {target} does not exist",
                    f"{py} -m pip uninstall -y agent-toolkit",
                ))
    return stale


def run(toolkit_root: Path) -> GroupResult:
    findings: list[str] = []
    failures: list[str] = []
    warns: list[str] = []
    fix_hints: list[str] = []

    schema = toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json"
    if not schema.exists():
        failures.append(f"schema missing at {schema}")
    else:
        findings.append("schema present at schemas/asset-frontmatter.v1alpha2.json")

    agents_md = toolkit_root / "AGENTS.md"
    if not agents_md.exists():
        failures.append("AGENTS.md missing")
    else:
        findings.append("AGENTS.md present")

    for tool in ("git", "gh", "uv"):
        if shutil.which(tool) is None:
            findings.append(f"{tool} NOT on PATH")
        else:
            findings.append(f"{tool} on PATH")

    if (toolkit_root / ".gitmodules").exists():
        findings.append(".gitmodules present")
    else:
        findings.append(".gitmodules absent (no submodules declared)")

    # PATH-shadowing check 1: multiple agent-toolkit entries on PATH
    cli_entries = _cli_entries_on_path("agent-toolkit")
    if len(cli_entries) > 1:
        paths_str = ", ".join(str(p) for p in cli_entries)
        warns.append(f"multiple agent-toolkit entries on PATH: {paths_str}")
        findings.append(f"PATH-shadow: {len(cli_entries)} entries found: {paths_str}")
        fix_hints.append(
            "run `python -m pip uninstall -y agent-toolkit` for the non-uv Python, "
            "or move ~/.local/bin earlier on $PATH"
        )
    elif cli_entries:
        findings.append(f"agent-toolkit on PATH: {cli_entries[0]}")

    # PATH-shadowing check 2: active CLI not from uv tools install
    if cli_entries:
        active = cli_entries[0]
        try:
            is_uv = active.resolve().is_relative_to(_UV_TOOLS_PREFIX)
        except (OSError, ValueError):
            is_uv = False
        if not is_uv:
            warns.append(
                f"active agent-toolkit ({active}) is not from uv tools install "
                f"(expected under {_UV_TOOLS_PREFIX})"
            )
            findings.append(
                f"PATH-shadow: active CLI {active} is not under {_UV_TOOLS_PREFIX}"
            )
            if not fix_hints:
                fix_hints.append(
                    "run `python -m pip uninstall -y agent-toolkit` for the non-uv Python, "
                    "or move ~/.local/bin earlier on $PATH"
                )

    # PATH-shadowing check 3: stale editable install pointing at missing directory
    for desc, fix_cmd in _stale_editable_installs():
        failures.append(desc)
        fix_hints.append(fix_cmd)

    if failures:
        return GroupResult(
            name="environment",
            status=Status.FAIL,
            summary=failures[0],
            findings=findings + failures,
            fix_hint=fix_hints[0] if fix_hints else None,
        )

    tool_warn = any("NOT on PATH" in f for f in findings)
    if warns or tool_warn:
        summary_parts: list[str] = []
        if tool_warn:
            summary_parts.append("some tools not on PATH")
        if warns:
            summary_parts.append("PATH-shadow detected")
        return GroupResult(
            name="environment",
            status=Status.WARN,
            summary="; ".join(summary_parts),
            findings=findings,
            fix_hint="; ".join(fix_hints) if fix_hints else None,
        )

    return GroupResult(
        name="environment",
        status=Status.OK,
        summary="schema, AGENTS.md, git, gh, uv, submodules all present",
        findings=findings,
    )
