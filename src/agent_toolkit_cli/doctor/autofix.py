"""Doctor autofix — mechanical resolutions for sidecar/inline mutex etc.

Currently implements the mutex case (strip inline frontmatter, sidecar wins).
Refuses to edit files inside submodule paths. The orphan-body case is
scaffolded but not yet wired through find_fixables; calling it raises
NotImplementedError.
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
    is_toolkit_frontmatter,
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
            inline_meta = extract_frontmatter(inline) if inline.is_file() else None
            if is_toolkit_frontmatter(inline_meta):
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
    """Apply a mechanical autofix."""
    if item.issue == "mutex":
        path = item.target_path
        # Defense in depth: never edit files in submodule paths
        toolkit_root = _find_toolkit_root(path)
        submods = _submodule_paths(toolkit_root)
        if _path_under(path, submods):
            raise NotImplementedError(
                f"refused: {path} is under a submodule path; "
                f"toolkit must not edit upstream content"
            )
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            return
        end = text.find("\n---\n", 4)
        if end == -1:
            return
        stripped = text[end + len("\n---\n") :].lstrip("\n")
        path.write_text(stripped, encoding="utf-8")
        return
    if item.issue == "orphan-body":
        raise NotImplementedError(
            "orphan-body autofix not yet wired through find_fixables. "
            "Until the discovery side emits orphan-body Fixables, this "
            "branch is unreachable; manually create the sidecar from the "
            "template in `agent-toolkit-cli new skill <slug>` for now."
        )


def _find_toolkit_root(path: Path) -> Path:
    """Walk up from a path to find the toolkit root (parent containing skills/ or mcps/)."""
    for ancestor in path.resolve().parents:
        if (ancestor / "skills").is_dir() or (ancestor / "mcps").is_dir():
            return ancestor
    raise RuntimeError(f"could not find toolkit root above {path}")


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
