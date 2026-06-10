# Deep Agents

`deepagents` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [❌](#instructions) | no pointer-satisfiable root file |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | — | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** none (memory middleware requires explicit `agentId` + source paths)
- **Project / global path:** none (no auto-load) / none (no auto-load)
- **Reads `AGENTS.md` natively:** no
- **Source:** https://deepagentsdk.dev/docs/guides/agent-memory ("Create memory middleware" requires `createAgentMemoryMiddleware({ agentId })`; project memory only loads via `requestProjectApproval`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.deepagents/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Python library; subagents are code `SubAgent` TypedDicts; no file-drop convention
- **Source:** github.com/langchain-ai/deepagents .../middleware/subagents.py
