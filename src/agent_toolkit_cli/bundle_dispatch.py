"""Map one bundle member to its kind's real add+install sequence.

The kinds are heterogeneous (skill uses `--scope` (--agents defaults to standard, so it's omitted); agent/pi-extension
use `-g/-p`; pi-extension's `add` has no `--ref`). Rather than duplicate any
installer logic, dispatch builds the same argv a human would type, per kind, and
invokes the CLI in-process via Click's programmatic mode (`standalone_mode=False`),
reusing every kind's validation, clone, projection, and lock-write. `mcp` is
reserved but hard-fails until the mcp kind ships (#329).

Three hardening rules (resolved critical-review findings):
- F2 `already_present`: install_member reads the kind's library lock for the slug
  BEFORE add. If present with the same source, it returns "already_present" and
  skips add+install (so the orchestrator excludes it from the rollback set).
- F5 sentinel: a `--` end-of-options marker precedes every manifest-derived
  positional, so a crafted value can never be parsed by Click as a flag.
- F8 `--project`: each independent in-process main() call is a fresh Click parse
  with no inherited top-level flag, so when project scope is active dispatch
  prepends `["--project", str(project_root)]` to the child argv.
"""
from __future__ import annotations

from agent_toolkit_cli.bundle_manifest import BundleMember

INSTALLABLE_KINDS: tuple[str, ...] = ("skill", "agent", "pi-extension")

_MCP_NOT_READY = (
    "member {slug!r}: 'mcp' members require the mcp asset type, which is not "
    "yet available (tracked in #329). Remove the mcp member or wait for the "
    "mcp kind to ship."
)


class DispatchError(RuntimeError):
    """A member could not be dispatched/installed."""


def _invoke_cli(argv: list[str]) -> None:
    """Run the toolkit CLI in-process; raise on any failure (no sys.exit)."""
    from agent_toolkit_cli.cli import main

    main.main(args=argv, standalone_mode=False)


def _project_prefix(scope: str, project_root: str | None) -> list[str]:
    if scope == "project" and project_root:
        return ["--project", str(project_root)]
    return []


def _check_member(member: BundleMember) -> None:
    if member.asset_type == "mcp":
        raise DispatchError(_MCP_NOT_READY.format(slug=member.slug or member.source))
    if member.asset_type not in INSTALLABLE_KINDS:
        raise DispatchError(f"un-installable member type {member.asset_type!r}")


def _derive_slug(source: str) -> str:
    """Last path segment, mirroring each kind's default slug derivation."""
    return source.rstrip("/").split("/")[-1]


def resolve_member(member: BundleMember) -> None:
    """Dry-run check: a member that cannot possibly install fails here.

    v1 resolution is structural (type is installable, mcp rejected). Source/ref
    reachability is proven by the real add during install; validate does NOT
    probe the network (AC7). Kept minimal by design.
    """
    _check_member(member)


def _scope_flag(scope: str) -> str:
    return "-g" if scope == "global" else "-p"


def _skill_add_argv(member: BundleMember) -> list[str]:
    argv = ["skill", "add"]
    if member.slug:
        argv += ["--slug", member.slug]
    if member.ref:
        argv += ["--ref", member.ref]
    return [*argv, "--", member.source]


def _skill_install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    return ["skill", "install", "--scope", scope, "--", slug]


def _agent_add_argv(member: BundleMember) -> list[str]:
    argv = ["agent", "add"]
    if member.slug:
        argv += ["--slug", member.slug]
    if member.ref:
        argv += ["--ref", member.ref]
    return [*argv, "--", member.source]


def _agent_install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    return ["agent", "install", _scope_flag(scope), "--", slug]


def _pi_ext_add_argv(member: BundleMember) -> list[str]:
    argv = ["pi-extension", "add"]
    if member.slug:
        argv += ["--slug", member.slug]
    return [*argv, "--", member.source]


