"""Single source of truth for the (harness, asset-kind) support matrix.

The matrix encodes which (harness, kind) pairs the toolkit can currently
project to a real on-disk slot. Adding a row here is the only place a new
adapter slot needs declaring; consumers (`_link_lib`, `_list_json`,
`commands/unlink`, `doctor/*`) read from here.

Issue #30: silent-skip on unsupported pairs is now a structured raise.
Issue #32 tracks closing remaining matrix gaps (e.g. opencode agents).
"""
from __future__ import annotations

import os
from pathlib import Path

import click

ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")
ALL_KINDS: tuple[str, ...] = (
    "skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension",
)

_USER_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       "{home}/.claude/skills",
    ("claude", "agent"):       "{home}/.claude/agents",
    ("claude", "command"):     "{home}/.claude/commands",
    ("claude", "hook"):        "{home}/.claude/hooks",
    ("claude", "plugin"):      "{home}/.claude/plugins",
    ("codex", "skill"):        "{home}/.codex/skills",
    ("opencode", "skill"):     "{home}/.config/opencode/skills",
    ("opencode", "agent"):     "{home}/.config/opencode/agents",
    ("opencode", "command"):   "{home}/.config/opencode/commands",
    ("pi", "skill"):           "{home}/.pi/agent/skills",
    ("pi", "agent"):           "{home}/.pi/agent/agents",
    ("pi", "pi-extension"):    "{home}/.pi/agent/extensions",
}
_PROJECT_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       ".claude/skills",
    ("claude", "agent"):       ".claude/agents",
    ("claude", "command"):     ".claude/commands",
    ("claude", "hook"):        ".claude/hooks",
    ("claude", "plugin"):      ".claude/plugins",
    ("codex", "skill"):        ".codex/skills",
    ("opencode", "skill"):     ".opencode/skills",
    ("opencode", "agent"):     ".opencode/agents",
    ("opencode", "command"):   ".opencode/commands",
    # Pi project-scope: pi reads from <cwd>/.pi/{skills,extensions} (no /agent/
    # infix at project scope). User-scope keeps the .pi/agent/ prefix because
    # pi's globalBaseDir == ~/.pi/agent. See package-manager.js:669-686.
    ("pi", "skill"):           ".pi/skills",
    ("pi", "agent"):           ".pi/agent/agents",  # pi has no project-scope
                                                    # agents discovery; left in
                                                    # the table to preserve the
                                                    # _USER/_PROJECT key parity
                                                    # invariant. Tracked as a
                                                    # follow-up to #41.
    ("pi", "pi-extension"):    ".pi/extensions",
}

# Derived: SUPPORTED_PAIRS = the set of (harness, kind) pairs with adapter slots.
# Both tables MUST share the same key set; tested in tests/test_support.py.
SUPPORTED_PAIRS: frozenset[tuple[str, str]] = frozenset(_USER_TARGETS.keys())


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


def is_supported(harness: str, kind: str) -> bool:
    """True iff `(harness, kind)` has a real adapter slot in the matrix."""
    return (harness, kind) in SUPPORTED_PAIRS


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
    """
    home = Path(os.environ.get("HOME", ""))
    if scope == "user":
        tmpl = _USER_TARGETS.get((harness, kind))
        return Path(tmpl.format(home=str(home))) if tmpl else None
    rel = _PROJECT_TARGETS.get((harness, kind))
    return (project_root / rel) if rel else None
