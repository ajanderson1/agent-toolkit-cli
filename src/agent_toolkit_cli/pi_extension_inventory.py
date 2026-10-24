"""Build the unified pi-extension inventory (spec §5): one record per
extension Pi could load, across three surfaces — the asset-type lock
(store-owned + tracked npm), loose entries in Pi's extensions/ dir
(untracked), and packages[] in settings.json (npm). Origin is a field,
not a gate. Read-only; PR2 adds projection/state."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli.pi_npm import NpmState, read_npm_states
from agent_toolkit_cli.pi_local_extensions import discover_local_extensions, read_local_extension_states
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import (
    Scope,
    library_pi_extension_path,
    lock_file_path,
    pi_extension_dir,
)

Origin = Literal["store-owned", "untracked", "npm", "local-package"]

@dataclass
class InventoryRecord:
    slug: str
    origin: Origin
    source: str
    global_loaded: bool = False
    project_loaded: bool = False
    pinned_sha: str | None = None
    managed: bool = False
    global_package_spec: str | None = None
    project_package_spec: str | None = None
    global_config_path: Path | None = None
    project_config_path: Path | None = None
    global_package_metadata: dict[str, object] | None = None
    project_package_metadata: dict[str, object] | None = None
    npm_state: NpmState | None = None


def _extensions_root(*, scope: Scope, home: Path | None, project: Path | None) -> Path:
    # pi_extension_dir(slug) is <root>/<slug>; the root is its parent.
    return pi_extension_dir("_", scope=scope, home=home, project=project).parent


def _discover_loose(root: Path) -> list[tuple[str, bool]]:
    """Return native-discoverable slugs without claiming settings selection."""
    return [(slug, True) for slug in discover_local_extensions(root)]


def _is_store_owned_symlink(slug: str, path: Path, rec: InventoryRecord) -> bool:
    """Return True iff path qualifies as a loaded projection for this record.

    For non-store-owned records (untracked, npm) any loadable path counts.
    For store-owned records the path must be a symlink that resolves to the
    toolkit's canonical store copy for slug — a foreign non-symlink squatting
    the slot does NOT qualify, even if it has index.ts/index.js.
    """
    if rec.origin != "store-owned":
        return True
    if not path.is_symlink():
        return False
    try:
        return path.resolve() == library_pi_extension_path(slug).resolve()
    except Exception:
        return False


def _package_slug(spec: str) -> str:
    """Return a stable inventory key without pretending local paths are npm names."""
    if spec.startswith("npm:"):
        return _npm_slug(spec)
    return spec


def _is_npm_spec(spec: str) -> bool:
    return spec.startswith("npm:")


def _package_metadata(spec: str, *, settings_path: Path) -> dict[str, object] | None:
    """Return local package.json metadata without mutating the package."""
    candidate = Path(spec).expanduser()
    if not candidate.is_absolute():
        candidate = settings_path.parent / candidate
    manifest = candidate / "package.json" if candidate.is_dir() else None
    if manifest is None or not manifest.is_file():
        return None
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


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

    # 1. Lock-backed entries: store-owned (git/https/ssh/local) or npm-tracked.
    # source_type="npm" rows are registry-tracked (no store copy); all other
    # source_types are store-owned (cloned into the library). Precedence is
    # resolved in passes 2 and 3: loose/untracked never overwrites a lock row.
    for scope, _ in scopes:
        try:
            lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
        except FileNotFoundError:
            continue
        for slug, entry in lock.skills.items():
            if entry.source_type == "npm":
                continue  # Legacy registrations are not native installation facts.
            origin: Origin = "npm" if entry.source_type == "npm" else "store-owned"
            # `ref_looks_pinned` is origin-aware (an npm row carrying a hex
            # `ref` is not a pin), so status never renders a phantom pin column
            # for an npm entry (spec invariant: npm/untracked → pinned_sha=None).
            pinned_sha = entry.ref if entry.ref_looks_pinned else None
            rec = by_slug.setdefault(
                slug,
                InventoryRecord(
                    slug=slug, origin=origin, source=entry.source,
                    pinned_sha=pinned_sha, managed=True,
                ),
            )
            rec.managed = True
            # A slug that appears in both scopes: store-owned beats npm in the
            # global lock. Project lock rows refine the loaded flags only.
            if rec.origin != "store-owned" or origin == "store-owned":
                rec.origin = origin
            rec.source = entry.source
            rec.pinned_sha = pinned_sha

    # 2. Loose / untracked entries already in Pi's extensions/ dirs.
    for scope, _ in scopes:
        root = _extensions_root(scope=scope, home=home, project=project)
        for slug, loaded in _discover_loose(root):
            rec = by_slug.setdefault(
                slug, InventoryRecord(slug=slug, origin="untracked", source="local")
            )
            # For store-owned slugs, only count the path as loaded when it is
            # actually our symlink to canonical — a foreign non-symlink squatter
            # must not propagate a false globalLoaded=True (fixes #314).
            ext_path = root / slug
            effective_loaded = loaded and _is_store_owned_symlink(slug, ext_path, rec)
            if scope == "global":
                rec.global_loaded = rec.global_loaded or effective_loaded
            else:
                rec.project_loaded = rec.project_loaded or effective_loaded

    # 3. npm packages[] (registry-tracked). Precedence: store-owned > npm >
    # untracked. Like the loose pass, we never clobber a higher-precedence
    # origin — a store-owned slug that is also listed as npm: keeps its
    # store-owned identity; we only record the npm presence (the *_loaded
    # flag). npm does upgrade a slug first seen as loose/untracked.
    for scope, _ in scopes:
        config_path = _pi_settings.settings_path(scope=scope, home=home, project=project)
        packages = _pi_settings.read_package_records(scope=scope, home=home, project=project)
        for package in packages:
            spec = package["source"]
            is_npm = _is_npm_spec(spec)
            if is_npm:
                continue  # Native facade supplies selection, versions and inheritance.
            slug = _package_slug(spec)
            metadata = None if is_npm else _package_metadata(spec, settings_path=config_path)
            origin: Origin = "npm" if is_npm else "local-package"
            source = spec
            rec = by_slug.setdefault(
                slug,
                InventoryRecord(slug=slug, origin=origin, source=source, managed=False),
            )
            if rec.origin != "store-owned" and (rec.origin != "npm" or is_npm):
                rec.origin = origin
                rec.source = source
            if scope == "global":
                rec.global_loaded = True
                rec.global_package_spec = spec
                rec.global_config_path = config_path
                rec.global_package_metadata = metadata
            else:
                rec.project_loaded = True
                rec.project_package_spec = spec
                rec.project_config_path = config_path
                rec.project_package_metadata = metadata

    if any(record.origin == "untracked" for record in by_slug.values()):
        states = read_local_extension_states(home=home, project=project)
        by_slug = {
            slug: record for slug, record in by_slug.items()
            if record.origin != "untracked"
            or (slug in states and (
                any(entry.path not in states[slug].global_package_paths for entry in states[slug].global_entries)
                or any(entry.path not in states[slug].project_package_paths for entry in states[slug].project_entries)
            ))
        }
    for identity, state in read_npm_states(home=home, project=project).items():
        slug = identity if identity not in by_slug else f"npm:{identity}"
        global_scope, project_scope = state.global_scope, state.project_scope
        by_slug[slug] = InventoryRecord(
            slug=slug, origin="npm", source=global_scope.source if global_scope.configured or global_scope.installed else project_scope.source,
            global_loaded=global_scope.enabled, project_loaded=project_scope.enabled,
            managed=False, npm_state=state,
            global_package_spec=global_scope.source if global_scope.configured else None,
            project_package_spec=(project_scope.record if isinstance(project_scope.record, str) else project_scope.record["source"]) if project_scope.record is not None else None,
            global_config_path=_pi_settings.settings_path(scope="global", home=home) if global_scope.configured else None,
            project_config_path=_pi_settings.settings_path(scope="project", project=project) if project is not None and project_scope.record is not None else None,
            global_package_metadata=global_scope.metadata, project_package_metadata=project_scope.metadata,
        )
    return [by_slug[k] for k in sorted(by_slug)]
