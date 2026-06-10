# ![MCPJam logo](https://www.google.com/s2/favicons?domain=mcpjam.com&sz=64){ .harness-logo } MCPJam

`mcpjam` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | — | no instruction-file concept |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.mcpjam/skills` |
| [Agents (subagents)](../kinds/agents.md) | — | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Not applicable — no root instruction-file concept at all.

- **Verdict:** unsupported (by design)
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** [www.mcpjam.com/](https://www.mcpjam.com/) ; [github.com/MCPJam/inspector](https://github.com/MCPJam/inspector)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.mcpjam/skills`
- **Global dir:** `~/.mcpjam/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** MCP inspector/testing tool, not a coding harness; no subagent concept
- **Source:** [github.com/MCPJam/inspector](https://github.com/MCPJam/inspector)
