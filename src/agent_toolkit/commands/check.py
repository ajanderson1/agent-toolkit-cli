"""`agent-toolkit check` — validate every asset and detect AGENTS.md drift."""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import click

from agent_toolkit.commands.fix import _render
from agent_toolkit.generators.markers import inject_region
from agent_toolkit.schema import Validator
from agent_toolkit.walker import discover_assets

_LEAK_PATTERN = re.compile(r"~/\.claude/(CONVENTIONS\.md|conventions/)")

# Repo-relative path prefixes that may legitimately reference the old paths.
_LEAK_ALLOWED_PREFIXES = (
    "docs/agent-toolkit/",
    "docs/plans/",
    "docs/superpowers/plans/",
    "docs/superpowers/specs/",
    "README.md",
    "src/agent_toolkit/commands/check.py",
    "tests/test_check_conventions_drift.py",
    ".git/",
    ".worktrees/",
)

# File extensions to scan. Stay narrow — we don't grep binaries.
_LEAK_SCAN_EXTENSIONS = {".md", ".py", ".sh", ".bash", ".yaml", ".yml", ".toml", ".json"}


@click.command()
@click.option("--repo-root", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--exit-code", "use_exit_code", is_flag=True, help="Exit non-zero on drift (CI gate).")
def check(repo_root: str, use_exit_code: bool) -> None:
    root = Path(repo_root).resolve()
    validator = Validator(repo_root=root)
    errors: list[str] = []
    for asset in discover_assets(root):
        errors.extend(validator.validate(asset))

    drift = _drift_for_agents_md(root)
    if drift:
        errors.append(f"AGENTS.md drift detected:\n{drift}")

    prose_drift = _drift_for_conventions_prose(root)
    if prose_drift:
        errors.append(prose_drift)

    for err in errors:
        click.echo(err, err=True)
    if errors:
        if use_exit_code:
            raise SystemExit(1)
    else:
        click.echo("OK")


def _drift_for_agents_md(root: Path) -> str | None:
    agents_path = root / "AGENTS.md"
    if not agents_path.exists():
        return None
    current = agents_path.read_text()
    rendered = current
    for region in ("component-table", "submodule-table"):
        try:
            body = _render(region, root)
            rendered = inject_region(rendered, region=region, body=body)
        except ValueError:
            # No marker for this region — skip silently
            continue
    if rendered == current:
        return None
    return _diff(current, rendered)


def _drift_for_conventions_prose(root: Path) -> str | None:
    """Scan repo for stale `~/.claude/CONVENTIONS.md` / `~/.claude/conventions/` prose.

    Returns a multi-line summary of leaks, or None if clean.
    """
    leaks: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in _LEAK_SCAN_EXTENSIONS:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if any(rel.startswith(prefix) for prefix in _LEAK_ALLOWED_PREFIXES):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _LEAK_PATTERN.search(line):
                leaks.append(f"{rel}:{lineno}: {line.strip()}")
    if not leaks:
        return None
    return (
        "Conventions prose leak (cite `~/.conventions/...` instead of `~/.claude/...`):\n"
        + "\n".join(leaks)
    )


def _diff(before: str, after: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="AGENTS.md (current)",
            tofile="AGENTS.md (would-regenerate)",
            lineterm="",
        )
    )
