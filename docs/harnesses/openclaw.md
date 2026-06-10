# ![OpenClaw logo](https://www.google.com/s2/favicons?domain=openclaw.ai&sz=64){ .harness-logo } OpenClaw

`openclaw` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `skills` |
| [Agents (subagents)](../kinds/agents.md) | [❌](#agents) | no file-drop convention |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** none (global/workspace-only) / `~/.openclaw/workspace/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.openclaw.ai/concepts/system-prompt](https://docs.openclaw.ai/concepts/system-prompt) + [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) README ("Injected prompt files: `AGENTS.md`, `SOUL.md`, `TOOLS.md`"; "Workspace root: `~/.openclaw/workspace`")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `skills`
- **Global dir:** `~/.openclaw/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** messaging-gateway personas (`~/.openclaw/agents/<id>/soul.md`), not coding subagents
- **Source:** [docs.openclaw.ai/concepts/multi-agent](https://docs.openclaw.ai/concepts/multi-agent)
