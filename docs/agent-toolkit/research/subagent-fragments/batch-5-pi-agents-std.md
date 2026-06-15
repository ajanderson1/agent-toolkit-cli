# Batch 5 — Pi + agents-std (raw research fragment)

> Raw output. Orchestrator normalizes verdict labels to matrix vocabulary at assembly (Task 4).

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `pi` | `dual-symlink` (3rd-party ext) | `@tintinweb/pi-subagents` loader | `~/.pi/agent/agents/<slug>.md` / `.pi/agents/<slug>.md` (legacy `.agents/<slug>.md` fallback) | markdown+frontmatter; all fields optional (`description`, `tools`, `model`, `thinking`, `max_turns`, `prompt_mode`) | github.com/tintinweb/pi-subagents (README); pi.dev/packages/pi-subagents |
| `amp` | `unsupported (gap)` | — | — / — | Task tool spawns subagents at runtime; `.agents/commands/` + `AGENT.md` guide main agent only | https://ampcode.com/manual |
| `cline` | `unsupported (gap)` | — | — / — | `use_subagents` spawns read-only runtime research agents; no file-drop convention | https://docs.cline.bot/features/subagents |
| `warp` | `unsupported (gap)` | — | — / — | Oz orchestration spawns named harnesses as children; `AGENTS.md`=context doc; skills≠spawnable agents | https://docs.warp.dev/agent-platform/capabilities/skills/ |
| `deepagents` | `unsupported (by design)` | — | — / — | Python library; subagents = `SubAgent` TypedDict via `SubAgentMiddleware(subagents=[...])`; no file-drop | github.com/langchain-ai/deepagents/.../middleware/subagents.py |
| `firebender` | `config_file+folder` | `firebender.json` agents array + `.firebender/agents/*.md` | `~/.firebender/firebender.json` → agent md / `firebender.json` → `.firebender/agents/<slug>.md` | markdown+frontmatter; required `name`, `description`; optional `callable` (must be true to spawn), `tools`, `model`, `color`, `icon` | https://docs.firebender.com/multi-agent/subagents |

## What I checked — Batch 5 Pi/agents-std

- `pi`: `@tintinweb/pi-subagents` is the primary 3rd-party loader; pi core has no native subagent support. Paths: builtin `~/.pi/agent/extensions/subagent/agents/`, user `~/.pi/agent/agents/**/*.md`, project `.pi/agents/**/*.md` (legacy `.agents/**/*.md` fallback). Competing forks exist (mjakl, gee666, can1357/oh-my-pi); tintinweb is feature-richest. NOTE: agent found `~/.agents/` is a SKILLS path not an agent-discovery path in current docs — agent-specific global path is `~/.pi/agent/agents/`.
- `amp`: Task tool spawns ad-hoc subagents; no user file-drop convention. → `unsupported (gap)`.
- `cline`: `use_subagents` = read-only parallel research agents, internal only; no def file. → `unsupported (gap)`.
- `warp`: Oz cross-harness orchestration; `AGENTS.md`=context; no user subagent file. → `unsupported (gap)`.
- `deepagents`: Python library (langchain-ai). Subagents = code TypedDicts via middleware; no path convention. → `unsupported (by design)`.
- `firebender`: JetBrains plugin. Subagents = markdown registered in `firebender.json` `agents` array; spawnable when `callable: true`. Config points to md files (not watched dir). → `config_file+folder`.

## Baseline deltas (vs v1 tag v1.0.0)

- **pi:** v1 = `dual-symlink → ~/.pi/agent/agents/<slug>.md` AND `~/.agents/<slug>.md` via `pi-subagents`, project `.pi/agents/` + `.agents/` (#75). CURRENT: loader is now namespaced `@tintinweb/pi-subagents`; the `~/.agents/` global alias appears to be a SKILLS path, not agent-discovery — agent-specific global is `~/.pi/agent/agents/`. Project-scope `.agents/` survives only as a legacy fallback. POTENTIAL baseline change: the user-scope dual `~/.agents/` alias may no longer be a valid agent slot. FLAGGED for Phase B verification against the actual installed extension.
- **firebender:** NOT in v1 — new supported harness via config-file-registered markdown.

## Re-verification 2026-06-10 — `.claude/agents/` readers (#361)

- `firebender`: WebSearch + docs.firebender.com — agents are registered in the
  `firebender.json` `agents` array pointing at `.firebender/agents/*.md`; no
  `.claude/agents/` auto-read. Negative.
