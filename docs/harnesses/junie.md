# ![Junie logo](https://www.google.com/s2/favicons?domain=jetbrains.com&sz=64){ .harness-logo } Junie

`junie` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.junie/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./.junie/AGENTS.md` (preferred) or `./AGENTS.md` (fallback) / `~/.junie/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [junie.jetbrains.com/docs/guidelines-and-memory.html](https://junie.jetbrains.com/docs/guidelines-and-memory.html)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.junie/skills`
- **Global dir:** `~/.junie/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.junie/agents/<slug>.md` (also `~/.agents/`) / `.junie/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `description`; Claude-compatible optional fields
- **Toolkit adapter:** enabled (symlink)
- **Source:** [junie.jetbrains.com/docs/junie-cli-subagents.html](https://junie.jetbrains.com/docs/junie-cli-subagents.html)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
