"""Column-level information for every explainable TUI grid column (#479).

The registry is intentionally keyed by ``(asset_type, column)``. A new rendered
column without authored copy must fail loudly instead of degrading into a dead
``ⓘ`` affordance. Values are factories so covered-harness lists are resolved
from their source of truth when the panel opens, never at import time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_toolkit_tui.composition import MAIN_HARNESS_CANDIDATES
from agent_toolkit_tui.display_names import asset_type_label, harness_label


@dataclass(frozen=True)
class ColumnInfo:
    """Content displayed by ``ColumnInfoModal`` for one grid column."""

    title: str
    lines: list[str]


Factory = Callable[[dict[str, object]], ColumnInfo]


# Spec R5 is the wording source of truth. These sentences deliberately stay
# beside the registry instead of being inferred from adapter internals: paths
# and mechanisms are user-facing explanations, not an adapter API.
_HARNESS_SENTENCES: dict[tuple[str, str], str] = {
    ("skill", "claude-code"): (
        "Reads skills from `~/.claude/skills/`, its own directory rather than "
        "the shared `.agents/skills` slot, so it needs a separate install."
    ),
    ("skill", "pi"): (
        "Reads skills from `~/.pi/agent/skills/`, its own directory rather "
        "than the shared `.agents/skills` slot."
    ),
    ("skill", "hermes-agent"): (
        "Reads skills from `~/.hermes/skills/`, its own directory outside the "
        "standard slot."
    ),
    ("skill", "paperclip"): (
        "Projects the skill into a Paperclip company library rather than a "
        "harness home, so its scope is the company, not the machine or the repo."
    ),
    ("instruction", "claude-code"): (
        "Reads `CLAUDE.md`, not `AGENTS.md`, so the toolkit writes a pointer "
        "file that references the canonical instructions."
    ),
    ("instruction", "gemini-cli"): (
        "Reads `GEMINI.md`, so the toolkit writes a pointer file; at project "
        "scope Gemini merges the global and project files rather than replacing "
        "one with the other."
    ),
    ("agent", "gemini-cli"): (
        "Gets a translated agent file at `.gemini/agents/<slug>.md`; the "
        "toolkit rewrites the frontmatter into Gemini's shape rather than symlinking."
    ),
    ("agent", "opencode"): (
        "Gets a translated agent file at `.opencode/agents/<slug>.md` "
        "(project) or the XDG config equivalent (global)."
    ),
    ("agent", "pi"): (
        "Gets a symlinked agent file at `.pi/agents/<slug>.md`, so edits to "
        "the library copy are picked up immediately."
    ),
    ("mcp", "claude-code"): (
        "Reads `mcpServers` from a JSON config; at project scope it is covered "
        "by the shared `.mcp.json` slot instead of its own entry."
    ),
    ("mcp", "codex"): (
        "Reads `[mcp_servers.<name>]` from a TOML config, so its entry is "
        "written and round-tripped separately from the JSON readers."
    ),
    ("mcp", "opencode"): (
        "Reads `mcpServers` from its own JSON config, which is not the shared "
        "project `.mcp.json`."
    ),
    ("mcp", "pi"): (
        "Reads `mcpServers` from a JSON config; at project scope it is covered "
        "by the shared `.mcp.json` slot instead of its own entry."
    ),
    ("command", "pi"): (
        "Reads command markdown from `.pi/prompts/` (project) or "
        "`.pi/agent/prompts/` (global)."
    ),
    ("command", "gemini-cli"): (
        "Needs a TOML command file at `.gemini/commands/<slug>.toml`, so the "
        "markdown is converted rather than copied."
    ),
    ("pi-extension", "pi"): (
        "Extensions are Pi-only; there is no shared slot and no other harness "
        "consumes them, which is why this asset type has no Standard column."
    ),
}

_STANDARD_SENTENCES: dict[str, str] = {
    "skill": (
        "One skill directory at `.agents/skills/<slug>/` that every harness "
        "in this list reads natively, so a single install serves all of them."
    ),
    "instruction": (
        "These harnesses read the repo's top-level `AGENTS.md` directly, so no "
        "per-harness pointer file is written for them."
    ),
    "agent": (
        "One file at `.claude/agents/<slug>.md` — the de-facto convergence "
        "directory these harnesses read, so the slot is a single artifact, not a bundle."
    ),
    "mcp": (
        "One `mcpServers` entry in the project's `.mcp.json`, which these "
        "harnesses read as a shared project-level server list."
    ),
}

_SKILL_STATE_LINES = [
    "Per-skill working-tree state in this scope.",
    "",
    "• clean — installed and matches the library canonical",
    "• dirty — installed but the on-disk copy diverges from the library",
    "• missing — in the library, not installed in this scope",
    "• copy — installed as a real copy (symlink fallback — e.g. Windows)",
    "• library — in the library, not yet installed in this project "
    "(project scope only — normal pre-install state)",
    "• unlisted — installed in this project but no longer tracked by "
    "the library lock (re-add via `skill doctor -p`)",
]

_THREE_BADGE_STATE_LINES = [
    "• installed — tracked by the library and present in this scope",
    "• library — in the library but not installed here",
    "• unlisted — present in this scope but no longer tracked by the library "
    "lock (re-add via the matching `doctor` command)",
]


def _scope(context: dict[str, object], *, default: str) -> str:
    value = context.get("scope", default)
    return value if isinstance(value, str) else default


def _marker_lines(asset_type: str, context: dict[str, object]) -> list[str]:
    """Return the existing project-scope 🌐 explanation, unchanged in wording."""

    if _scope(context, default="global") != "project" or not context.get("global_linked", True):
        return []
    if asset_type == "skill":
        return [
            "",
            "🌐 marker (project scope only):",
            "  This skill is also installed globally,",
            "  so you may not need it at project scope too.",
        ]
    if asset_type == "instruction":
        return [
            "",
            "🌐 marker (project scope only):",
            "  This harness also loads a global AGENTS.md,",
            "  merged with (not replaced by) the project one.",
        ]
    if asset_type == "agent":
        return [
            "",
            "🌐 marker (project scope only):",
            "  This agent is also installed globally.",
        ]
    return []


def _standard_info(
    asset_type: str,
    names: tuple[str, ...],
    context: dict[str, object],
) -> ColumnInfo:
    lines = [
        f"Covered harnesses ({len(names)}):",
        "",
        *[f"  • {harness_label(name)}" for name in names],
        "",
        _STANDARD_SENTENCES[asset_type],
    ]
    if asset_type == "agent" and _scope(context, default="global") == "global":
        lines += ["", "Devin reads .claude/agents at project scope only."]
    lines += _marker_lines(asset_type, context)
    return ColumnInfo(
        title=f"Standard — {asset_type_label(asset_type, plural=True)}",
        lines=lines,
    )


def _standard_skills(context: dict[str, object]) -> ColumnInfo:
    # source: skill_agents.AGENTS / get_standard_agents()
    from agent_toolkit_cli.skill_agents import get_standard_agents

    return _standard_info("skill", tuple(get_standard_agents()), context)


def _standard_instructions(context: dict[str, object]) -> ColumnInfo:
    # source: instructions_matrix.instructions_matrix_rows()
    from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

    names = tuple(
        row["harness"]
        for row in instructions_matrix_rows()
        if row["verdict"] == "native"
    )
    return _standard_info("instruction", names, context)


def _standard_agents(context: dict[str, object]) -> ColumnInfo:
    # source: agent_adapters.standard.agents_standard_covered()
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered

    names = tuple(sorted(agents_standard_covered(_scope(context, default="global"))))
    return _standard_info("agent", names, context)


def _standard_mcps(context: dict[str, object]) -> ColumnInfo:
    # source: mcp_standard.mcp_standard_covered(); project-only by design
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered

    names = tuple(sorted(mcp_standard_covered(_scope(context, default="project"))))
    return _standard_info("mcp", names, context)


def _standard_commands(context: dict[str, object]) -> ColumnInfo:
    # source: command_adapters.standard.commands_standard_covered()
    from agent_toolkit_cli.command_adapters.standard import commands_standard_covered

    scope = _scope(context, default="global")
    names = tuple(sorted(commands_standard_covered(scope)))
    if scope == "project":
        sentence = (
            "One Markdown command slot at `.claude/commands/<slug>.md` serves "
            "Claude and Neovate; Devin imports it as a skill."
        )
    else:
        sentence = (
            "One Markdown command slot at `.claude/commands/<slug>.md` serves "
            "Claude and Neovate."
        )
    lines = [
        f"Covered harnesses ({len(names)}):",
        "",
        *[f"  • {harness_label(name)}" for name in names],
        "",
        sentence,
    ]
    return ColumnInfo(
        title=f"Standard — {asset_type_label('command', plural=True)}",
        lines=lines,
    )


def _harness_info(asset_type: str, harness: str, _context: dict[str, object]) -> ColumnInfo:
    sentence = _HARNESS_SENTENCES.get((asset_type, harness))
    if not sentence:
        sentence = f"Manages {asset_type_label(asset_type, plural=True).lower()} for {harness_label(harness)}."
    return ColumnInfo(
        title=f"{harness_label(harness)} — {asset_type_label(asset_type, plural=True)}",
        lines=[sentence],
    )


def _skill_state(_context: dict[str, object]) -> ColumnInfo:
    return ColumnInfo(title="State badges — Skills", lines=list(_SKILL_STATE_LINES))


def _three_badge_state(asset_type: str, _context: dict[str, object]) -> ColumnInfo:
    return ColumnInfo(
        title=f"State badges — {asset_type_label(asset_type, plural=True)}",
        lines=[f"Per-{asset_type_label(asset_type).lower()} state in this scope.", "", *_THREE_BADGE_STATE_LINES],
    )


def _pi_extension_origin(_context: dict[str, object]) -> ColumnInfo:
    return ColumnInfo(
        title="Origin — Pi Extensions",
        lines=[
            "• library — owned by the toolkit store",
            "• npm — installed as an npm package",
            "• untracked — present in Pi but not managed by the toolkit",
        ],
    )


COLUMN_INFO: dict[tuple[str, str], Factory] = {
    ("skill", "standard"): _standard_skills,
    ("skill", "claude-code"): lambda context: _harness_info("skill", "claude-code", context),
    ("skill", "pi"): lambda context: _harness_info("skill", "pi", context),
    ("skill", "hermes-agent"): lambda context: _harness_info("skill", "hermes-agent", context),
    ("skill", "paperclip"): lambda context: _harness_info("skill", "paperclip", context),
    ("skill", "state"): _skill_state,
    ("instruction", "standard"): _standard_instructions,
    ("instruction", "claude-code"): lambda context: _harness_info("instruction", "claude-code", context),
    ("instruction", "gemini-cli"): lambda context: _harness_info("instruction", "gemini-cli", context),
    ("agent", "standard"): _standard_agents,
    ("agent", "gemini-cli"): lambda context: _harness_info("agent", "gemini-cli", context),
    ("agent", "opencode"): lambda context: _harness_info("agent", "opencode", context),
    ("agent", "pi"): lambda context: _harness_info("agent", "pi", context),
    ("agent", "state"): lambda context: _three_badge_state("agent", context),
    ("mcp", "standard"): _standard_mcps,
    ("mcp", "claude-code"): lambda context: _harness_info("mcp", "claude-code", context),
    ("mcp", "codex"): lambda context: _harness_info("mcp", "codex", context),
    ("mcp", "opencode"): lambda context: _harness_info("mcp", "opencode", context),
    ("mcp", "pi"): lambda context: _harness_info("mcp", "pi", context),
    ("mcp", "state"): lambda context: _three_badge_state("mcp", context),
    ("command", "standard"): _standard_commands,
    ("command", "pi"): lambda context: _harness_info("command", "pi", context),
    ("command", "gemini-cli"): lambda context: _harness_info("command", "gemini-cli", context),
    ("command", "state"): lambda context: _three_badge_state("command", context),
    ("pi-extension", "pi"): lambda context: _harness_info("pi-extension", "pi", context),
    ("pi-extension", "origin"): _pi_extension_origin,
}


def get_column_info(
    column: str,
    *,
    asset_type: str,
    context: dict[str, object] | None = None,
) -> ColumnInfo:
    """Return fresh info for an authored ``(asset_type, column)`` pair.

    Unknown pairs raise ``KeyError`` deliberately: a new column cannot silently
    gain an inert info glyph.
    """

    if (asset_type, column) in COLUMN_INFO:
        return COLUMN_INFO[(asset_type, column)](context or {})

    if column in MAIN_HARNESS_CANDIDATES:
        return _harness_info(asset_type, column, context or {})

    raise KeyError((asset_type, column))


def registered_pairs() -> frozenset[tuple[str, str]]:
    """Return the registry's authored ``(asset_type, column)`` pairs."""

    return frozenset(COLUMN_INFO)
