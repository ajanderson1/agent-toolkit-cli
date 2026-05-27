# Batch 3 — OpenCode + forks (raw research fragment)

> Raw output from research agent. Orchestrator normalizes verdict labels to the
> matrix mechanism vocabulary at assembly (Task 4).

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `opencode` | `translate` | frontmatter `mode` field | `~/.config/opencode/{agent,agents}/**/*.md` / `.opencode/{agent,agents}/**/*.md` | markdown+frontmatter; required: none (name from filename); optional: `mode` (subagent/primary/all, default "all"), `description`, `model`, `temperature`, `top_p`, `steps`, `permission`, `hidden`, `disable`, `color`, `variant`, `prompt`; forbidden: none | `packages/opencode/src/config/agent.ts` load() — `Glob.scan("{agent,agents}/**/*.md")`; mode at `packages/opencode/src/agent/agent.ts:32` via `Schema.Literals(["subagent","primary","all"])` |
| `crush` | `unsupported (gap)` | | n/a | n/a | github.com/charmbracelet/crush issue #1807 — open feature request (2026-05); delegation is runtime-only via hardcoded `agent`+`agentic_fetch` tools; no user-authored agent files |
| `goose` | `unsupported (by design)` | | n/a | n/a | block/goose — "subagents" runtime-only (no def file) + "subrecipes" (YAML session presets in `~/.config/goose/recipes/`, user-invoked not spawnable); neither = subagent-file concept; `documentation/blog/2025-09-26-subagents-vs-subrecipes/` |
| `aider-desk` | `config_file+folder` | `<slug>/config.json` subdir under `.aider-desk/agents/`; `subagent.enabled:true` marks spawnable; invoked via `run_task` tool; hot-reloaded | `~/.aider-desk/agents/<slug>/config.json` / `<project>/.aider-desk/agents/<slug>/config.json` | JSON (no markdown); required `id`(uuid), `name`, `provider`, `model`, `subagent.enabled`, `subagent.systemPrompt`, `subagent.invocationMode`; `order.json` controls sort | github.com/hotovo/aider-desk/blob/main/src/main/agent/agent-profile-manager.ts + .../constants.ts (`AIDER_DESK_AGENTS_DIR`) |

## What I checked — Batch 3 OpenCode+forks

- `opencode`: Read `packages/opencode/src/config/agent.ts` `load()` from `sst/opencode` main. Glob `"{agent,agents}/**/*.md"` — BOTH singular+plural at both scopes. User = `Global.Path.config` (`~/.config/opencode/`); project = `.opencode/`. `mode` optional, default `"all"`; body becomes system prompt. Docs confirm `description` as nominal required field though schema marks optional.
- `crush`: Issue #1807 open feature request — user-defined subagent files do not exist. Delegation runtime-only via hardcoded `agent`+`agentic_fetch`. → `unsupported (gap)`.
- `goose`: Has `subagent_execution_tool` (Rust) + blog distinguishing "subagents" (transient, no def file) vs "subrecipes" (YAML in `~/.config/goose/recipes/` or `.goose/recipes/`, user-invoked session configs). Neither = orchestrator-spawnable file-defined assistant. → `unsupported (by design)`.
- `aider-desk`: (researched separately — originally assigned to this batch, dispatched as a follow-up after a partition slip.) Source-confirmed: agent profiles are `<slug>/config.json` subdirs under `.aider-desk/agents/` at global (`~/`) and project scope, file-watched/hot-reloaded; `subagent.enabled:true` in the JSON marks a profile spawnable (invoked via `run_task`). JSON not markdown. → `config_file+folder`.

## Baseline deltas (vs v1 tag v1.0.0)

- **opencode:** v1 = `translate → ~/.config/opencode/agents/<slug>.md` (user) / `.opencode/agents/<slug>.md` (project), inject `mode: subagent`. CONFIRMED + REFINED: loader globs BOTH `{agent,agents}` (singular AND plural accepted) recursively (`**`). Mechanism stays **translate** (inject `mode: subagent`). Citation upgraded to `agent.ts` load() + `agent.ts:32`. Baseline holds with the singular/plural refinement.
