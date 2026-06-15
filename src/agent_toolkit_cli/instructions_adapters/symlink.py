"""Symlink mechanism: drop a same-name pointer at each harness's slot.

7 cells. Per-cell paths live in CELLS below. The adapter is a closure factory:
adapter_for(harness) returns a small object with .install() / .uninstall().

Sources: Phase A matrix at docs/agent-toolkit/harness-matrix.md
§ "Instruction-file (`instructions` asset type) support — all harnesses"
(symlink-verdict rows, verified 2026-05-29).

Templates use {HOME}, {PROJECT}, {POINTER_NAME} placeholders.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


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
    # google-gemini/gemini-cli memoryTool.ts DEFAULT_CONTEXT_FILENAME = 'GEMINI.md'.
    "gemini-cli":  {"pointer_name": "GEMINI.md",
                    "global":  "{HOME}/.gemini/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "iflow-cli":   {"pointer_name": "IFLOW.md",
                    "global":  "{HOME}/.iflow/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # Replit Agent auto-creates and reads replit.md at project root only.
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
        pointer.parent.mkdir(parents=True, exist_ok=True)
        if pointer.is_symlink():
            current = pointer.resolve()
            if current == canonical.resolve():
                return  # idempotent no-op
            raise PointerConflictError(
                f"{pointer.name} points elsewhere ({current}); refused. "
                "Remove it manually and re-run install."
            )
        if pointer.exists():
            raise PointerConflictError(
                f"{pointer.name} is a real file at {pointer}; refused. "
                "Move or delete it manually and re-run install."
            )
        pointer.symlink_to(canonical)

    def uninstall(
        self,
        *,
        scope: Scope,
        project_root: Path | None,
        canonical: Path,
        home: Path | None,
    ) -> None:
        """Remove only our exact pointer. Real files and foreign symlinks untouched."""
        pointer = _pointer_path(self.harness, scope, project_root, home)
        if not pointer.is_symlink():
            return  # real file or absent — leave alone
        if pointer.resolve() != canonical.resolve():
            return  # foreign symlink — not ours
        pointer.unlink()


def adapter_for(harness: str) -> Adapter:
    if harness not in CELLS:
        raise UnknownHarnessError(f"unknown harness for instructions asset type: {harness!r}")
    return Adapter(harness=harness)
