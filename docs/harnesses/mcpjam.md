# ![MCPJam logo](https://www.google.com/s2/favicons?domain=mcpjam.com&sz=64){ .harness-logo } MCPJam

`mcpjam` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | N/A | no instruction-file concept |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.mcpjam/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not applicable — no root instruction-file concept at all.

- **Project verdict:** unsupported (by design)
- **Global verdict:** unsupported (by design)
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** [www.mcpjam.com/](https://www.mcpjam.com/) ; [github.com/MCPJam/inspector](https://github.com/MCPJam/inspector)

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.mcpjam/skills`
- **Global dir:** `~/.mcpjam/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** MCP inspector/testing tool, not a coding harness; no subagent concept
- **Source:** [github.com/MCPJam/inspector](https://github.com/MCPJam/inspector)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
