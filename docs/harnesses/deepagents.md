# ![Deep Agents logo](https://github.com/langchain-ai.png?size=64){ .harness-logo } Deep Agents

`deepagents` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [—](#instructions) | no pointer-satisfiable root file |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Project verdict:** unsupported (gap)
- **Global verdict:** unsupported (gap)
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** none (memory middleware requires explicit `agentId` + source paths)
- **Project / global path:** none (no auto-load) / none (no auto-load)
- **Reads `AGENTS.md` natively:** no
- **Source:** [deepagentsdk.dev/docs/guides/agent-memory](https://deepagentsdk.dev/docs/guides/agent-memory) ("Create memory middleware" requires `createAgentMemoryMiddleware({ agentId })`; project memory only loads via `requestProjectApproval`)

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.deepagents/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Python library; subagents are code `SubAgent` TypedDicts; no file-drop convention
- **Source:** [langchain-ai/deepagents libs/deepagents/deepagents/middleware/subagents.py](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/subagents.py)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
