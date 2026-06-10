# MCPJam

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
- **Source:** https://www.mcpjam.com/ ; https://github.com/MCPJam/inspector

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.mcpjam/skills`
- **Global dir:** `~/.mcpjam/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** MCP inspector/testing tool, not a coding harness; no subagent concept
- **Source:** github.com/MCPJam/inspector
