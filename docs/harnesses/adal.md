# ![AdaL logo](https://www.google.com/s2/favicons?domain=sylph.ai&sz=64){ .harness-logo } AdaL

`adal` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.adal/skills` |
| [Agents (subagents)](../kinds/agents.md) | [?](#agents) | no public evidence |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (nearest while walking up from cwd) / none documented (project-only auto-load)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [codingagents.md/agents/adal/](https://codingagents.md/agents/adal/) ; [docs.sylph.ai/](https://docs.sylph.ai/)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.adal/skills`
- **Global dir:** `~/.adal/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** AdaL CLI codebase private; public repo docs-only; no public subagent file convention
- **Source:** [codingagents.md/agents/adal](https://codingagents.md/agents/adal/)
