"""Command install facade and harness adapter dispatch."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from agent_toolkit_cli._install_core import InstallError, InstallPlan, InstallResult, plan as _core_plan
from agent_toolkit_cli.command_adapters import INSTALLABLE_HARNESSES, SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.command_adapters.base import sidecar_path
from agent_toolkit_cli.command_lock import LockEntry, add_entry, read_lock, write_lock
from agent_toolkit_cli.command_paths import Scope, canonical_command_dir, library_lock_path, lock_file_path
from agent_toolkit_cli.skill_source import ParsedSource

COMMAND_SYNTHETIC_NAMES = frozenset({"standard-command"})


def _command_file(canonical: Path) -> Path:
    content = canonical / "COMMAND.md"
    if content.is_symlink() or not content.is_file():
        raise InstallError(f"{content}: COMMAND.md must be a regular file")
    return content


def _ordered_tokens(tokens: Iterable[str]) -> tuple[str, ...]:
    """Dedupe preserving order, with standard first when present."""
    ordered = list(dict.fromkeys(tokens))
    if "standard" in ordered:
        ordered = ["standard", *[t for t in ordered if t != "standard"]]
    return tuple(ordered)


def _normalize_to_standard(
    name: str,
    slug: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> str:
    """Return 'standard' when name's destination is the shared Standard slot."""
    if name == "standard":
        return name
    try:
        std_dest = get_adapter("standard").destination(
            slug, scope=scope, home=home, project=project,
        )
        dest = get_adapter(name).destination(
            slug, scope=scope, home=home, project=project,
        )
    except ValueError:
        return name
    if dest == std_dest:
        return "standard"
    return name