def _pi_ext_install_argv(member: BundleMember, scope: str) -> list[str]:
    slug = member.slug or _derive_slug(member.source)
    return ["pi-extension", "install", _scope_flag(scope), "--", slug]


_ADD_BUILDERS = {
    "skill": _skill_add_argv,
    "agent": _agent_add_argv,
    "pi-extension": _pi_ext_add_argv,
}
_INSTALL_BUILDERS = {
    "skill": _skill_install_argv,
    "agent": _agent_install_argv,
    "pi-extension": _pi_ext_install_argv,
}


def _skill_uninstall_argv(slug: str, scope: str) -> list[str]:
    # Rollback must fully undo add+install → `remove --force` (drops lock entry +
    # canonical + projections). `uninstall` is projection-only and would leave the
    # member in the library lock, breaking all-or-nothing (AC4). `remove` takes no
    # scope flag (it is library/global-level, like the add lock-precheck).
    return ["skill", "remove", "--force", "--", slug]


def _agent_uninstall_argv(slug: str, scope: str) -> list[str]:
    return ["agent", "remove", "--force", "--", slug]


def _pi_ext_uninstall_argv(slug: str, scope: str) -> list[str]:
    return ["pi-extension", "remove", "--force", "--", slug]


_UNINSTALL_BUILDERS = {
    "skill": _skill_uninstall_argv,
    "agent": _agent_uninstall_argv,
    "pi-extension": _pi_ext_uninstall_argv,
}


def _lock_has_member(member: BundleMember) -> bool:
    """F2: is this slug already in the kind's GLOBAL library lock at the same
    source? Returns False on any read error (treat as 'not present').
    """
    from agent_toolkit_cli import _paths_core
    from agent_toolkit_cli.skill_lock import read_lock

    binding = {
        "skill": _paths_core.SKILL_BINDING,
        "agent": _paths_core.AGENT_BINDING,
        "pi-extension": _paths_core.PI_EXTENSION_BINDING,
    }[member.asset_type]
    lock_path = _paths_core.library_lock_path_for_asset_type(binding)
    slug = member.slug or _derive_slug(member.source)
    try:
        lock = read_lock(lock_path)
    except (OSError, ValueError):
        return False
    entry = lock.skills.get(slug)
    if entry is None:
        return False
    return entry.source == member.source


def install_member(
    member: BundleMember,
    scope: str,
    project_root: str | None = None,
) -> str | None:
    """Add the member to the library, then project it at `scope`.

    Returns "already_present" if the lock-precheck (F2) finds the slug already in
    the library at the same source (add+install skipped); otherwise returns None
    after a real add+install. project_root threads the top-level --project (F8).
    """
    _check_member(member)
    if _lock_has_member(member):
        return "already_present"
    prefix = _project_prefix(scope, project_root)
    try:
        _invoke_cli(prefix + _ADD_BUILDERS[member.asset_type](member))
        _invoke_cli(prefix + _INSTALL_BUILDERS[member.asset_type](member, scope))
    except DispatchError:
        raise
    except (Exception, SystemExit) as exc:
        raise DispatchError(
            f"member {member.slug or member.source!r} ({member.asset_type}) "
            f"failed to install: {exc}"
        ) from exc
    return None


def uninstall_member(
    member: BundleMember,
    scope: str,
    project_root: str | None = None,
) -> None:
    """Roll back a member installed earlier this run (in-process).

    Uses `<kind> remove --force` (not `uninstall`) so the library lock entry
    and canonical are also removed — the true inverse of `add`+`install`.
    `remove` is library-level (no scope flag), so `--project` is not prepended.
    """
    _check_member(member)
    slug = member.slug or _derive_slug(member.source)
    try:
        _invoke_cli(_UNINSTALL_BUILDERS[member.asset_type](slug, scope))
    except (Exception, SystemExit) as exc:
        raise DispatchError(
            f"rollback of {slug!r} ({member.asset_type}) failed: {exc}"
        ) from exc
