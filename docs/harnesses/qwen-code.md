# ![Qwen Code logo](https://github.com/QwenLM.png?size=64){ .harness-logo } Qwen Code

`qwen-code` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.qwen/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `QWEN.md` + `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (or `./QWEN.md`) / `~/.qwen/AGENTS.md` (or `~/.qwen/QWEN.md`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [PR #2018](https://github.com/QwenLM/qwen-code/pull/2018) merged 2026-03-02 in `packages/core/src/tools/memoryTool.ts` adds `AGENT_CONTEXT_FILENAME = 'AGENTS.md'` and sets `currentGeminiMdFilename = [DEFAULT_CONTEXT_FILENAME, AGENT_CONTEXT_FILENAME]` (closes [#2006](https://github.com/QwenLM/qwen-code/issues/2006))

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.qwen/skills`
- **Global dir:** `~/.qwen/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.qwen/agents/<slug>.md` / `.qwen/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`,`systemPrompt`
- **Toolkit adapter:** enabled (translate)
- **Source:** [`packages/core/src/subagents/subagent-manager.ts:930-931`](https://github.com/QwenLM/qwen-code/blob/main/packages/core/src/subagents/subagent-manager.ts), `validation.ts:34-36`
