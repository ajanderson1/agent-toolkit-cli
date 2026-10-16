"""Symlink mechanism: drop a same-name pointer at each harness's slot.

7 cells. Per-cell paths live in CELLS below. The adapter is a closure factory:
adapter_for(harness) returns a small object with .install() / .uninstall().

Sources: Phase A matrix at docs/agent-toolkit/harness-matrix.md
§ "Instruction-file (`instructions` asset type) support — all harnesses"
(symlink-verdict rows, verified 2026-05-29).

Templates use {HOME}, {PROJECT}, {POINTER_NAME} placeholders.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Literal
import unicodedata


class PointerConflictError(RuntimeError):
    """A real file or foreign symlink occupies the pointer slot; refused."""


class MissingHomeError(RuntimeError):
    """A {HOME} template was expanded with home=None — a caller bug, not a
    legitimately-skippable cell. Distinct from the ValueError raised when a
    harness simply has no slot for the requested scope, so callers can keep
    swallowing the latter while failing loud on the former."""


class UnknownHarnessError(KeyError):
    """`harness` is not in the instructions-asset-type CELLS table."""


Scope = Literal["project", "global"]


# Per-harness pointer path templates + the own-name file each harness reads.
# Sources cited inline; full Phase A evidence in instructions-fragments/.
CELLS: dict[str, dict[str, str]] = {
    # CLAUDE.md is the default-loaded root file across the Auggie precedence chain.
    "augment":     {"pointer_name": "CLAUDE.md",
                    "global":  "{HOME}/.augment/CLAUDE.md",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # https://code.claude.com/docs/en/memory — "Claude Code reads CLAUDE.md, not AGENTS.md".
    "claude-code": {"pointer_name": "CLAUDE.md",
                    "global":  "{HOME}/.claude/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "codebuddy":   {"pointer_name": "CODEBUDDY.md",
                    "global":  "{HOME}/.codebuddy/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # Native in repositories; managed pointer only at the global reader slot.
    "codex":       {"pointer_name": "AGENTS.md",
                    "global":  "{HOME}/.codex/AGENTS.md",
                    "project": ""},
    # google-gemini/gemini-cli memoryTool.ts DEFAULT_CONTEXT_FILENAME = 'GEMINI.md'.
    "gemini-cli":  {"pointer_name": "GEMINI.md",
                    "global":  "{HOME}/.gemini/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "iflow-cli":   {"pointer_name": "IFLOW.md",
                    "global":  "{HOME}/.iflow/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # Replit Agent auto-creates and reads replit.md at project root only.
    "opencode":    {"pointer_name": "AGENTS.md",
                    "global":  "{HOME}/.config/opencode/AGENTS.md",
                    "project": ""},
    "pi":          {"pointer_name": "AGENTS.md",
                    "global":  "{HOME}/.pi/agent/AGENTS.md",
                    "project": ""},
    "replit":      {"pointer_name": "replit.md",
                    "global":  "",  # no global
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "tabnine-cli": {"pointer_name": "TABNINE.md",
                    "global":  "{HOME}/.tabnine/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
}


def _expand(template: str, *, home: Path | None, project: Path | None, pointer_name: str) -> Path:
    """Expand {HOME}/{PROJECT}/{POINTER_NAME}. Fail-loud on missing inputs."""
    out = template.replace("{POINTER_NAME}", pointer_name)
    if "{HOME}" in out:
        if home is None:
            raise MissingHomeError(
                f"_expand: template {template!r} needs home= but None was passed"
            )
        out = out.replace("{HOME}", str(home))
    if "{PROJECT}" in out:
        if project is None:
            raise ValueError(f"_expand: template {template!r} needs project= but None was passed")
        out = out.replace("{PROJECT}", str(project))
    return Path(out)


def _pointer_path(
    harness: str, scope: Scope, project_root: Path | None, home: Path | None
) -> Path:
    cell = CELLS[harness]
    template = cell[scope]
    if not template:
        raise ValueError(
            f"harness {harness!r} has no {scope} pointer slot (project-only or global-only)"
        )
    return _expand(template, home=home, project=project_root, pointer_name=cell["pointer_name"])


class CanonicalChainError(RuntimeError):
    """A removal would break (or cannot safely inspect) canonical's source chain."""


@dataclass(frozen=True)
class PointerState:
    linked: bool = False
    conflict: bool = False
    error: str = ""


def canonical_usable(canonical: Path) -> bool:
    try:
        if not canonical.is_file():
            return False
        with canonical.open('rb'):
            return True
    except (OSError, RuntimeError):
        return False


def inspect_pointer(pointer: Path, canonical: Path) -> PointerState:
    """Read installation truth without creating or repairing anything."""
    try:
        try:
            mode = pointer.lstat().st_mode
        except FileNotFoundError:
            return PointerState()
        if stat.S_ISLNK(mode):
            canonical_chain(pointer)
            canonical_chain(canonical)
            linked = pointer.resolve() == canonical.resolve()
            return PointerState(linked=linked, conflict=not linked)
        return PointerState(conflict=True)
    except (OSError, RuntimeError) as exc:
        return PointerState(conflict=True, error=str(exc))


def link_snapshot(pointer: Path) -> tuple[int, int, str] | None:
    """Identify the symlink node itself, never its final resolved source file."""
    try:
        info = pointer.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISLNK(info.st_mode):
        return None
    return info.st_dev, info.st_ino, os.readlink(pointer)


