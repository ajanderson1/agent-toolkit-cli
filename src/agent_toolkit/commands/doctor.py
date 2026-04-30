"""`agent-toolkit doctor` — environment sanity check."""
from __future__ import annotations

import shutil
from pathlib import Path

import click


@click.command()
@click.option("--repo-root", default=".", type=click.Path(exists=True, file_okay=False))
def doctor(repo_root: str) -> None:
    root = Path(repo_root).resolve()
    checks = [
        ("schema present", (root / "schemas" / "asset-frontmatter.v1alpha1.json").exists()),
        ("AGENTS.md present", (root / "AGENTS.md").exists()),
        ("git available", shutil.which("git") is not None),
        ("gh available", shutil.which("gh") is not None),
        ("submodules initialised", (root / ".gitmodules").exists()),
    ]
    for label, ok in checks:
        marker = "OK" if ok else "missing"
        click.echo(f"[{marker}] {label}")
