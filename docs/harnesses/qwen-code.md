# ![Qwen Code logo](https://github.com/QwenLM.png?size=64){ .harness-logo } Qwen Code

`qwen-code` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.qwen/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `QWEN.md` + `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (or `./QWEN.md`) / `~/.qwen/AGENTS.md` (or `~/.qwen/QWEN.md`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [PR #2018](https://github.com/QwenLM/qwen-code/pull/2018) merged 2026-03-02 in `packages/core/src/tools/memoryTool.ts` adds `AGENT_CONTEXT_FILENAME = 'AGENTS.md'` and sets `currentGeminiMdFilename = [DEFAULT_CONTEXT_FILENAME, AGENT_CONTEXT_FILENAME]` (closes [#2006](https://github.com/QwenLM/qwen-code/issues/2006))

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.qwen/skills`
- **Global dir:** `~/.qwen/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.qwen/agents/<slug>.md` / `.qwen/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`,`systemPrompt`
- **Toolkit adapter:** enabled (translate)
- **Source:** [`packages/core/src/subagents/subagent-manager.ts:930-931`](https://github.com/QwenLM/qwen-code/blob/main/packages/core/src/subagents/subagent-manager.ts), `validation.ts:34-36`

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
