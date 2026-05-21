"""Canonical-clone + per-harness symlink projection.

Layout matches vercel-labs/skills:
  canonical: <root>/.agents/skills/<slug>/   (a real git clone)
  symlinks:  <root>/.<harness>/skills/<slug> -> canonical

Idempotent: re-install on existing canonical fast-forwards the clone;
re-symlink to the right target is a no-op.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    harness_projection_dir,
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Raised when install would clobber a conflicting symlink or path."""


def install(
    *,
    parsed: ParsedSource,
    slug: str,
    scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
    env: dict[str, str] | None,
) -> Path:
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    if canonical.exists():
        skill_git.fetch(canonical, env=env)
        try:
            skill_git.merge(canonical, ref=parsed.ref or "main", env=env)
        except skill_git.GitError:
            # Best-effort fast-forward; local commits or conflicts keep working copy.
            pass
    else:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(parsed.url, canonical, ref=parsed.ref, env=env)

    for harness in harnesses:
        link_path = harness_projection_dir(
            harness, slug, scope=scope, home=home, project=project,
        )
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if link_path.is_symlink():
            target = link_path.resolve()
            if target != canonical.resolve():
                raise InstallError(
                    f"conflicting symlink at {link_path}: "
                    f"points to {target}, expected {canonical}"
                )
        elif link_path.exists():
            raise InstallError(
                f"conflicting non-symlink at {link_path}; refusing to overwrite"
            )
        else:
            link_path.symlink_to(canonical)

    return canonical


def uninstall(
    *,
    slug: str,
    scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
) -> None:
    for harness in harnesses:
        link_path = harness_projection_dir(
            harness, slug, scope=scope, home=home, project=project,
        )
        if link_path.is_symlink() or link_path.exists():
            link_path.unlink()
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    if canonical.exists():
        shutil.rmtree(canonical)
