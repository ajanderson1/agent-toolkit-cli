"""MCP install facade: apply / uninstall / remove across harness adapters.

apply() installs one library MCP into N harnesses, writes the lock, and rolls
back projections made THIS CALL if a later adapter fails (mirrors
agent_install.apply()'s rollback contract). uninstall() removes harness
projections (non-destructive: library + other-scope locks untouched). remove()
is the destructive verb; for a library-sourced kind it equals uninstalling the
slug from every harness recorded in the lock (the library entry itself is kept).

Facade safety duties (spec Rules 3+5, #329 critical review):
  - installed-harness sentinel: a harness whose sentinel dir is absent at the
    write scope is warned-and-skipped (exit 0), never mkdir-p'd into existence.
  - running-claude guard: a global-scope claude-code write is refused when a
    `claude` process is detected, unless force=True (~/.claude.json is live state).
  - hand-rolled collision: upserting over a same-name entry NOT in our lock
    prints a loud warning (manage-by-name is correct; the user must see it).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.mcp_adapters import get_adapter
from agent_toolkit_cli.mcp_library import load_mcp_asset
from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    collapse_covered,
    lock_path_for_scope,
    read_lock,
    remove_entry,
    upsert_entry,
    write_lock,
)
from agent_toolkit_cli.mcp_standard import mcp_standard_covered


class RunningClaudeError(InstallError):
    """A global-scope claude-code write was refused: a claude process is running."""


@dataclass(frozen=True)
class ApplyResult:
    """Structured outcome of apply() — lets the CLI render precisely without
    re-deriving state. The failure path raises instead of returning this."""

    installed: list[str]    # harnesses actually projected this call
    skipped: list[str]      # harnesses skipped (sentinel absent)
    collisions: list[str]   # harnesses where a hand-rolled entry was overwritten


def _loud(msg: str) -> None:
    """Facade output → STDERR, keeping stdout clean for the CLI layer to own
    (mirrors bundle_install.py:111 `err=True` and the agent adapters)."""
    print(msg, file=sys.stderr)


def _sentinel_present(harness: str, *, scope: str, home: Path) -> bool:
    """Is `harness` installed (its sentinel dir present) at this write scope?

    A harness whose sentinel is absent is treated as not-installed and skipped
    (never mkdir-p'd into existence). Sentinels are a GLOBAL-scope concern: they
    mark whether the harness is installed on THIS MACHINE, so its HOME-rooted
    config file (~/.claude.json, ~/.codex/config.toml, …) is a real target.

    At PROJECT scope the config target is a project-rooted file (.mcp.json,
    .codex/config.toml) that serves the project regardless of any per-machine
    install — so the sentinel does not gate a project write. Pi makes this
    explicit (the shared .mcp.json serves every host at project scope); the
    same logic applies to every harness, hence the blanket project short-circuit.
    """
    if scope == "project":
        return True  # project-rooted config file; not a per-machine install marker
    if harness == "claude-code":
        return (home / ".claude").is_dir()
    if harness == "codex":
        return (home / ".codex").is_dir()
    if harness == "opencode":
        return (home / ".config" / "opencode").is_dir()
    if harness == "pi":
        # Pi is adapter-gated at USER scope: its sentinel is the pi-mcp-adapter
        # extension, NOT just ~/.pi.
        return (home / ".pi" / "agent" / "npm" / "node_modules" / "pi-mcp-adapter").is_dir()
    return True  # unknown harness: do not block (get_adapter will reject it)


def _claude_is_running() -> bool:
    """Best-effort: is a `claude` process running? Monkeypatched in tests."""
    if shutil.which("pgrep") is None:
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-x", "claude"], capture_output=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def apply(
    *,
    slug: str,
    harnesses: list[str],
    scope: str,
    library_root: Path,
    home: Path,
    project: Path | None = None,
    force: bool = False,
) -> ApplyResult:
    """Install `slug` into each harness. Atomic across harnesses: roll back on failure.

    - Harnesses whose sentinel is absent at this scope are warned-and-skipped.
    - A global-scope claude-code write is refused if a claude process is running
      (unless force=True).
    - Upserting over a same-name entry not in our lock warns loudly.

    Returns an ApplyResult on the success path; the failure path rolls back and
    re-raises (returns nothing).
    """
    asset = load_mcp_asset(library_root, slug)
    lock_path = lock_path_for_scope(scope, home=home, project=project)
    lock = read_lock(lock_path)

    done: list[str] = []
    skipped: list[str] = []
    collisions: list[str] = []
    try:
        for harness in harnesses:
            if not _sentinel_present(harness, scope=scope, home=home):
                _loud(f"{harness} does not appear to be installed; skipping")
                skipped.append(harness)
                continue
            # Running-claude guard: global-scope claude-code only.
            if harness == "claude-code" and scope == "global" and not force:
                if _claude_is_running():
                    raise RunningClaudeError(
                        "refusing to write ~/.claude.json while a claude process "
                        "is running (it rewrites this file continuously and your "
                        "MCP entry could be lost). Quit claude or re-run with --force."
                    )
            adapter = get_adapter(harness)
            target = adapter.config_target(scope=scope, home=home, project=project)
            # Hand-rolled collision: entry exists but not tracked by us.
            already = adapter.is_installed(slug, scope=scope, home=home, project=project)
            tracked = any(e.harness == harness for e in lock.get(slug, []))
            if already and not tracked:
                _loud(
                    f"WARNING: overwriting existing hand-rolled entry '{slug}' in "
                    f"{target} — this entry was not previously managed by agent-toolkit"
                )
                collisions.append(harness)
            _loud(f"→ writing {target}")
            try:
                adapter.install(slug, asset.inner_config, scope=scope, home=home, project=project)
            except InstallError as exc:
                _loud(f"{harness}: {exc}; skipping")
                skipped.append(harness)
                continue
            _loud(f"✓ wrote {target}")
            lock = upsert_entry(lock, McpLockEntry(
                slug=slug, harness=harness,
                source=asset.install_method or "unknown",
                pin=asset.resolved_version,
            ))
            # #399 collapse-on-install: writing `standard` drops the covered
            # legacy rows (claude-code/pi) for this slug, folded into the SAME
            # lock object written once below — so the 3-row state never persists.
            if harness == "standard" and scope == "project":
                lock = collapse_covered(lock, slug, mcp_standard_covered("project"))
            done.append(harness)
        write_lock(lock_path, lock)
    except BaseException:
        # Roll back every projection made this call (newest-first, LIFO unwind);
        # do not write a partial lock. F9 (mirrors bundle_install._rollback): a
        # rollback failure is WARNED (never swallowed) and its harness collected,
        # so a stray projection with no lock entry can never go invisible.
        failed_rollbacks: list[str] = []
        for harness in reversed(done):
            try:
                get_adapter(harness).uninstall(slug, scope=scope, home=home, project=project)
                _loud(f"↩ rolled back {harness}:{slug}")
            except Exception as rb_exc:  # rollback must not mask the original error
                _loud(f"warning: rollback of {harness}:{slug} failed: {rb_exc}")
                failed_rollbacks.append(harness)
        if failed_rollbacks:
            _loud(
                f"NOTE: rollback failed for {', '.join(failed_rollbacks)} — manual "
                "cleanup may be needed (orphan projection(s) with no lock entry)."
            )
        # Re-raise the ORIGINAL error (bare) so the failure still propagates with
        # its own traceback; the warnings above are additive, not a replacement.
        raise

    return ApplyResult(installed=done, skipped=skipped, collisions=collisions)


def uninstall(
    *,
    slug: str,
    harnesses: list[str],
    scope: str,
    library_root: Path,
    home: Path,
    project: Path | None = None,
    force: bool = False,
) -> None:
    """Remove `slug`'s projection from each named harness. Non-destructive:
    the library and any other-scope lock are untouched.

    Running-claude guard (symmetric with apply(); spec AC9 "before ANY
    global-scope claude-code write"): rewriting ~/.claude.json while a claude
    process is live is the same lost-update hazard whether we add or remove an
    entry. If any global-scope claude-code uninstall would happen and a claude
    process is detected, refuse BEFORE doing ANY of the uninstalls (mirrors
    apply()'s pre-write guard) unless force=True.

    (library_root is accepted for facade-uniform call sites; uninstall/remove
    don't read it.)"""
    if (
        not force
        and scope == "global"
        and "claude-code" in harnesses
        and _claude_is_running()
    ):
        raise RunningClaudeError(
            "refusing to write ~/.claude.json while a claude process is running "
            "(it rewrites this file continuously and a concurrent removal could be "
            "lost). Quit claude or re-run with --force."
        )
    lock_path = lock_path_for_scope(scope, home=home, project=project)
    lock = read_lock(lock_path)
    for harness in harnesses:
        adapter = get_adapter(harness)
        target = adapter.config_target(scope=scope, home=home, project=project)
        _loud(f"→ removing {slug} from {target}")
        adapter.uninstall(slug, scope=scope, home=home, project=project)
        lock = remove_entry(lock, slug=slug, harness=harness)
    write_lock(lock_path, lock)


def remove(
    *,
    slug: str,
    scope: str,
    library_root: Path,
    home: Path,
    project: Path | None = None,
    force: bool = False,
) -> None:
    """Destructive verb: uninstall `slug` from EVERY harness recorded in the lock.

    For a library-sourced kind there is no owned canonical store to delete (the
    library is the source of truth), so remove == full-fan-out uninstall. Kept as
    a distinct verb to preserve the kind-wide non-destructive(uninstall) /
    destructive(remove) contract. The library entry is NOT deleted here.

    Delegates to uninstall(), threading `force` through so the running-claude
    guard on a global-scope claude-code removal is symmetric with apply().

    (library_root is accepted for facade-uniform call sites; uninstall/remove
    don't read it.)
    """
    lock_path = lock_path_for_scope(scope, home=home, project=project)
    lock = read_lock(lock_path)
    harnesses = [e.harness for e in lock.get(slug, [])]
    if not harnesses:
        _loud(f"{slug}: nothing to remove (no lock entry at {scope} scope)")
        return
    uninstall(
        slug=slug, harnesses=harnesses, scope=scope,
        library_root=library_root, home=home, project=project, force=force,
    )
