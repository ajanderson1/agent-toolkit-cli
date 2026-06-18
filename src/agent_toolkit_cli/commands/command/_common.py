from __future__ import annotations

import re
from pathlib import Path

import click

from agent_toolkit_cli._paths_core import default_scope

SUPPORTED_COMMAND_HARNESSES = ("claude-code", "pi", "codex", "gemini-cli")
DEFAULT_COMMAND_HARNESSES = ("claude-code", "pi", "gemini-cli")
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_slug(slug: str) -> str:
    if not _SLUG_RE.fullmatch(slug or "") or slug in {".", ".."}:
        raise click.ClickException(f"invalid command slug: {slug!r}")
    return slug


def parse_harness_tokens(raw: str) -> tuple[str, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    unknown = [p for p in parts if p not in SUPPORTED_COMMAND_HARNESSES]
    if unknown:
        raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
    return tuple(dict.fromkeys(parts))


def scope_and_roots(global_: bool, project_flag: bool, project_root: Path | None) -> tuple[str, Path | None, Path | None, bool]:
    if global_ and project_flag:
        raise click.UsageError("choose only one of --global/--project")
    cwd = Path.cwd()
    project = project_root or cwd
    if global_:
        return "global", Path.home(), None, False
    if project_flag:
        return "project", None, project, False
    scope = default_scope(project)
    if scope == "project":
        return "project", None, project, True
    return "global", Path.home(), None, True
