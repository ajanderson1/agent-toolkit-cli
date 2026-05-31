"""Store-owned projection for the pi-extension kind.

Pi extensions have NO per-harness fan-out and NO universal bundle: a
store-owned extension projects exactly ONE symlink per scope into Pi's
discovery dir (~/.pi/agent/extensions/<slug> global, <proj>/.pi/extensions/<slug>
project). This module reuses the kind-agnostic guard posture from
_install_core (refuse to overwrite a foreign path; write lock only after a
successful projection) without reusing the skill agent-matrix apply().

Registry-tracked (npm) rows are NOT handled here — they go through
_pi_settings.add_package / remove_package. This module is store-owned only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli._install_core import InstallError  # reuse the base error + posture
from agent_toolkit_cli.pi_extension_paths import (
    Scope,
    library_pi_extension_path,
    pi_extension_dir,
)

__all__ = ["InstallError", "ProjectionPlan", "plan", "apply"]

Action = Literal["install", "uninstall"]


def _doctor_hint(slug: str, scope: Scope) -> str:
    flag = "-g" if scope == "global" else "-p"
    return (
        f"\n  Run: agent-toolkit-cli pi-extension doctor {flag}"
        f"  (clears stray symlinks)"
    )


@dataclass(frozen=True)
class ProjectionPlan:
    slug: str
    scope: Scope
    action: Action
    link: Path          # where Pi discovers it
    canonical: Path     # the store copy
    create: bool        # apply should create the symlink
    remove: bool        # apply should remove the symlink

    def is_noop(self) -> bool:
        return not self.create and not self.remove


def _canonical_for(slug: str) -> Path:
    # Global store-owned canonical lives in the global library regardless of the
    # PROJECTION scope: project-scope install symlinks <proj>/.pi/extensions/<slug>
    # at the SAME global store copy (add is global-only; project install reuses it).
    return library_pi_extension_path(slug)


def plan(
    *,
    slug: str,
    scope: Scope,
    action: Action,
    home: Path | None = None,
    project: Path | None = None,
) -> ProjectionPlan:
    """Compute what apply() should do without mutating anything."""
    link = pi_extension_dir(slug, scope=scope, home=home, project=project)
    canonical = _canonical_for(slug)
    already_ours = (
        link.is_symlink()
        and link.exists()
        and link.resolve() == canonical.resolve()
    )
    if action == "install":
        return ProjectionPlan(
            slug=slug, scope=scope, action=action, link=link, canonical=canonical,
            create=not already_ours, remove=False,
        )
    # uninstall
    return ProjectionPlan(
        slug=slug, scope=scope, action=action, link=link, canonical=canonical,
        create=False, remove=already_ours,
    )


def apply(
    p: ProjectionPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Realise the projection. Foreign-file guard + lock-after-projection.

    create:  refuse if a non-ours path squats the link; else symlink.
    remove:  only unlink if it is OUR symlink (plan.remove already gated that).
    """
    link = p.link
    canonical = p.canonical

    if p.create:
        if not canonical.exists():
            raise InstallError(
                f"{p.slug}: store copy missing at {canonical}; "
                f"run `pi-extension add` first"
            )
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            if link.resolve() != canonical.resolve():
                raise InstallError(
                    f"{p.slug}: conflicting symlink at {link}: points to "
                    f"{link.resolve()}, expected {canonical}"
                    + _doctor_hint(p.slug, p.scope)
                )
            # already ours — idempotent, nothing to do
        elif link.exists():
            raise InstallError(
                f"{p.slug}: conflicting non-symlink at {link}; refusing to "
                f"overwrite a user-authored extension"
                + _doctor_hint(p.slug, p.scope)
            )
        else:
            link.symlink_to(canonical, target_is_directory=True)

    if p.remove:
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            raise InstallError(
                f"{p.slug}: cannot uninstall {link}: not a symlink "
                f"(user-authored?); refusing to delete"
            )
        # absent → already uninstalled, no-op
