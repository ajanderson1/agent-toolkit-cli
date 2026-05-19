"""Single source of truth for the (harness, asset-kind) support matrix.

The matrix encodes which (harness, kind) pairs the toolkit can currently
project to a real on-disk slot. Adding a row here is the only place a new
adapter slot needs declaring; consumers (`_link_lib`, `_list_json`,
`commands/unlink`, `doctor/*`) read from here.

Issue #30: silent-skip on unsupported pairs is now a structured raise.
Remaining matrix gaps tracked individually: #74 (codex MCP HTTP transport),
#75 (pi/agent dual-target), #53 (Gemini CLI as fifth harness).
#140 (codex, agent) — now supported.
"""
from __future__ import annotations

import os
from pathlib import Path

import click

ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "gemini", "pi")
ALL_KINDS: tuple[str, ...] = (
    "skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension",
)

_USER_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       "{home}/.claude/skills",
    ("claude", "agent"):       "{home}/.claude/agents",
    ("claude", "command"):     "{home}/.claude/commands",
    # ("claude", "hook"): intentionally absent — no ClaudeHookAdapter exists
    # yet (see #123). Leaving the row would advertise a supported pair while
    # `link` silently no-ops (allowlist gets edited but no script is
    # materialised and ~/.claude/settings.json is never written).
    ("claude", "plugin"):      "{home}/.claude/plugins",
    ("codex", "agent"):        "{home}/.codex/agents",
    ("codex", "skill"):        "{home}/.codex/skills",
    ("codex", "hook"):         "{home}/.codex/agent-toolkit-hooks",  # config_file+folder
    ("opencode", "skill"):     "{home}/.config/opencode/skills",
    ("opencode", "agent"):     "{home}/.config/opencode/agents",
    ("opencode", "command"):   "{home}/.config/opencode/commands",
    ("gemini", "skill"):       "{home}/.gemini/skills",
    ("gemini", "agent"):       "{home}/.gemini/agents",
    ("gemini", "command"):     "{home}/.gemini/commands",
    ("pi", "skill"):           "{home}/.pi/agent/skills",
    ("pi", "agent"):           "{home}/.pi/agent/agents",
    ("pi", "pi-extension"):    "{home}/.pi/agent/extensions",
}
_PROJECT_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       ".claude/skills",
    ("claude", "agent"):       ".claude/agents",
    ("claude", "command"):     ".claude/commands",
    # ("claude", "hook"): see _USER_TARGETS — unsupported until adapter lands (#123).
    ("claude", "plugin"):      ".claude/plugins",
    ("codex", "agent"):        ".codex/agents",
    ("codex", "skill"):        ".codex/skills",
    ("opencode", "skill"):     ".opencode/skills",
    ("opencode", "agent"):     ".opencode/agents",
    ("opencode", "command"):   ".opencode/commands",
    ("gemini", "skill"):       ".gemini/skills",
    ("gemini", "agent"):       ".gemini/agents",
    ("gemini", "command"):     ".gemini/commands",
    # Pi project-scope: pi core reads from <cwd>/.pi/{skills,extensions} (no
    # /agent/ infix). User-scope keeps the .pi/agent/ prefix because pi's
    # globalBaseDir == ~/.pi/agent. See package-manager.js:669-686.
    ("pi", "skill"):           ".pi/skills",
    ("pi", "pi-extension"):    ".pi/extensions",
    # Pi agents are loaded by the third-party `pi-subagents` extension, not
    # Pi core. At project scope it reads BOTH `.pi/agents/` and `.agents/`
    # (no /agent/ infix at project scope). Primary stays under `.pi/`; the
    # `.agents/` mirror is added via _PROJECT_TARGET_ALIASES.
    ("pi", "agent"):           ".pi/agents",
}

# Alias targets: additional slot directories per (harness, kind) that the
# linker writes to and unlink/list/doctor read from. The primary target in
# _USER_TARGETS / _PROJECT_TARGETS stays the source of truth for is_supported
# and the singular `slot_dir` / `harness_target_dir` helpers; alias targets
# expose secondary slots that some harnesses also auto-discover.
#
# Currently used only by `(pi, agent)`: `pi-subagents` reads both the legacy
# `~/.pi/agent/agents/` and the new `~/.agents/` (and project equivalents).
_USER_TARGET_ALIASES: dict[tuple[str, str], list[str]] = {
    ("pi", "agent"): ["{home}/.agents"],
}
_PROJECT_TARGET_ALIASES: dict[tuple[str, str], list[str]] = {
    ("pi", "agent"): [".agents"],
}

# Derived: SUPPORTED_PAIRS = the set of (harness, kind) pairs with adapter slots.
# Derived from _USER_TARGETS; _PROJECT_TARGETS is a subset (tested in tests/test_support.py).
SUPPORTED_PAIRS: frozenset[tuple[str, str]] = frozenset(_USER_TARGETS.keys())

