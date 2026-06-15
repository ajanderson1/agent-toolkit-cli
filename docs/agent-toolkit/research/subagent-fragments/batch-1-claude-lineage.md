# Batch 1 — Claude-lineage (raw research fragment)

> Raw output from research agent. Verdict labels here use the agent's loose
> reading; the orchestrator normalizes to the matrix mechanism vocabulary at
> assembly (Task 4). See `## Baseline deltas` at the end.

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `claude-code` | `config_file+folder` | `config_file+folder` | `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md` | markdown+frontmatter; required: `name`, `description`; optional: `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt`; no forbidden keys documented (extra keys silently ignored) | https://code.claude.com/docs/en/sub-agents |
| `openclaw` | `unsupported (gap)` | — | — | — | https://docs.openclaw.ai/concepts/multi-agent |
| `kode` | `config_file+folder` | `config_file+folder` | `~/.kode/agents/` AND `~/.claude/agents/` (both user-scope) / `.kode/agents/` AND `.claude/agents/` (both project-scope) | markdown+frontmatter; required: `name`, `description`; optional: `tools` (array, defaults to all), `model_name`; deprecated/forbidden: `model` (field is ignored) | https://github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md |
| `mux` | `config_file+folder` | `config_file+folder` | `~/.mux/agents/*.md` / `.mux/agents/*.md` (non-recursive, project overrides user) | markdown+frontmatter; required: `name`; optional: `description`, `base`, `ui`, `prompt`, `subagent` (with `runnable`, `skip_init_hook`, `append_prompt`), `ai`, `tools`; no forbidden keys documented | https://mux.coder.com/agents |
| `command-code` | `config_file+folder` | `config_file+folder` | `~/.commandcode/agents/<slug>.md` / `.commandcode/agents/<slug>.md` | markdown+frontmatter; required: `name`, `description`, `tools`; optional: (markdown body = system prompt); reserved names (`explore`, `plan`, `review`, `general`) cannot be customized | https://commandcode.ai/docs/core-concepts/custom-agents |
| `codemaker` | `unsupported (by design)` | — | — | — | https://github.com/codemakerai/codemaker-cli |

## What I checked — Batch 1 Claude-lineage

- `claude-code`: Fetched current Anthropic docs at `code.claude.com/docs/en/sub-agents`. Required fields `name`+`description`; 15 optional frontmatter fields; extra keys silently ignored. Discovery walks `.claude/agents/` and `~/.claude/agents/` recursively; also `--agents` JSON flag, managed settings, plugin `agents/` dirs.
- `openclaw`: OpenClaw is a messaging gateway (WhatsApp/Telegram→AI), not a coding CLI. "Multi-agent" = persistent chat personas in `~/.openclaw/agents/<agentId>/` (`soul.md`, `agent.md`, `user.md`), not spawnable coding sub-assistants. Projection would need redesign → `unsupported (gap)`.
- `kode`: Scans both `.kode/agents/` and `.claude/agents/` at user+project scope (five-tier priority). `model` deprecated → `model_name`. `/agents` command + `kode agents validate`. Explicit Claude Code compatibility layer.
- `mux`: Coder's parallel-agent desktop app. Distinct agent defs at `.mux/agents/*.md` / `~/.mux/agents/*.md` (non-recursive). Inheritance via `base:`; subagent spawning via `task()` when `runnable: true`. Genuine spawnable-subagent mechanism.
- `command-code`: Proprietary coding CLI (commandcode.ai). Custom agents at `.commandcode/agents/` + `~/.commandcode/agents/`, markdown+frontmatter, `/agents` command. Required `name`/`description`/`tools`. Mirrors Claude Code's convention.
- `codemaker`: CodeMaker AI Go CLI for batch code-gen (last release v1.6.0, Jul 2024). No subagent concept; calls backend API. → `unsupported (by design)`.

## Baseline deltas (vs v1 tag v1.0.0)

- **claude-code:** v1 = `symlink → ~/.claude/agents/<slug>.md`. CURRENT: still a markdown+frontmatter drop-in (so our mechanism stays **symlink** — agent's `config_file+folder` label is a misclassification of "reads a folder"; we do not mutate a config file). NEW facts: discovery is now **recursive**; optional-frontmatter set greatly expanded (15 fields). Mechanism verdict for our matrix: **symlink** (frontmatter passes unchanged). Confirmed live.
- **kode / mux / command-code:** NOT in v1's 5 baselines — newly surfaced supported harnesses. kode reads `.claude/agents/` (Claude-compatible) → symlink; mux + command-code use their own dirs with compatible markdown → symlink (verify frontmatter reshape need in Phase B).

## Re-verification 2026-06-10 — `.claude/agents/` readers (#361)

- `claude-code`: re-fetched https://code.claude.com/docs/en/sub-agents —
  confirms `.claude/agents/` (project, discovered by walking up from cwd) and
  `~/.claude/agents/` (user), both scanned **recursively**, by default. HOLDS
  at both scopes.
- `kode`: re-fetched docs/agents-system.md — five-tier priority order still
  lists `~/.claude/agents/` (user) and `./.claude/agents/` (project) as
  auto-scanned defaults, no flags/config. HOLDS at both scopes.
- `command-code`: WebSearch `"command code" commandcode.ai ".claude/agents"` —
  no evidence command-code reads `.claude/agents/`; own
  `~/.commandcode/agents/` dirs only. Negative.
- `mux`: WebSearch `mux coder ".claude/agents"` — no evidence mux reads
  `.claude/agents/` for agent definitions (it accepts `CLAUDE.md` as an
  instruction base file, which is unrelated). Negative.
