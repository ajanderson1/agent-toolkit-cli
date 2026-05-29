"""Reconcile filesystem pointers to match the instructions lockfile.

Public surface:
    apply(scope, project_root, home)     — reconcile pointers ON for `scope`
    uninstall(scope, project_root, home) — remove pointers + clear lock entry
    plan(scope, project_root, home)      — return diff without touching disk

`apply` is idempotent and pruning: it creates pointers for lock-listed
harnesses that aren't on disk, removes ours-but-no-longer-listed pointers,
and leaves foreign / real-file slots alone (delegated to the adapter).

Unsupported harnesses in the lock (`native` / `gap` / `by-design` / `unknown`)
are silently skipped — surfacing them is the CLI's job (it has access to
`click.echo`). This module returns structured plans, not user-facing text.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.instructions_lock import (
    read_lock,
    remove_entry,
    write_lock,
)

Scope = Literal["project", "global"]


class CanonicalMissingError(RuntimeError):
    """No AGENTS.md at the resolved canonical path — pointer install refused."""


@dataclass
class PointerAction:
    harness: str
    pointer: Path
    action: Literal["create", "remove", "noop-already-correct", "skip-foreign", "skip-unsupported"]


@dataclass
class Plan:
    canonical: Path
    actions: list[PointerAction]


def _resolve_canonical(scope: Scope, project_root: Path | None) -> Path:
    if scope == "project":
        if project_root is None:
            raise ValueError("project scope requires project_root")
        return instructions_paths.project_canonical_agents_md(project_root)
    return instructions_paths.global_canonical_agents_md()


def _list_currently_owned(
    canonical: Path, scope: Scope, project_root: Path | None, home: Path | None
) -> set[str]:
    """For each supported harness, return those whose pointer symlinks at canonical."""
    from agent_toolkit_cli.instructions_adapters.symlink import (
        _pointer_path,
    )
    owned: set[str] = set()
    for harness in SUPPORTED_HARNESSES:
        # Some cells are project-only or global-only — _pointer_path raises for those.
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer.is_symlink() and pointer.resolve() == canonical.resolve():
            owned.add(harness)
    return owned


def plan(
    *, scope: Scope, project_root: Path | None, home: Path | None
) -> Plan:
    """Return a Plan describing what apply() would do. No disk changes."""
    canonical = _resolve_canonical(scope, project_root)
    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)

    wanted: set[str] = set()
    for entry in lock.instructions.values():
        wanted.update(h for h in entry.harnesses if h in SUPPORTED_HARNESSES)

    owned = _list_currently_owned(canonical, scope, project_root, home)

    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path

    # Some harnesses share a pointer slot (e.g. `augment` and `claude-code` both
    # use project-root CLAUDE.md). Reconcile by pointer *path*, not harness name,
    # so we never prune a slot that a still-wanted harness also claims.
    wanted_paths: set[Path] = set()
    for harness in wanted:
        try:
            wanted_paths.add(_pointer_path(harness, scope, project_root, home))
        except ValueError:
            continue

    actions: list[PointerAction] = []
    for harness in sorted(wanted - owned):
        try:
            ptr = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        actions.append(PointerAction(harness=harness, pointer=ptr, action="create"))
    for harness in sorted(owned - wanted):
        ptr = _pointer_path(harness, scope, project_root, home)
        if ptr in wanted_paths:
            # Slot is still claimed by another wanted harness — keep it.
            continue
        actions.append(PointerAction(harness=harness, pointer=ptr, action="remove"))
    for harness in sorted(owned & wanted):
        ptr = _pointer_path(harness, scope, project_root, home)
        actions.append(PointerAction(harness=harness, pointer=ptr, action="noop-already-correct"))
    return Plan(canonical=canonical, actions=actions)


def apply(*, scope: Scope, project_root: Path | None, home: Path | None) -> Plan:
    """Reconcile filesystem to match the lock. Returns the plan that was applied.

    Refuses if canonical AGENTS.md is missing.
    """
    canonical = _resolve_canonical(scope, project_root)
    if not canonical.exists():
        raise CanonicalMissingError(
            f"no AGENTS.md at {canonical} to point to; create it before running install"
        )

    p = plan(scope=scope, project_root=project_root, home=home)
    for act in p.actions:
        if act.action == "create":
            get_adapter(act.harness).install(
                scope=scope, project_root=project_root,
                canonical=canonical, home=home,
            )
        elif act.action == "remove":
            get_adapter(act.harness).uninstall(
                scope=scope, project_root=project_root,
                canonical=canonical, home=home,
            )
        # noop-already-correct: nothing to do.
    return p


def uninstall(
    *, scope: Scope, project_root: Path | None, home: Path | None
) -> None:
    """Remove all our pointers and clear the lock entry at this scope."""
    canonical = _resolve_canonical(scope, project_root)
    owned = _list_currently_owned(canonical, scope, project_root, home)
    for harness in owned:
        get_adapter(harness).uninstall(
            scope=scope, project_root=project_root,
            canonical=canonical, home=home,
        )
    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)
    new = lock
    for slug in list(lock.instructions.keys()):
        new = remove_entry(new, slug)
    write_lock(lock_path, new)
