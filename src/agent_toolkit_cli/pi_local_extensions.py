"""Native configuration selection for conventional, non-owned Pi extensions.

Selectors address lexical resource paths. Canonical paths are used ONLY for
Pi's final resource deduplication, never for matching or writing selectors.
No extension code is imported; no library locks or source files are written.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from pathspec import GitIgnoreSpec
from wcmatch import glob

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli._pi_settings import PiSettingsError, Scope


@dataclass(frozen=True)
class LocalExtensionEntry:
    path: Path
    enabled: bool


@dataclass(frozen=True)
class LocalExtensionState:
    global_entries: tuple[LocalExtensionEntry, ...] = ()
    project_entries: tuple[LocalExtensionEntry, ...] = ()
    available_paths: tuple[Path, ...] = ()

    @property
    def global_enabled(self) -> bool:
        return bool(self.global_entries) and all(e.enabled for e in self.global_entries)

    @property
    def project_enabled(self) -> bool:
        return bool(self.project_entries) and all(e.enabled for e in self.project_entries)

    @property
    def global_mixed(self) -> bool:
        return any(e.enabled for e in self.global_entries) and not self.global_enabled

    @property
    def project_mixed(self) -> bool:
        return any(e.enabled for e in self.project_entries) and not self.project_enabled

    def paths_for(self, scope: str) -> tuple[Path, ...]:
        entries = self.global_entries if scope == "global" else self.project_entries
        return tuple(e.path for e in entries) or self.available_paths


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _directory_entries(directory: Path) -> tuple[Path, ...]:
    """Mirror Pi resolveExtensionEntries: valid manifest, then index.ts/.js."""
    try:
        data = json.loads((directory / "package.json").read_text(encoding="utf-8-sig"))
        manifest = data.get("pi") if isinstance(data, dict) else None
        entries = manifest.get("extensions") if isinstance(manifest, dict) else None
        if isinstance(entries, list) and all(isinstance(e, str) for e in entries):
            paths = tuple(_lexical(directory / e) for e in entries if (directory / e).exists())
            if paths:
                return paths
    except (OSError, ValueError):
        pass
    for name in ("index.ts", "index.js"):
        path = directory / name
        if path.exists():
            return (path,)
    return ()


def discover_local_extensions(root: Path) -> dict[str, tuple[Path, ...]]:
    """Group native auto-discovered lexical entrypoints by the existing slug."""
    root = _lexical(root)
    if not root.is_dir():
        return {}
    grouped: dict[str, list[Path]] = {}
    seen: set[Path] = set()

    def add(slug: str, paths: tuple[Path, ...]) -> None:
        for path in paths:
            canonical = path.resolve()
            if canonical not in seen:
                seen.add(canonical)
                grouped.setdefault(slug, []).append(path)

    root_entries = _directory_entries(root)
    if root_entries:
        for path in root_entries:
            relative = Path(os.path.relpath(path, root))
            slug = relative.parts[0] if len(relative.parts) > 1 and relative.parts[0] != ".." else path.stem
            add(slug, (path,))
    else:
        rules: list[str] = []
        for name in (".gitignore", ".ignore", ".fdignore"):
            try:
                rules.extend((root / name).read_text().splitlines())
            except OSError:
                pass
        ignored = GitIgnoreSpec.from_lines(rules)
        for path in sorted(root.iterdir()):
            if path.name.startswith(".") or path.name == "node_modules":
                continue
            is_dir = path.is_dir()
            if ignored.match_file(path.name + ("/" if is_dir else "")):
                continue
            if is_dir:
                add(path.name, _directory_entries(path))
            elif path.is_file() and path.suffix in (".ts", ".js"):
                add(path.stem, (path,))
    return {slug: tuple(paths) for slug, paths in grouped.items()}


def _normalize_pattern(value: str, home: Path) -> str:
    if value == "~":
        return str(home)
    if value.startswith("~/"):
        return str(home / value[2:])
    if value.startswith("file://"):
        return unquote(urlparse(value).path)
    return value


def _exact(path: Path, pattern: str, base: Path, home: Path) -> bool:
    if pattern.startswith(("./", ".\\")):
        pattern = pattern[2:]
    pattern = _normalize_pattern(pattern, home)
    return pattern in (str(path), os.path.relpath(path, base))


def _matches(path: Path, pattern: str, base: Path, home: Path) -> bool:
    pattern = _normalize_pattern(pattern, home)
    if pattern.startswith("#"):
        return False  # Minimatch comments are not exclusion expressions.
    # Minimatch's leading ! negates the expression, even after the selector !.
    negated = False
    while pattern.startswith("!"):
        negated = not negated
        pattern = pattern[1:]
    flags = glob.GLOBSTAR | glob.BRACE | glob.EXTGLOB
    return any(
        (not glob.globmatch(value, pattern, flags=flags)) if negated
        else glob.globmatch(value, pattern, flags=flags)
        for value in (os.path.relpath(path, base), path.name, str(path))
    )


def _is_pattern(value: str) -> bool:
    return value.startswith(("!", "+", "-")) or "*" in value or "?" in value


def _enabled(path: Path, selectors: list[str], base: Path, home: Path, *, explicit: bool = False) -> bool:
    patterns = [s for s in selectors if _is_pattern(s)]
    includes = [s for s in patterns if not s.startswith(("!", "+", "-"))]
    enabled = not (explicit and includes) or any(_matches(path, s, base, home) for s in includes)
    if any(_matches(path, s[1:], base, home) for s in patterns if s.startswith("!")):
        enabled = False
    if any(_exact(path, s[1:], base, home) for s in patterns if s.startswith("+")):
        enabled = True
    if any(_exact(path, s[1:], base, home) for s in patterns if s.startswith("-")):
        enabled = False
    return enabled


def _plain_paths(selectors: list[str], base: Path, home: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for value in selectors:
        if _is_pattern(value):
            continue
        path = _lexical(base / _normalize_pattern(value.strip(), home))
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(p for entries in discover_local_extensions(path).values() for p in entries)
    return tuple(paths)


def _resolve_local_states(
    *, home: Path, project: Path | None,
    overrides: dict[str, list[str]] | None = None,
) -> dict[str, LocalExtensionState]:
    """Resolve the loose universe once; project state includes global inheritance."""
    bases = {"global": _lexical(home / ".pi/agent")}
    if project is not None:
        bases["project"] = _lexical(project / ".pi")
    discovered = {scope: discover_local_extensions(base / "extensions") for scope, base in bases.items()}
    selectors = {
        scope: overrides[scope] if overrides is not None and scope in overrides
        else _pi_settings.read_extension_paths(scope=scope, home=home, project=project)
        for scope in bases
    }
    plain = {scope: _plain_paths(selectors[scope], base, home) for scope, base in bases.items()}

    def resolve(with_project: bool) -> dict[Path, bool]:
        # Native addResource is first-lexical-wins; final canonical dedup gives
        # project metadata priority over global metadata.
        resources: dict[Path, tuple[bool, str]] = {}
        scopes = ["project", "global"] if with_project and project is not None else ["global"]
        for explicit in (True, False):
            for scope in scopes:
                paths = plain[scope] if explicit else tuple(p for entries in discovered[scope].values() for p in entries)
                for path in paths:
                    resources.setdefault(path, (_enabled(path, selectors[scope], bases[scope], home, explicit=explicit), scope))
        seen: set[Path] = set()
        result: dict[Path, bool] = {}
        for path, (enabled, scope) in sorted(resources.items(), key=lambda item: item[1][1] != "project"):
            canonical = path.resolve()
            if canonical not in seen:
                seen.add(canonical)
                result[path] = enabled
        return result

    global_values = resolve(False)
    project_values = resolve(True) if project is not None else {}
    all_slugs = dict.fromkeys(slug for entries in discovered.values() for slug in entries)
    states = {}
    for slug in all_slugs:
        paths = tuple(dict.fromkeys(path for entries in discovered.values() for path in entries.get(slug, ())))
        states[slug] = LocalExtensionState(
            global_entries=tuple(LocalExtensionEntry(p, global_values[p]) for p in paths if p in global_values),
            project_entries=tuple(LocalExtensionEntry(p, project_values[p]) for p in paths if p in project_values),
            available_paths=paths,
        )
    return states


def read_local_extension_states(*, home: Path, project: Path | None) -> dict[str, LocalExtensionState]:
    return _resolve_local_states(home=home, project=project)


def read_local_extension_state(*, slug: str, home: Path, project: Path | None) -> LocalExtensionState:
    return read_local_extension_states(home=home, project=project).get(slug, LocalExtensionState())


@contextmanager
def _settings_lock(path: Path):
    """proper-lockfile's realpath:false protocol: mkdir <settings>.lock.

    Never steal an existing lock (including a stale/unknown lock). A busy lock
    is an actionable retry, not permission to overwrite another writer.
    """
    lock = Path(str(path) + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise PiSettingsError(f"{path}: settings are locked; retry Apply after Pi finishes saving") from exc
    try:
        yield
    finally:
        lock.rmdir()


def _write_settings(path: Path, data: dict[str, object]) -> None:
    # Follow an existing settings symlink rather than replacing that symlink.
    destination = path.resolve() if path.is_symlink() else path
    mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o600
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(data, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def set_local_extension_enabled(
    *, slug: str, enabled: bool, scope: Scope, home: Path,
    project: Path | None, expected_paths: tuple[Path, ...],
) -> None:
    """Apply a queued local intent, rejecting changed targets and busy settings."""
    path = _pi_settings.settings_path(scope=scope, home=home, project=project)
    try:
        with _settings_lock(path):
            state = read_local_extension_state(slug=slug, home=home, project=project)
            targets = state.paths_for(scope)
            if not expected_paths or set(targets) != set(expected_paths):
                raise PiSettingsError(f"{slug}: local entrypoints changed or disappeared; revert, refresh and queue again")
            data = _pi_settings._load(path)
            current = _pi_settings._string_list(data, "extensions", path)
            base = _lexical(path.parent)
            updated = [s for s in current if not any(_exact(p, s[1:] if s.startswith(("!", "+", "-")) else s, base, home) for p in targets)]
            auto_paths = {p for entries in discover_local_extensions(base / "extensions").values() for p in entries}
            inherited_paths = {entry.path for entry in state.global_entries} if scope == "project" else set()
            for target in targets:
                inherited = target in inherited_paths
                if (inherited or target not in auto_paths) and str(target) not in updated:
                    updated.append(str(target))
                pattern = str(target.relative_to(base)) if target.is_relative_to(base) and not inherited else str(target)
                updated.append(("+" if enabled else "-") + pattern)
            # Validate the effective result before committing. Competing lexical
            # references to one canonical source must never become successful no-ops.
            prospective = _resolve_local_states(home=home, project=project, overrides={scope: updated}).get(slug, LocalExtensionState())
            selected = prospective.global_entries if scope == "global" else prospective.project_entries
            if {e.path for e in selected} != set(targets) or any(e.enabled != enabled for e in selected):
                raise PiSettingsError(f"{slug}: conflicting native reference prevents this change; inspect Pi config")
            if current != updated:
                data["extensions"] = updated
                _write_settings(path, data)
    except OSError as exc:
        raise PiSettingsError(f"{path}: {exc}") from exc
