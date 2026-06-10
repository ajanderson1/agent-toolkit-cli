# ![Deep Agents logo](https://github.com/langchain-ai.png?size=64){ .harness-logo } Deep Agents

`deepagents` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [—](#instructions) | no pointer-satisfiable root file |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | N/A | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** none (memory middleware requires explicit `agentId` + source paths)
- **Project / global path:** none (no auto-load) / none (no auto-load)
- **Reads `AGENTS.md` natively:** no
- **Source:** [deepagentsdk.dev/docs/guides/agent-memory](https://deepagentsdk.dev/docs/guides/agent-memory) ("Create memory middleware" requires `createAgentMemoryMiddleware({ agentId })`; project memory only loads via `requestProjectApproval`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.deepagents/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Python library; subagents are code `SubAgent` TypedDicts; no file-drop convention
- **Source:** [langchain-ai/deepagents libs/deepagents/deepagents/middleware/subagents.py](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/subagents.py)
