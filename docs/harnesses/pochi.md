# ![Pochi logo](https://www.google.com/s2/favicons?domain=getpochi.com&sz=64){ .harness-logo } Pochi

`pochi` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.pochi/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `README.pochi.md` OR `AGENTS.md` (treated identically)
- **Project / global path:** `./AGENTS.md` (or `./README.pochi.md`) / `~/.pochi/README.pochi.md` (AGENTS.md alternative implied — docs say files are "treated identically")
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.getpochi.com/rules/](https://docs.getpochi.com/rules/)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.pochi/skills`
- **Global dir:** `~/.pochi/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.pochi/agents/<name>.md` / `.pochi/agents/<name>.md`
- **Format:** markdown+frontmatter; required `description`; optional `name`,`tools`; spawn via `newTask(<name>)`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.getpochi.com/custom-agent](https://docs.getpochi.com/custom-agent)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
