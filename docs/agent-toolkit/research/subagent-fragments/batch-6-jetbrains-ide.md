# Batch 6 — JetBrains/IDE (raw research fragment)

> Raw output. Orchestrator normalizes verdict labels to matrix vocabulary at assembly (Task 4).
> Most "config_file+folder" labels here are Claude-style markdown drop-ins → normalize to `symlink`/`translate`.

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `junie` | `config_file+folder` | markdown+frontmatter | `~/.junie/agents/<slug>.md` or `~/.agents/<slug>.md` / `.junie/agents/<slug>.md` or `.agents/<slug>.md` | markdown; required `description`; optional `name`, `tools`, `disallowedTools`, `model`, `reasoningLevel`, `skills`, `allowPromptArgument` | https://junie.jetbrains.com/docs/junie-cli-subagents.html |
| `qoder` | `config_file+folder` | markdown+frontmatter | `~/.qoder/agents/<name>.md` / `${project}/.qoder/agents/<name>.md` | markdown; required `name`, `description`; optional `tools` (comma-sep), `skills`, `mcpServers` | https://docs.qoder.com/extensions/subagent |
| `cursor` | `config_file+folder` | markdown+frontmatter | `~/.cursor/agents/<slug>.md` (also `~/.claude/agents/`, `~/.codex/agents/`) / `.cursor/agents/<slug>.md` (also `.claude/agents/`, `.codex/agents/`) | markdown; required `name`, `description`; optional `model` (default `inherit`), `readonly`, `is_background` | https://cursor.com/docs/subagents (re-verified 2026-06-10) |
| `kilo` | `config_file+folder` | markdown+frontmatter | `~/.config/kilo/agent/<slug>.md` / `.kilo/agents/<slug>.md` or `.kilo/agent/<slug>.md` | markdown; required `description`, `mode` (primary/subagent/all); optional `model`, `color`, `permission`, `temperature`; `mode: subagent` = only invokable via `task` tool | https://kilo.ai/docs/agent-behavior/custom-modes |
| `roo` | `unsupported (gap)` | | global `custom_modes.yaml/json` / `.roomodes` (workspace root) | mode/persona defs (YAML/JSON); delegation via Orchestrator `new_task` tool + `whenToUse`; mode-switch not independent-context spawn | https://roocodeinc.github.io/Roo-Code/features/custom-modes ; .../boomerang-tasks |
| `continue` | `unknown — no public evidence found` | | `.continue/agents/` mentioned in passing (issue #9550); config.yaml-based, internal testing | no stable public file-based subagent spec | https://github.com/continuedev/continue/issues/9550 |
| `windsurf` | `unsupported (by design)` | | n/a | Cascade single-agent; Wave 13 parallel sessions = independent full agents not file-defined; AGENTS.md=context | https://docs.windsurf.com/windsurf/cascade/agents-md |
| `trae` | `unsupported (by design)` | | n/a | custom agents UI-configured (Builder), stored server-side, no on-disk file format | https://docs.trae.ai/ide/agent |
| `trae-cn` | `unsupported (by design)` | | n/a | same product as Trae international (diff bundled models only); identical UI-agent architecture | https://technode.com/2025/03/04/bytedance-launches-trae-ai-ide-in-china-... |

## What I checked — Batch 6 JetBrains/IDE

- `junie`: JetBrains official subagent docs confirm file-based subagents, markdown+frontmatter, dual user/project paths. NOTE: agent reports `~/.agents/` + `.agents/` as alt slots (cross-harness convergence). → markdown drop-in (symlink/translate per frontmatter).
- `qoder`: Docs confirm `~/.qoder/agents/` + `${project}/.qoder/agents/`, required name+description. → markdown drop-in.
- `cursor`: cursor.com/docs/subagents confirms `.cursor/agents/` + `~/.cursor/agents/`, markdown+frontmatter, added Jan 2026. Built-in subagents (Explore/Bash/Browser) need no files. → markdown drop-in. (MAJOR: Cursor previously had only "rules"/"modes" — subagents are NEW.)
- `kilo`: `.kilo/agents/<slug>.md` + `~/.config/kilo/agent/<slug>.md`; `mode: subagent` restricts to `task`-tool invocation. Genuine programmatic delegation. → markdown drop-in WITH required `mode` field (translate to inject `mode`).
- `roo`: Custom modes (`.roomodes`/global) ARE real delegation targets via Orchestrator `new_task`, but a mode-switch reusing context, not an independently-spawned agent. → `unsupported (gap)` (closest non-spawning analog; projection could map mode slugs).
- `continue`: Subagent support in private testing (issue #9550), config.yaml-based, no stable public file-folder spec. → `unknown`.
- `windsurf`: Wave 13 parallel agents = user-spawned Cascade sessions, not file-defined. → `unsupported (by design)`.
- `trae`/`trae-cn`: UI-configured agents stored server-side, no on-disk format. trae-cn = same product, diff models. → `unsupported (by design)`.

## Baseline deltas (vs v1 tag v1.0.0)

- None of these 9 were in v1's 5 baselines. SIX are newly-relevant: **cursor, junie, qoder, kilo** newly support file-drop subagents (cursor + qoder + junie are Claude-style markdown → symlink/translate; kilo needs a `mode` field → translate). **roo** is a near-miss gap. **continue** is unknown (private testing).

## Re-verification 2026-06-10 — `.claude/agents/` readers (#361)

- `cursor`: **JOINS the `.claude/agents/` covered set (both scopes).** Fetched
  https://cursor.com/docs/subagents.md — default discovery locations are now
  `.cursor/agents/`, `.claude/agents/`, `.codex/agents/` (project) and
  `~/.cursor/agents/`, `~/.claude/agents/`, `~/.codex/agents/` (user), no
  flags/config; `.cursor/` wins name conflicts. Table row above updated. This
  postdates the original Phase A finding (own dirs only).
- `junie`: WebSearch + junie.jetbrains.com/docs/junie-cli-subagents.html —
  Junie *detects* `.cursor/agents/`, `.claude/agents/`, `.codex/agents/` files
  and **suggests importing** them into `.junie/agents/`. Import-on-prompt, not
  a default read → does NOT count as a `.claude/agents/` reader.
- `qoder`: WebSearch `Qoder ".claude/agents"` — no evidence; own
  `~/.qoder/agents/` + `.qoder/agents/` dirs only. Negative.
- `kilo`: Fetched kilo.ai/docs/agent-behavior/custom-modes — scans
  `.kilo/agents/`, `.kilo/agent/`, `.opencode/agents/` (project) and
  `~/.config/kilo/agent/` (global); no `.claude/agents/` mention. Negative.
  (Note: kilo DOES read `.opencode/agents/` — an opencode compat layer, not a
  claude one.)
