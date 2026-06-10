# Code Studio

`codestudio` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [?](#instructions) | no public evidence |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.codestudio/skills` |
| [Agents (subagents)](../kinds/agents.md) | [?](#agents) | no public evidence |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** (exhaustive search: ByteDance/Trae, Alibaba/Qoder, Baidu/Comate, Tencent/CodeBuddy, Volcano Engine — no product literally named "codestudio" found)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.codestudio/skills`
- **Global dir:** `~/.codestudio/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** no product 'codestudio' found across vendors/GitHub/roundups; may be placeholder
- **Source:** exhaustive search, no source
