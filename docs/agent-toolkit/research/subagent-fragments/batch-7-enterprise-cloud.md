# Batch 7 — Enterprise/cloud (raw research fragment)

> Raw output. Orchestrator normalizes verdict labels to matrix vocabulary at assembly (Task 4).
> "config_file+folder" labels for Claude-style markdown drop-ins → normalize to `symlink`/`translate`.

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `bob` | `unsupported (gap)` | — | `~/.bob/rules*/` / `.bob/rules*/` (modes only) | markdown rules + YAML mode config; no `agents/` dir | https://bob.ibm.com/docs/ide/configuration/rules |
| `codearts-agent` | `unknown — no public evidence found` | — | — | — | huaweicloud.com/intl/en-us/product/codearts/ai.html |
| `cortex` | `config_file+folder` | markdown agents dir | `~/.snowflake/cortex/agents/` or `~/.claude/agents/` / `.cortex/agents/` or `.claude/agents/` | markdown+frontmatter; required `name`, `description`, `tools` (array or `"*"`); optional `model` | https://docs.snowflake.com/en/user-guide/cortex-code/extensibility |
| `devin` | `config_file+folder` | markdown agents dir | `~/.config/devin/agents/{profile}/AGENT.md` / `.devin/agents/{profile}/AGENT.md` | markdown+frontmatter; required `name`, `description`; optional `model`, `allowed-tools`, `permissions`, `max-nesting`; also reads `.claude/agents/*.md` | https://cli.devin.ai/docs/subagents |
| `droid` | `config_file+folder` | markdown droids dir | `~/.factory/droids/` / `.factory/droids/` | markdown+frontmatter; required `name` (lc/digits/-/_), non-empty body; optional `description` (≤500), `model`, `tools` | https://docs.factory.ai/cli/configuration/custom-droids |
| `rovodev` | `config_file+folder` | markdown subagents dir | `~/.rovodev/subagents/` / `.rovodev/subagents/` | markdown+frontmatter; required `name`, `description`, `tools` (list); body=system prompt | https://support.atlassian.com/rovo/docs/use-subagents-in-rovo-dev-cli/ |
| `tabnine-cli` | `unsupported (by design)` | — | — | "mini-agents" internal routing, not user-definable | https://docs.tabnine.com/main/getting-started/tabnine-cli |
| `zencoder` | `unsupported (by design)` | — | — | Zen Agents via marketplace UI; no local file-drop dir | https://zencoder.ai/blog/introducing-zen-agents-mcp-library-and-marketplace |

## What I checked — Batch 7 Enterprise/cloud

- `bob` (IBM): `.bob/` holds `rules*/` + mode configs; no `agents/` subdir or spawnable subagent. Modes = prompt personas not spawnable. → `unsupported (gap)`.
- `codearts-agent` (Huawei): public beta Feb 2026; "four-layer extension" mentions MCP+Skills but no public file-drop subagent dir. → `unknown`.
- `cortex` (Snowflake Cortex Code CLI): explicit 3-scope dirs (`~/.snowflake/cortex/agents/`, `~/.claude/agents/`, `.cortex/agents/`, `.claude/agents/`), markdown+frontmatter. → markdown drop-in.
- `devin` (Cognition): `cli.devin.ai/docs/subagents` live; `AGENT.md` per named profile dir; ALSO imports `.claude/agents/*.md` with field aliasing. → markdown drop-in.
- `droid` (Factory.ai): `.factory/droids/` (project) + `~/.factory/droids/` (user); DroidValidator enforces `name` at load. → markdown drop-in.
- `rovodev` (Atlassian): `.rovodev/subagents/` + `~/.rovodev/subagents/`, required name/description/tools; `/subagents` command. → markdown drop-in.
- `tabnine-cli`: Enterprise Agent routes to internal mini-agents; no user file-drop. → `unsupported (by design)`.
- `zencoder`: Zen Agents marketplace/UI-defined; OSS repo is a catalog not local drop-in. → `unsupported (by design)`.

## Baseline deltas (vs v1 tag v1.0.0)

- None in v1's 5. FIVE newly-supported via markdown drop-in: **cortex, devin, droid, rovodev** (+ cortex/devin also read `.claude/agents/`). bob = near-miss gap; codearts-agent = unknown; tabnine/zencoder = by design.

## Re-verification 2026-06-10 — `.claude/agents/` readers (#361)

- `cortex`: re-fetched docs.snowflake.com/en/user-guide/cortex-code/extensibility —
  three documented locations still include Project `.cortex/agents/` **or**
  `.claude/agents/` and User `~/.claude/agents/` (plus Global
  `~/.snowflake/cortex/agents/`), no conditions. HOLDS at both scopes.
- `devin`: original citation `cli.devin.ai/docs/subagents` now **301s to
  https://docs.devin.ai/cli/subagents** (matrix citation updated). The page's
  "Importing From Other Tools" table lists `.claude/agents/*.md` ("each `.md`
  file becomes a subagent profile") as a **project-relative** import source;
  `tools`/`allowed-tools` frontmatter both accepted. Global scope is the
  profile-dir tree (`~/.config/devin/agents/{profile}/AGENT.md`), NOT
  `~/.claude/agents/` → devin is a **project-scope `.claude/agents/` reader
  only**. Also new: project paths now include `.agents/agents/{name}/AGENT.md`.
  HOLDS (project scope only).
- `droid`: WebSearch + docs.factory.ai/cli/configuration/custom-droids — Factory
  supports a one-time **import** of a project's `.claude/agents/` that *copies*
  into `~/.factory/droids/`; not a default read → does NOT count. Negative.
- `rovodev`: WebSearch `Rovo Dev CLI ".claude/agents"` — no evidence; own
  `.rovodev/subagents/` dirs only. Negative.
