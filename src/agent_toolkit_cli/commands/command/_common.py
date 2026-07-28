from __future__ import annotations

import re
from pathlib import Path

import click

from agent_toolkit_cli._paths_core import default_scope
from agent_toolkit_cli.command_adapters import INSTALLABLE_HARNESSES, SUPPORTED_HARNESSES
from agent_toolkit_cli.command_install import _normalize_to_standard, _ordered_tokens

SUPPORTED_COMMAND_HARNESSES = SUPPORTED_HARNESSES
INSTALLABLE_COMMAND_HARNESSES = INSTALLABLE_HARNESSES
DEFAULT_COMMAND_HARNESSES = ("standard", "pi", "gemini-cli")
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_slug(slug: str) -> str:
    if not _SLUG_RE.fullmatch(slug or "") or slug in {".", ".."}:
        raise click.ClickException(f"invalid command slug: {slug!r}")
    return slug


def default_install_harnesses(scope: str) -> tuple[str, ...]:
    del scope  # defaults are scope-independent for Commands
    return DEFAULT_COMMAND_HARNESSES


def default_uninstall_harnesses(scope: str) -> tuple[str, ...]:
    del scope
    return _ordered_tokens(("standard", *SUPPORTED_COMMAND_HARNESSES))


def parse_harness_tokens(
    raw: str,
    *,
    scope: str = "global",
    slug: str = "demo",
    home: Path | None = None,
    project: Path | None = None,
) -> tuple[str, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    known = set(INSTALLABLE_COMMAND_HARNESSES)
    unknown = [p for p in parts if p not in known]
    if unknown:
        raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
    if "standard-command" in parts:
        raise click.UsageError("unsupported command harness: standard-command")
    resolved = [
        _normalize_to_standard(p, slug, scope=scope, home=home, project=project)
        for p in parts
    ]
    return _ordered_tokens(resolved)


def scope_and_roots(
    global_: bool,
    project_flag: bool,
    project_root: Path | None,
) -> tuple[str, Path | None, Path | None, bool]:
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
