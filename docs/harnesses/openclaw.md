# ![OpenClaw logo](https://www.google.com/s2/favicons?domain=openclaw.ai&sz=64){ .harness-logo } OpenClaw

`openclaw` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** none (global/workspace-only) / `~/.openclaw/workspace/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.openclaw.ai/concepts/system-prompt](https://docs.openclaw.ai/concepts/system-prompt) + [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) README ("Injected prompt files: `AGENTS.md`, `SOUL.md`, `TOOLS.md`"; "Workspace root: `~/.openclaw/workspace`")

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `skills`
- **Global dir:** `~/.openclaw/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** messaging-gateway personas (`~/.openclaw/agents/<id>/soul.md`), not coding subagents
- **Source:** [docs.openclaw.ai/concepts/multi-agent](https://docs.openclaw.ai/concepts/multi-agent)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
