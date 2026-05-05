"""Dispatcher: orchestrates adapter.diff() output into atomic writes + prints.

Single writer-of-truth for MCP adapter actions. CLI commands (link/unlink/fix)
flow through `apply_link`; the dispatcher handles dry-run, atomic writes, and
the loud-print contract.

The dispatcher knows nothing about harness-specific details — that's the
adapter's job. It only knows: how to call adapter.diff(), how to write bytes
atomically, and what the loud-print contract looks like.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import IO, Iterable

from agent_toolkit.harness_adapters.base import (
    McpEntry,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)
from agent_toolkit.walker import extract_frontmatter


def _build_mcp_entries(toolkit_root: Path, slugs: Iterable[str]) -> list[McpEntry]:
    """Resolve a list of slugs to McpEntry instances.

    Skips slugs whose `mcps/<slug>/{config.json, README.md}` are not both present.
    Returns entries in the order slugs were requested (skipped slugs simply absent).
    """
    entries: list[McpEntry] = []
    for slug in slugs:
        mcp_dir = toolkit_root / "mcps" / slug
        config_path = mcp_dir / "config.json"
        readme_path = mcp_dir / "README.md"
        if not config_path.is_file() or not readme_path.is_file():
            continue
        inner = json.loads(config_path.read_text(encoding="utf-8"))
        fm = extract_frontmatter(readme_path) or {}
        mcp_spec = ((fm.get("spec") or {}).get("mcp")) or {}
        entries.append(McpEntry(name=slug, inner_config=inner, mcp_spec=mcp_spec))
    return entries


def apply_link(
    adapter,
    *,
    scope: Scope,
    project_root: Path,
    entries: list[McpEntry],
    dry_run: bool,
    stdout: IO[str],
    previously_allowed: set[str] = frozenset(),
    force: bool = False,  # noqa: ARG001 — reserved; not wired by any current adapter
) -> list[WriteAction]:
    """Reconcile adapter state to the desired entry set.

    Both `link` and `unlink` reduce to this single call; they differ only in
    how the allow-list YAML is mutated *before* the dispatch and in what's
    passed as `entries` and `previously_allowed`.

    `previously_allowed` is the set of names that were in the YAML allow-list
    before this dispatch's mutation. It defaults to empty (suitable for `fix`
    reconcile, which doesn't mutate the YAML). Forwarded to adapter.diff().

    For each entry, calls `adapter.can_install(entry)` first; CannotInstall
    propagates to the caller (the caller decides whether to swallow per-entry
    or fail the batch).

    In dry-run mode, prints `would-<op>: <path>` per non-`unchanged` action and
    makes no filesystem mutation.

    In real-run mode, writes bytes atomically and prints the op-specialised
    loud-print pair.

    Returns the list of WriteActions produced by the adapter (caller may use
    them for counters / reporting).
    """
    if isinstance(adapter, UnimplementedAdapter):
        # Should not be called for unimplemented adapters; the caller checks
        # first and prints the skip message. If it slips through, no-op
        # silently — better to surface the bug elsewhere than to print twice.
        return []

    # Pre-flight every entry. CannotInstall raises here.
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

    for act in actions:
        if act.op == "unchanged":
            continue
        _print_pre(act, stdout)
        _execute_action(act)
        _print_post(act, stdout)
    return actions


def _execute_action(act: WriteAction) -> None:
    if act.op in {"create", "update"}:
        if act.contents is None:
            raise RuntimeError(f"{act.op} action missing contents: {act.path}")
        _atomic_write_bytes(act.path, act.contents)
    elif act.op == "delete":
        try:
            act.path.unlink()
        except FileNotFoundError:
            pass
    elif act.op == "unchanged":
        return
    else:
        raise RuntimeError(f"unknown action op: {act.op}")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomic write: same-directory temp file + os.replace.

    Same-directory staging guarantees atomicity across filesystems.
    Creates parent dirs if missing. Cleans up the temp file on any error
    (so partial writes don't pollute the directory).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _print_pre(act: WriteAction, stdout: IO[str]) -> None:
    if act.op == "create":
        print(f"→ creating {act.path}", file=stdout)
    elif act.op == "update":
        print(f"→ updating {act.path}", file=stdout)
    elif act.op == "delete":
        print(f"→ deleting {act.path}", file=stdout)


def _print_post(act: WriteAction, stdout: IO[str]) -> None:
    if act.op == "create":
        print(f"✓ created {act.path} ({act.bytes_after}B)", file=stdout)
    elif act.op == "update":
        print(
            f"✓ updated {act.path} ({act.bytes_before}B → {act.bytes_after}B)",
            file=stdout,
        )
    elif act.op == "delete":
        print(f"✓ deleted {act.path} (was {act.bytes_before}B)", file=stdout)
