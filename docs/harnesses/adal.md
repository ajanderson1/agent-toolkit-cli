# ![AdaL logo](https://www.google.com/s2/favicons?domain=sylph.ai&sz=64){ .harness-logo } AdaL

`adal` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.adal/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [?](#agents) | no public evidence |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (nearest while walking up from cwd) / none documented (project-only auto-load)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [codingagents.md/agents/adal/](https://codingagents.md/agents/adal/) ; [docs.sylph.ai/](https://docs.sylph.ai/)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.adal/skills`
- **Global dir:** `~/.adal/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** AdaL CLI codebase private; public repo docs-only; no public subagent file convention
- **Source:** [codingagents.md/agents/adal](https://codingagents.md/agents/adal/)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
