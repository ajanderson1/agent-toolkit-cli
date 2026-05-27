# Batch 2 — Google/Gemini (raw research fragment)

> Raw output from research agent. Orchestrator normalizes verdict labels to the
> matrix mechanism vocabulary at assembly (Task 4).

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `gemini-cli` | `translate` | `translate` | `~/.gemini/agents/<slug>.md` / `.gemini/agents/<slug>.md` | markdown+frontmatter; required: `name` (slug), `description`; forbidden: any extra top-level key (zod `.strict()`) | `packages/core/src/agents/agentLoader.ts` localAgentSchema `.strict()` + `packages/core/src/config/storage.ts:117-118,309-310` |
| `qwen-code` | `translate` | `translate` | `~/.qwen/agents/<slug>.md` / `.qwen/agents/<slug>.md` | markdown+frontmatter; required: `name`, `description`, `systemPrompt`; no strict rejection of extra keys | `packages/core/src/subagents/subagent-manager.ts:930-931`, `storage.ts:144-154`, `validation.ts:34-36` |
| `antigravity` | `unknown — no public evidence found` | | | | GitHub discussion #27305; official source not public (closed-source Go binary) |
| `iflow-cli` | `unsupported (gap)` | | | | Shut down 2026-04-17; was `.iflow/agents/<slug>.md` / `~/.iflow/agents/<slug>.md`, required `agentType`+`systemPrompt`+`whenToUse` |

## What I checked — Batch 2 Google/Gemini

- `gemini-cli`: Read `packages/core/src/agents/agentLoader.ts` via `gh api`; confirmed `localAgentSchema.strict()`. `storage.ts` lines 54-59 (`getGlobalGeminiDir()`), 117-118 (`getUserAgentsDir()` → `~/.gemini/agents`), 309-310 (`getProjectAgentsDir()` → `.gemini/agents`). `registry.ts` 172-235 confirms both load paths. Official `docs/core/subagents.md` confirms.
- `qwen-code`: Gemini-CLI fork with INDEPENDENT subagent loader. `subagent-manager.ts:930-931` project `.qwen/agents/`, user `~/.qwen/agents`. `validation.ts` requires name/description/systemPrompt. No `.strict()`. `QWEN_DIR='.qwen'`.
- `antigravity`: 12+ sources (Google blog, tutorials, discussion #27305, antigravity.google/docs empty). Dynamic subagents are orchestrator-spawned (not user-file-defined). Community shows `~/.gemini/antigravity-cli/agents/<name>/agent.json` (JSON not .md) but no official loader source. Closed-source Go binary. → `unknown` for user-definable file-drop subagents.
- `iflow-cli`: Shut down 2026-04-17 (community notice + changelog). Pre-shutdown DID support `.iflow/agents/<slug>.md` + `~/.iflow/agents/<slug>.md`, required `agentType`/`systemPrompt`/`whenToUse`. Marked gap (defunct harness).

## Baseline deltas (vs v1 tag v1.0.0)

- **gemini-cli:** v1 = `translate → ~/.gemini/agents/<slug>.md`, name+description only, zod `.strict()` (#97). CONFIRMED live with citation upgrade: `agentLoader.ts` `localAgentSchema.strict()`, `storage.ts:117-118,309-310`. Baseline holds. Mechanism: **translate**.
- **qwen-code:** NOT in v1 — new supported harness. Gemini fork but own loader; requires an extra `systemPrompt` field and does NOT use `.strict()` → its own translate flavor in Phase B.