def pointer_slot(pointer: Path, *, node: tuple[int, int] | None = None) -> tuple:
    """Identify a fixed-name slot, disambiguating alternate chain spellings if needed."""
    try:
        parent = pointer.parent.stat()
    except FileNotFoundError:
        return ('path', pointer.parent.resolve(), pointer.name)
    if node is None:
        try:
            info = pointer.lstat()
        except FileNotFoundError:
            pass
        else:
            node = info.st_dev, info.st_ino
    name = pointer.name
    if node is not None:
        entries = list(pointer.parent.iterdir())
        exact = [entry for entry in entries if entry.name == name]
        if exact:
            matches = exact
        else:
            normalized = unicodedata.normalize('NFC', name).casefold()
            matches = [entry for entry in entries
                       if unicodedata.normalize('NFC', entry.name).casefold() == normalized]
        validated = []
        for entry in matches:
            info = entry.lstat()
            if (info.st_dev, info.st_ino) == node:
                validated.append(entry)
        if len(validated) != 1:
            raise PointerConflictError(f'cannot identify directory entry for {pointer}; refused batch')
        name = validated[0].name
    return ('directory', parent.st_dev, parent.st_ino, name)


def canonical_chain(canonical: Path) -> set[tuple[int, int]]:
    """Collect physical symlink-node identities, including directory-component hops."""
    return {node for _, node in _symlink_chain(canonical)}


def pointer_chain(pointer: Path) -> set[tuple]:
    """Collect traversed entries, not every hardlink sharing a traversed node."""
    return {pointer_slot(path, node=node) for path, node in _symlink_chain(pointer)}


def _symlink_chain(canonical: Path) -> Iterator[tuple[Path, tuple[int, int]]]:
    path = canonical.absolute()
    pending = deque(path.parts[1:])
    resolved = Path(path.anchor)
    hops = 0
    while pending:
        part = pending.popleft()
        if part == '..':
            resolved = resolved.parent
            continue
        if part == '.':
            continue
        candidate = resolved / part
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            info = None
        if info is not None and stat.S_ISLNK(info.st_mode):
            hops += 1
            if hops > 40:
                raise CanonicalChainError(f'cannot inspect canonical chain at {canonical}: symlink loop or too many hops')
            yield candidate, (info.st_dev, info.st_ino)
            target = Path(os.readlink(candidate))
            if target.is_absolute():
                resolved = Path(target.anchor)
                parts = target.parts[1:]
            else:
                parts = target.parts
            pending.extendleft(reversed(parts))
        else:
            resolved = candidate


def preflight_removals(canonical: Path, pointers: list[Path]) -> None:
    if not pointers:
        return
    try:
        chain = canonical_chain(canonical)
        for pointer in pointers:
            node = link_snapshot(pointer)
            if node is not None and node[:2] in chain:
                raise CanonicalChainError(
                    f'refused removal batch: {pointer} participates in canonical '
                    f'AGENTS.md symlink chain ({canonical}). Reorganize your source '
                    'chain manually before uninstalling; no chain links were changed.'
                )
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, CanonicalChainError):
            raise
        raise CanonicalChainError(f'cannot safely inspect canonical chain at {canonical}: {exc}') from exc


@dataclass(frozen=True)
class Adapter:
    """Per-harness install/uninstall closure."""
    harness: str

    def install(
        self,
        *,
        scope: Scope,
        project_root: Path | None,
        canonical: Path,
        home: Path | None,
    ) -> None:
        """Create the pointer symlink → canonical. Refuse on conflict."""
        pointer = _pointer_path(self.harness, scope, project_root, home)
        state = inspect_pointer(pointer, canonical)
        if state.linked:
            return
        if state.conflict:
            raise PointerConflictError(
                f'{pointer} is a real file or foreign/unresolvable symlink; refused. '
                f'Move it manually and re-run install. {state.error}'
            )
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.symlink_to(canonical.absolute())

    def uninstall(
        self,
        *,
        scope: Scope,
        project_root: Path | None,
        canonical: Path,
        home: Path | None,
        expected_link: tuple[int, int, str] | None = None,
    ) -> None:
        """Remove only the prevalidated symlink; protect canonical's physical source chain."""
        pointer = _pointer_path(self.harness, scope, project_root, home)
        original = link_snapshot(pointer)
        if expected_link is not None and original != expected_link:
            raise PointerConflictError(f'{pointer} changed since removal planning; inspect it before retrying')
        state = inspect_pointer(pointer, canonical)
        if state.error:
            raise PointerConflictError(f'cannot inspect {pointer}: {state.error}')
        if not state.linked:
            if expected_link is not None:
                raise PointerConflictError(f'{pointer} no longer resolves to canonical; requested removal was not completed')
            return
        preflight_removals(canonical, [pointer])
        current = inspect_pointer(pointer, canonical)
        if not current.linked or current.error or link_snapshot(pointer) != original:
            raise PointerConflictError(f'{pointer} changed during removal; inspect it before retrying')
        pointer.unlink()


def adapter_for(harness: str) -> Adapter:
    if harness not in CELLS:
        raise UnknownHarnessError(f"unknown harness for instructions asset type: {harness!r}")
    return Adapter(harness=harness)
