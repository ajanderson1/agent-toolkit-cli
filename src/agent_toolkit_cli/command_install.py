"""Command install facade and harness adapter dispatch."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from agent_toolkit_cli._install_core import InstallError, InstallPlan, InstallResult, plan as _core_plan
from agent_toolkit_cli.command_adapters import SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.command_paths import Scope, canonical_command_dir
from agent_toolkit_cli.skill_source import ParsedSource

COMMAND_SYNTHETIC_NAMES = frozenset({"standard-command"})


def _command_file(canonical: Path) -> Path:
    content = canonical / "COMMAND.md"
    if content.is_symlink() or not content.is_file():
        raise InstallError(f"{content}: COMMAND.md must be a regular file")
    return content


def plan(*, slug: str, scope: Scope, source: ParsedSource | None = None, ref: str | None = None, target_agents: Iterable[str] = (), home: Path | None = None, project: Path | None = None) -> InstallPlan:
    targets = tuple(dict.fromkeys(target_agents))
    for name in targets:
        if name in COMMAND_SYNTHETIC_NAMES:
            raise InstallError(f"unsupported command harness: {name}")
        get_adapter(name)
    return _core_plan(slug=slug, scope=scope, source=source, ref=ref, target_agents=targets, home=home, project=project, canonical_dir_resolver=canonical_command_dir, standard_bundle_link=None, synthetic_names=COMMAND_SYNTHETIC_NAMES, current_linked_resolver=_current_linked_harnesses)


def _current_linked_harnesses(*, slug: str, scope: Scope, home: Path | None, project: Path | None, **_: object) -> tuple[str, ...]:
    linked: list[str] = []
    for name in SUPPORTED_HARNESSES:
        try:
            dest = get_adapter(name).destination(slug, scope=scope, home=home, project=project)
        except ValueError:
            continue
        if dest.exists() or dest.is_symlink():
            linked.append(name)
    return tuple(linked)


def apply(plan: InstallPlan, *, home: Path | None = None, project: Path | None = None, env: dict[str, str] | None = None, command_dir_resolver=canonical_command_dir) -> InstallResult:
    canonical = command_dir_resolver(plan.slug, scope=plan.scope, home=home, project=project)
    source_file = _command_file(canonical) if plan.add_agents or canonical.exists() else None
    created: list[Path] = []
    removed: list[Path] = []
    try:
        for name in plan.add_agents:
            if name in COMMAND_SYNTHETIC_NAMES:
                raise InstallError(f"unsupported command harness: {name}")
            if source_file is None:
                raise InstallError(f"{canonical / 'COMMAND.md'}: COMMAND.md must be a regular file")
            adapter = get_adapter(name)
            dest = adapter.install(plan.slug, source_file, scope=plan.scope, home=home, project=project)
            created.append(dest)
        for name in plan.remove_agents:
            if name in COMMAND_SYNTHETIC_NAMES:
                continue
            adapter = get_adapter(name)
            try:
                if name in {"claude-code", "pi", "codex"}:
                    gone = adapter.uninstall(plan.slug, scope=plan.scope, home=home, project=project, canonical=source_file)
                else:
                    gone = adapter.uninstall(plan.slug, scope=plan.scope, home=home, project=project)
            except ValueError:
                continue
            if gone is not None:
                removed.append(gone)
    except Exception:
        for dest in reversed(created):
            try:
                if dest.exists() or dest.is_symlink():
                    dest.unlink()
                side = dest.with_suffix(dest.suffix + ".attk")
                side.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return InstallResult(plan=plan, canonical_path=canonical, created=tuple(created), removed=tuple(removed), skipped=(), lock_action="unchanged")


def install(slug: str, agents: Iterable[str], *, scope: Scope, home: Path | None = None, project: Path | None = None) -> InstallResult:
    p = InstallPlan(slug=slug, scope=scope, source=None, ref=None, add_agents=tuple(agents), remove_agents=())
    return apply(p, home=home, project=project)


def uninstall(slug: str, agents: Iterable[str] = (), *, scope: Scope, home: Path | None = None, project: Path | None = None) -> tuple[Path, ...]:
    targets = tuple(agents) if agents else SUPPORTED_HARNESSES
    p = InstallPlan(slug=slug, scope=scope, source=None, ref=None, add_agents=(), remove_agents=targets)
    return apply(p, home=home, project=project).removed