def ensure_project_command_canonical(*, slug: str, project: Path) -> bool:
    """Materialise the project canonical from the global library.

    Returns True only when this call created the project directory.
    Does not write lock state.
    """
    project_canonical = canonical_command_dir(slug, scope="project", project=project)
    if project_canonical.exists() or project_canonical.is_symlink():
        return False
    global_canonical = canonical_command_dir(slug, scope="global")
    source_file = _command_file(global_canonical)
    # Validate global COMMAND.md is regular (already enforced by _command_file).
    del source_file
    project_canonical.parent.mkdir(parents=True, exist_ok=True)
    try:
        project_canonical.symlink_to(global_canonical.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(global_canonical, project_canonical, symlinks=True)
    return True


def _project_entry_from_global(slug: str) -> LockEntry | None:
    global_entry = read_lock(library_lock_path()).skills.get(slug)
    if global_entry is None:
        return None
    return LockEntry(
        source=global_entry.source,
        source_type=global_entry.source_type,
        ref=global_entry.ref,
        command_path=global_entry.command_path,
        upstream_sha=None,
        local_sha=None,
        parent_url=global_entry.parent_url,
        read_only=global_entry.read_only,
        extras=dict(global_entry.extras),
        harnesses=(),
    )


def plan(
    *,
    slug: str,
    scope: Scope,
    source: ParsedSource | None = None,
    ref: str | None = None,
    target_agents: Iterable[str] = (),
    home: Path | None = None,
    project: Path | None = None,
) -> InstallPlan:
    targets = _ordered_tokens(
        _normalize_to_standard(n, slug, scope=scope, home=home, project=project)
        for n in target_agents
    )
    for name in targets:
        if name in COMMAND_SYNTHETIC_NAMES:
            raise InstallError(f"unsupported command harness: {name}")
        get_adapter(name)
    return _core_plan(
        slug=slug,
        scope=scope,
        source=source,
        ref=ref,
        target_agents=targets,
        home=home,
        project=project,
        canonical_dir_resolver=canonical_command_dir,
        standard_bundle_link=None,
        synthetic_names=COMMAND_SYNTHETIC_NAMES,
        current_linked_resolver=_current_linked_harnesses,
    )


def _current_linked_harnesses(
    *,
    slug: str,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    **_: object,
) -> tuple[str, ...]:
    """Report owned projections. Standard first; one destination = one token."""
    linked: list[str] = []
    seen_destinations: set[Path] = set()
    source_file: Path | None = None
    try:
        canonical = canonical_command_dir(slug, scope=scope, home=home, project=project)
        if (canonical / "COMMAND.md").is_file() and not (canonical / "COMMAND.md").is_symlink():
            source_file = canonical / "COMMAND.md"
    except (ValueError, OSError):
        source_file = None

    # Probe Standard first and reserve its destination before ownership check.
    try:
        std = get_adapter("standard")
        std_dest = std.destination(slug, scope=scope, home=home, project=project)
    except ValueError:
        std = None
        std_dest = None
    if std_dest is not None:
        seen_destinations.add(std_dest)
        if source_file is not None and std is not None:
            if std.is_installed(slug, source_file, scope=scope, home=home, project=project):
                linked.append("standard")

    for name in SUPPORTED_HARNESSES:
        try:
            adapter = get_adapter(name)
            dest = adapter.destination(slug, scope=scope, home=home, project=project)
        except ValueError:
            continue
        if dest in seen_destinations:
            continue
        if source_file is None:
            if dest.exists() or dest.is_symlink():
                linked.append(name)
            continue
        if adapter.is_installed(slug, source_file, scope=scope, home=home, project=project):
            linked.append(name)
    return tuple(linked)


def _snapshot_slot(dest: Path) -> tuple[bool, bool]:
    """Return (dest_existed, sidecar_existed) before a mutation."""
    dest_existed = dest.exists() or dest.is_symlink()
    side_existed = sidecar_path(dest).exists()
    return dest_existed, side_existed


def _rollback_created(
    created_new: list[Path],
    adopted_sidecars: list[Path],
    *,
    created_project_canonical: Path | None,
) -> None:
    for dest in reversed(created_new):
        try:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            sidecar_path(dest).unlink(missing_ok=True)
        except OSError:
            pass
    for side in adopted_sidecars:
        try:
            side.unlink(missing_ok=True)
        except OSError:
            pass
    if created_project_canonical is not None:
        try:
            if created_project_canonical.is_symlink():
                created_project_canonical.unlink(missing_ok=True)
            elif created_project_canonical.exists():
                shutil.rmtree(created_project_canonical)
        except OSError:
            pass


def apply(
    plan: InstallPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
    env: dict[str, str] | None = None,
    command_dir_resolver=canonical_command_dir,
) -> InstallResult:
    del env  # reserved for future clone-on-install
    created_project_canonical: Path | None = None
    created_new: list[Path] = []
    adopted_sidecars: list[Path] = []
    created: list[Path] = []
    removed: list[Path] = []
    successful_add: list[str] = []
    successful_remove: list[str] = []

    try:
        if plan.scope == "project" and plan.add_agents:
            if project is None:
                raise ValueError("project scope requires project")
            if ensure_project_command_canonical(slug=plan.slug, project=project):
                created_project_canonical = command_dir_resolver(
                    plan.slug, scope="project", home=home, project=project,
                )

        canonical = command_dir_resolver(
            plan.slug, scope=plan.scope, home=home, project=project,
        )
        source_file = (
            _command_file(canonical)
            if plan.add_agents or canonical.exists() or canonical.is_symlink()
            else None
        )

        # Normalize and dedupe tokens.
        add_tokens = _ordered_tokens(
            _normalize_to_standard(n, plan.slug, scope=plan.scope, home=home, project=project)
            for n in plan.add_agents
            if n not in COMMAND_SYNTHETIC_NAMES
        )
        remove_tokens = _ordered_tokens(
            _normalize_to_standard(n, plan.slug, scope=plan.scope, home=home, project=project)
            for n in plan.remove_agents
            if n not in COMMAND_SYNTHETIC_NAMES
        )

        # Non-standard adds first; Standard last (adopting action after fallible writes).
        ordered_adds = [n for n in add_tokens if n != "standard"]
        if "standard" in add_tokens:
            ordered_adds.append("standard")

        for name in ordered_adds:
            if name in COMMAND_SYNTHETIC_NAMES:
                raise InstallError(f"unsupported command harness: {name}")
            if source_file is None:
                raise InstallError(f"{canonical / 'COMMAND.md'}: COMMAND.md must be a regular file")
            adapter = get_adapter(name)
            dest = adapter.destination(
                plan.slug, scope=plan.scope, home=home, project=project,
            )
            dest_existed, side_existed = _snapshot_slot(dest)
            if name in {"claude-code", "pi", "codex", "standard"}:
                result_dest = adapter.install(
                    plan.slug, source_file, scope=plan.scope, home=home, project=project,
                )
            else:
                result_dest = adapter.install(
                    plan.slug, source_file, scope=plan.scope, home=home, project=project,
                )
            created.append(result_dest)
            successful_add.append(name)
            if not dest_existed:
                created_new.append(result_dest)
            elif not side_existed and sidecar_path(result_dest).exists():
                # Adoption: only the new sidecar is rollback-owned.
                adopted_sidecars.append(sidecar_path(result_dest))

        for name in remove_tokens:
            adapter = get_adapter(name)
            try:
                if name in {"claude-code", "pi", "codex"}:
                    gone = adapter.uninstall(
                        plan.slug,
                        scope=plan.scope,
                        home=home,
                        project=project,
                        canonical=source_file,
                    )
                elif name == "standard":
                    gone = adapter.uninstall(
                        plan.slug,
                        source_file,
                        scope=plan.scope,
                        home=home,
                        project=project,
                    )
                else:
                    gone = adapter.uninstall(
                        plan.slug, scope=plan.scope, home=home, project=project,
                    )
            except ValueError:
                continue
            if gone is not None:
                removed.append(gone)
                successful_remove.append(name)

        # Merge actual successful tokens into the active lock entry once.
        lock_path = lock_file_path(scope=plan.scope, home=home, project=project)
        lock = read_lock(lock_path)
        existing = lock.skills.get(plan.slug)
        lock_action: str = "unchanged"

        if successful_add or successful_remove:
            if existing is not None:
                current = list(existing.harnesses)
                # Normalize any legacy claude-code tokens on mutation.
                current = [
                    "standard" if t == "claude-code" else t for t in current
                ]
                for t in successful_add:
                    if t not in current:
                        current.append(t)
                for t in successful_remove:
                    if t in current:
                        current.remove(t)
                updated = LockEntry(
                    source=existing.source,
                    source_type=existing.source_type,
                    ref=existing.ref,
                    command_path=existing.command_path,
                    upstream_sha=existing.upstream_sha,
                    local_sha=existing.local_sha,
                    parent_url=existing.parent_url,
                    read_only=existing.read_only,
                    extras=dict(existing.extras),
                    harnesses=_ordered_tokens(current),
                )
                write_lock(lock_path, add_entry(lock, plan.slug, updated))
                lock_action = "updated"
            elif plan.scope == "project" and successful_add:
                derived = _project_entry_from_global(plan.slug)
                if derived is not None:
                    derived = LockEntry(
                        source=derived.source,
                        source_type=derived.source_type,
                        ref=derived.ref,
                        command_path=derived.command_path,
                        upstream_sha=None,
                        local_sha=None,
                        parent_url=derived.parent_url,
                        read_only=derived.read_only,
                        extras=dict(derived.extras),
                        harnesses=_ordered_tokens(successful_add),
                    )
                    write_lock(lock_path, add_entry(lock, plan.slug, derived))
                    lock_action = "added"
            elif plan.scope == "global" and successful_add and existing is None:
                # Global library entry may already exist without harnesses;
                # if no entry at all (manual canonical), leave untracked.
                pass

        # If existing global entry and we mutated, already handled above.
        # Refresh harnesses on global entry that existed with empty field.
        if (
            plan.scope == "global"
            and existing is not None
            and (successful_add or successful_remove)
        ):
            pass  # already written above

        return InstallResult(
            plan=plan,
            canonical_path=canonical,
            created=tuple(created),
            removed=tuple(removed),
            skipped=(),
            lock_action=lock_action,  # type: ignore[arg-type]
        )
    except Exception:
        _rollback_created(
            created_new,
            adopted_sidecars,
            created_project_canonical=created_project_canonical,
        )
        raise


def install(
    slug: str,
    agents: Iterable[str],
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> InstallResult:
    p = InstallPlan(
        slug=slug,
        scope=scope,
        source=None,
        ref=None,
        add_agents=tuple(agents),
        remove_agents=(),
    )
    return apply(p, home=home, project=project)


def uninstall(
    slug: str,
    agents: Iterable[str] = (),
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> tuple[Path, ...]:
    targets = tuple(agents) if agents else INSTALLABLE_HARNESSES
    p = InstallPlan(
        slug=slug,
        scope=scope,
        source=None,
        ref=None,
        add_agents=(),
        remove_agents=targets,
    )
    return apply(p, home=home, project=project).removed