# Cell statuses that count as "linked at this (scope, harness)" — the union
# of the three states the inventory builder emits when an asset has a real
# slot occupation (symlink, hook entry, or MCP entry). Imported by:
#   - commands/_list_json.py        (user_scope_covered)
#   - commands/list.py              (text-mode render)
#   - doctor/user_scope_coverage.py
#   - agent_toolkit_tui/widgets/asset_grid.py
USER_LINKED_STATUSES: frozenset[str] = frozenset(
    {"linked", "linked-matches", "linked-drifted"}
)


class UnsupportedPair(Exception):
    """Raised when an apply path is asked to act on a (harness, kind) pair
    that has no adapter slot in the support matrix.

    Carry the pair on the exception so callers can format messages or
    surface them in structured CLI errors.
    """

    def __init__(self, harness: str, kind: str) -> None:
        self.harness = harness
        self.kind = kind
        super().__init__(
            f"unsupported (harness, kind) pair: ({harness!r}, {kind!r})"
        )


def is_supported(harness: str, kind: str, scope: str | None = None) -> bool:
    """True iff `(harness, kind)` has a real adapter slot in the matrix.

    With `scope=None` (default), returns True if the pair has a slot at *any*
    scope — i.e., membership in `SUPPORTED_PAIRS`. This is the back-compat
    answer used by allow-list/validate code paths that operate before a scope
    is in scope.

    With `scope="user"` or `scope="project"`, returns True only if the pair
    has a slot at *that* scope. Use this in projection-time code paths
    (linker iteration loops, etc.) so per-scope-only entries (e.g.
    `("pi","agent")` at user scope only) are skipped cleanly instead of
    falling through to a `harness_target_dir → None → RuntimeError`.

    Any other scope value returns False.
    """
    if scope is None:
        return (harness, kind) in SUPPORTED_PAIRS
    if scope == "user":
        return (harness, kind) in _USER_TARGETS
    if scope == "project":
        return (harness, kind) in _PROJECT_TARGETS
    return False


def supported_kinds_for(harness: str) -> tuple[str, ...]:
    """Return the kinds the given harness supports, in `ALL_KINDS` order."""
    return tuple(k for k in ALL_KINDS if (harness, k) in SUPPORTED_PAIRS)


def validate_pair(ctx: click.Context, harness: str, kind: str) -> None:
    """Exit 2 with a structured stderr message if the pair is unsupported.

    Mirrors the shape of `_link_lib.validate_harness` so Click subcommands
    can reuse it consistently.
    """
    if is_supported(harness, kind):
        return
    supported = supported_kinds_for(harness)
    if supported:
        hint = f"supported kinds for {harness!r}: " + " ".join(supported)
    else:
        hint = f"{harness!r} has no supported kinds"
    click.echo(
        f"unsupported (harness, kind) pair: ({harness!r}, {kind!r}) — {hint}",
        err=True,
    )
    ctx.exit(2)


def slot_dir(
    harness: str,
    kind: str,
    scope: str,
    project_root: Path,
) -> Path | None:
    """Return the absolute slot directory for a `(harness, kind, scope)` triple,
    or `None` if the pair is unsupported. Mirrors the prior
    `_list_json._slot_dir` helper.

    This returns the PRIMARY slot only. For (harness, kind) pairs with alias
    targets (e.g. `(pi, agent)` which is mirrored at `~/.agents/`), use
    `slot_dirs()` instead.
    """
    home = Path(os.environ.get("HOME", ""))
    if scope == "user":
        tmpl = _USER_TARGETS.get((harness, kind))
        return Path(tmpl.format(home=str(home))) if tmpl else None
    rel = _PROJECT_TARGETS.get((harness, kind))
    return (project_root / rel) if rel else None


def slot_dirs(
    harness: str,
    kind: str,
    scope: str,
    project_root: Path,
) -> list[Path]:
    """Return all slot directories for a `(harness, kind, scope)` triple —
    the primary first, then any aliases.

    Returns `[]` when the pair is unsupported at this scope. Used by code that
    must write to / read from EVERY known slot (linker, unlinker, list, doctor)
    rather than just the primary.
    """
    primary = slot_dir(harness, kind, scope, project_root)
    if primary is None:
        return []
    home = Path(os.environ.get("HOME", ""))
    out: list[Path] = [primary]
    if scope == "user":
        for tmpl in _USER_TARGET_ALIASES.get((harness, kind), []):
            out.append(Path(tmpl.format(home=str(home))))
    else:
        for rel in _PROJECT_TARGET_ALIASES.get((harness, kind), []):
            out.append(project_root / rel)
    return out
