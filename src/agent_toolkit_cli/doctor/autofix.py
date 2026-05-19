"""Doctor autofix — mechanical resolutions for sidecar/inline mutex etc.

PR 1: dry-run scaffolding only. Actual write logic activates in PR 3.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli.walker import (
    _SIDECAR_KINDS,
    _KIND_ROOT,
    _inline_body_path,
    extract_frontmatter,
    read_sidecar,
)


@dataclass(frozen=True)
class Fixable:
    """Describes one mechanically-resolvable issue."""

    kind: str
    slug: str
    issue: str       # "mutex" | "orphan-body"
    action: str      # human-readable "would do X"
    target_path: Path


def find_fixables(toolkit_root: Path) -> list[Fixable]:
    """Walk the repo and produce the list of mechanically-fixable issues."""
    fixables: list[Fixable] = []
    submodule_paths = _submodule_paths(toolkit_root)
    for kind in _SIDECAR_KINDS:
        root = toolkit_root / _KIND_ROOT[kind]
        if not root.exists():
            continue
        for sidecar in sorted(root.glob("*.toolkit.yaml")):
            slug = sidecar.name[: -len(".toolkit.yaml")]
            if read_sidecar(sidecar) is None:
                continue
            inline = _inline_body_path(kind, slug, toolkit_root)
            if inline.is_file() and extract_frontmatter(inline) is not None:
                # Mutex violation: prefer sidecar. If body is under a submodule
                # path, we can't safely strip its frontmatter; refuse to autofix
                # that case (operator must intervene).
                if _path_under(inline, submodule_paths):
                    fixables.append(Fixable(
                        kind=kind,
                        slug=slug,
                        issue="mutex",
                        action=(
                            f"Refuse autofix: {inline.relative_to(toolkit_root)} "
                            f"is inside a submodule; cannot strip its frontmatter."
                        ),
                        target_path=inline,
                    ))
                else:
                    fixables.append(Fixable(
                        kind=kind,
                        slug=slug,
                        issue="mutex",
                        action=(
                            f"Would strip inline frontmatter from "
                            f"{inline.relative_to(toolkit_root)} "
                            f"(sidecar wins)."
                        ),
                        target_path=inline,
                    ))
    return fixables


def apply_fixable(item: Fixable) -> None:
    """Apply a fix. PR 1: not implemented — raises NotImplementedError."""
    raise NotImplementedError(
        "Autofix writes activate in PR 3. Run `doctor --fix --dry-run` for now."
    )


def _submodule_paths(toolkit_root: Path) -> list[Path]:
    gm = toolkit_root / ".gitmodules"
    if not gm.exists():
        return []
    parser = configparser.ConfigParser()
    parser.read(gm)
    paths: list[Path] = []
    for sect in parser.sections():
        rel = parser[sect].get("path")
        if rel:
            paths.append((toolkit_root / rel).resolve())
    return paths


def _path_under(path: Path, submodule_paths: list[Path]) -> bool:
    rp = path.resolve()
    for sm in submodule_paths:
        try:
            rp.relative_to(sm)
            return True
        except ValueError:
            continue
    return False
