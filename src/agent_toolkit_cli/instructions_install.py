"""Explicit, lockless operations on Instructions pointer slots."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.instructions_adapters.symlink import (
    CanonicalChainError,
    PointerConflictError,
    _pointer_path,
    canonical_usable,
    inspect_pointer,
    preflight_removals,
)

Scope = Literal['project', 'global']


class CanonicalMissingError(RuntimeError):
    """Canonical instruction content is not a readable file."""


@dataclass
class PointerAction:
    harness: str
    pointer: Path
    action: Literal['create', 'remove', 'noop-already-correct', 'skip-foreign']


@dataclass
class Plan:
    canonical: Path
    actions: list[PointerAction]


def _resolve_canonical(scope: Scope, project_root: Path | None) -> Path:
    if scope == 'project':
        if project_root is None:
            raise ValueError('project scope requires project_root')
        return instructions_paths.project_canonical_agents_md(project_root)
    if scope == 'global':
        return instructions_paths.global_canonical_agents_md()
    raise ValueError(f'unknown scope: {scope!r}')


def pointer_slots(*, scope: Scope, project_root: Path | None, home: Path | None) -> dict[str, Path]:
    _resolve_canonical(scope, project_root)
    slots = {}
    for harness in sorted(SUPPORTED_HARNESSES):
        try:
            slots[harness] = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
    return slots


def _list_currently_owned(canonical: Path, scope: Scope, project_root: Path | None, home: Path | None) -> set[str]:
    return {
        h for h, pointer in pointer_slots(scope=scope, project_root=project_root, home=home).items()
        if inspect_pointer(pointer, canonical).linked
    }


def plan(*, scope: Scope, project_root: Path | None, home: Path | None,
         add_harnesses: Iterable[str] = (), remove_harnesses: Iterable[str] = ()) -> Plan:
    """Preflight the entire explicit batch; never prune unrequested pointers."""
    canonical = _resolve_canonical(scope, project_root)
    intents: dict[Path, tuple[str, str, Path]] = {}
    for operation, harnesses in [('create', add_harnesses), ('remove', remove_harnesses)]:
        for harness in sorted(set(harnesses)):
            get_adapter(harness)
            pointer = _pointer_path(harness, scope, project_root, home)
            physical = pointer.parent.resolve() / pointer.name
            if physical in intents and intents[physical][1] != operation:
                raise PointerConflictError(f'opposing requests for shared pointer {pointer}; refused batch')
            intents[physical] = (harness, operation, pointer)
    if any(op == 'create' for _, op, _ in intents.values()) and not canonical_usable(canonical):
        raise CanonicalMissingError(f'no readable AGENTS.md at {canonical}; create it before running install')
    preflight_removals(canonical, [p for _, op, p in intents.values() if op == 'remove'])
    actions = []
    for harness, operation, pointer in intents.values():
        state = inspect_pointer(pointer, canonical)
        if state.error:
            raise PointerConflictError(f'cannot inspect {pointer}: {state.error}')
        if operation == 'create':
            if state.conflict:
                raise PointerConflictError(f'{pointer} is a real file or foreign symlink; refused batch')
            action = 'noop-already-correct' if state.linked else 'create'
        else:
            action = 'remove' if state.linked else 'skip-foreign'
        actions.append(PointerAction(harness, pointer, action))
    return Plan(canonical, actions)


def apply(*, scope: Scope, project_root: Path | None, home: Path | None,
          add_harnesses: Iterable[str] = (), remove_harnesses: Iterable[str] = ()) -> Plan:
    p = plan(scope=scope, project_root=project_root, home=home,
             add_harnesses=add_harnesses, remove_harnesses=remove_harnesses)
    for action in p.actions:
        adapter = get_adapter(action.harness)
        if action.action == 'create':
            adapter.install(scope=scope, project_root=project_root, canonical=p.canonical, home=home)
        elif action.action == 'remove':
            adapter.uninstall(scope=scope, project_root=project_root, canonical=p.canonical, home=home)
    return p


def uninstall(*, scope: Scope, project_root: Path | None, home: Path | None) -> None:
    canonical = _resolve_canonical(scope, project_root)
    owned = _list_currently_owned(canonical, scope, project_root, home)
    # Even an unresolvable slot must not be silently reported as uninstalled.
    for pointer in pointer_slots(scope=scope, project_root=project_root, home=home).values():
        state = inspect_pointer(pointer, canonical)
        if state.error:
            raise PointerConflictError(f'cannot inspect {pointer}: {state.error}')
    apply(scope=scope, project_root=project_root, home=home, remove_harnesses=owned)
