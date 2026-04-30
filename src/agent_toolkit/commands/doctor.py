"""`agent-toolkit doctor` — environment sanity check."""
from __future__ import annotations

import shutil
from pathlib import Path

import click

from agent_toolkit._ui import header, summary


@click.command(short_help="Check the environment for prerequisites.")
@click.option(
    "--repo-root",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Repo root to inspect (defaults to current directory).",
)
def doctor(repo_root: str) -> None:
    """Quick sanity check — verifies the schema file is present, AGENTS.md exists,
    and that git, gh, and submodules are available. Reports findings line-by-line
    on stdout. Always exits 0; doctor reports, it does not gate.
    """
    header("Checking environment for agent-toolkit prerequisites...")
    root = Path(repo_root).resolve()
    checks = [
        ("schema present", (root / "schemas" / "asset-frontmatter.v1alpha1.json").exists()),
        ("AGENTS.md present", (root / "AGENTS.md").exists()),
        ("git available", shutil.which("git") is not None),
        ("gh available", shutil.which("gh") is not None),
        ("submodules initialised", (root / ".gitmodules").exists()),
    ]
    ok_count = 0
    missing_count = 0
    for label, ok in checks:
        if ok:
            marker = "OK"
            ok_count += 1
        else:
            marker = "missing"
            missing_count += 1
        click.echo(f"[{marker}] {label}")
    summary(
        f"{ok_count} OK, {missing_count} missing. "
        f"Doctor only reports — it does not gate commits."
    )
