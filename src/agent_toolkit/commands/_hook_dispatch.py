"""Dispatcher: orchestrates CodexHookAdapter.diff() output into atomic writes + chmod.

Mirrors _mcp_dispatch.apply_link but typed for HookEntry. Reuses the atomic
write engine and loud-print contract from _mcp_dispatch.

The dispatcher is the boundary between the toolkit source-of-truth (where
hooks/<slug>/ lives) and the harness-projected output (script_root/<slug>/).
The adapter never reads the toolkit directory.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import IO, Iterable

import yaml

from agent_toolkit.harness_adapters.base import (
    HookEntry,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)
from agent_toolkit.commands._mcp_dispatch import (
    _atomic_write_bytes,
    _print_post,
    _print_pre,
)


def _build_hook_entries(toolkit_root: Path, slugs: Iterable[str]) -> list[HookEntry]:
    """Resolve slugs → HookEntry by reading hooks/<slug>/.meta.yaml + the script.

    Skips slugs whose hooks/<slug>/.meta.yaml is not present. Each entry's
    `command` is resolved to an absolute destination path under
    $HOME/.codex/agent-toolkit-hooks/<slug>/<command>.
    """
    home = Path(os.environ.get("HOME", ""))
    script_root = home / ".codex" / "agent-toolkit-hooks"

    entries: list[HookEntry] = []
    for slug in slugs:
        hook_dir = toolkit_root / "hooks" / slug
        meta_path = hook_dir / ".meta.yaml"
        if not meta_path.is_file():
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        spec_hook = ((meta.get("spec") or {}).get("hook")) or {}
        command_rel = spec_hook.get("command")
        if not command_rel:
            continue

        # Source script (in toolkit) and destination script (under script_root).
        src_script = hook_dir / command_rel
        if not src_script.is_file():
            continue
        dest_script = script_root / slug / command_rel
        script_bytes = src_script.read_bytes()

        entries.append(HookEntry(
            name=slug,
            events=tuple(spec_hook.get("events") or ()),
            command=str(dest_script),
            matcher=spec_hook.get("matcher"),
            timeout=spec_hook.get("timeout"),
            async_=bool(spec_hook.get("async", False)),
            status_message=spec_hook.get("status_message"),
            script_files={dest_script: script_bytes},
        ))
    return entries


def apply_link(
    adapter,
    *,
    scope: Scope,
    project_root: Path,
    entries: list[HookEntry],
    dry_run: bool,
    stdout: IO[str],
    previously_allowed: set[str] = frozenset(),
) -> list[WriteAction]:
    """Reconcile adapter state to the desired hook entry set.

    Pre-flight every entry (CannotInstall propagates). In dry-run, prints
    `would-<op>: <path>` per non-unchanged action. In real-run, writes
    bytes atomically, chmods scripts under script_root to 0o755, and
    prints the loud-print contract pair.
    """
    if isinstance(adapter, UnimplementedAdapter):
        return []

    for entry in entries:
        adapter.can_install(entry)

    actions = adapter.diff(
        scope, project_root, entries,
        previously_allowed=previously_allowed,
    )

    if dry_run:
        for act in actions:
            if act.op == "unchanged":
                continue
            print(f"would-{act.op}: {act.path}", file=stdout)
        return actions

    script_root = adapter.script_root(scope, project_root)

    for act in actions:
        if act.op == "unchanged":
            continue
        _print_pre(act, stdout)
        _execute_action(act, script_root)
        _print_post(act, stdout)
    return actions


def _execute_action(act: WriteAction, script_root: Path | None) -> None:
    if act.op in {"create", "update"}:
        if act.contents is None:
            raise RuntimeError(f"{act.op} action missing contents: {act.path}")
        _atomic_write_bytes(act.path, act.contents)
        # Chmod 0o755 if the path lives under script_root.
        if script_root is not None and _path_under(act.path, script_root):
            os.chmod(act.path, 0o755)
    elif act.op == "delete":
        if act.path.is_dir():
            try:
                act.path.rmdir()  # only works if empty; files were deleted earlier
            except (FileNotFoundError, OSError):
                pass
        else:
            try:
                act.path.unlink()
            except FileNotFoundError:
                pass


def _path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
