"""Build the unified pi-extension inventory (spec §5): one record per
extension Pi could load, across three surfaces — the kind lock
(store-owned + tracked npm), loose entries in Pi's extensions/ dir
(untracked), and packages[] in settings.json (npm). Origin is a field,
not a gate. Read-only; PR2 adds projection/state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import (
    Scope,
    lock_file_path,
    pi_extension_dir,
)

Origin = Literal["store-owned", "untracked", "npm"]

# Pi loads dirs with index.ts/.js or a pi.extensions manifest, plus loose
# .ts/.js files. We classify discovered entries by these rules (0.77.0).
_EXTENSION_FILE_SUFFIXES = (".ts", ".js")


@dataclass
class InventoryRecord:
    slug: str
    origin: Origin
    source: str
    global_loaded: bool = False
    project_loaded: bool = False


def _extensions_root(*, scope: Scope, home: Path | None, project: Path | None) -> Path:
    # pi_extension_dir(slug) is <root>/<slug>; the root is its parent.
    return pi_extension_dir("_", scope=scope, home=home, project=project).parent


def _discover_loose(root: Path) -> list[tuple[str, bool]]:
    """Return (slug, is_loaded) for entries Pi would discover under `root`.

    A directory loads if it has index.ts/.js or package.json; a loose
    *.ts/*.js file loads as its stem. We don't read package.json contents
    in PR1 — presence of the file is enough to call it loadable."""
    out: list[tuple[str, bool]] = []
    if not root.exists():
        return out
    for entry in sorted(root.iterdir()):
        if entry.is_dir() or (entry.is_symlink() and entry.resolve().is_dir()):
            has_entry = any(
                (entry / name).exists()
                for name in ("index.ts", "index.js", "package.json")
            )
            if has_entry:
                out.append((entry.name, True))
        elif entry.suffix in _EXTENSION_FILE_SUFFIXES:
            out.append((entry.stem, True))
    return out


def _npm_slug(spec: str) -> str:
    # "npm:@scope/name" -> "@scope/name"; "git:github.com/o/r" -> "github.com/o/r"
    return spec.split(":", 1)[1] if ":" in spec else spec


def build_inventory(
    *,
    home: Path | None = None,
    project: Path | None = None,
) -> list[InventoryRecord]:
    home = home or Path.home()
    by_slug: dict[str, InventoryRecord] = {}
    scopes: list[tuple[Scope, Path | None]] = [("global", None)]
    if project is not None:
        scopes.append(("project", project))

    # 1. Store-owned (from the kind lock).
    for scope, _ in scopes:
        try:
            lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
        except FileNotFoundError:
            continue
        for slug, entry in lock.skills.items():
            rec = by_slug.setdefault(
                slug,
                InventoryRecord(slug=slug, origin="store-owned", source=entry.source),
            )
            rec.origin = "store-owned"
            rec.source = entry.source

    # 2. Loose / untracked entries already in Pi's extensions/ dirs.
    for scope, _ in scopes:
        root = _extensions_root(scope=scope, home=home, project=project)
        for slug, loaded in _discover_loose(root):
            rec = by_slug.setdefault(
                slug, InventoryRecord(slug=slug, origin="untracked", source="local")
            )
            if scope == "global":
                rec.global_loaded = rec.global_loaded or loaded
            else:
                rec.project_loaded = rec.project_loaded or loaded

    # 3. npm packages[] (registry-tracked). Precedence: store-owned > npm >
    # untracked. Like the loose pass, we never clobber a higher-precedence
    # origin — a store-owned slug that is also listed as npm: keeps its
    # store-owned identity; we only record the npm presence (the *_loaded
    # flag). npm does upgrade a slug first seen as loose/untracked.
    for scope, _ in scopes:
        for spec in _pi_settings.read_packages(scope=scope, home=home, project=project):
            if not spec.startswith("npm:"):
                continue
            slug = _npm_slug(spec)
            rec = by_slug.setdefault(
                slug, InventoryRecord(slug=slug, origin="npm", source=spec)
            )
            if rec.origin != "store-owned":
                rec.origin = "npm"
                rec.source = spec
            if scope == "global":
                rec.global_loaded = True
            else:
                rec.project_loaded = True

    return [by_slug[k] for k in sorted(by_slug)]
