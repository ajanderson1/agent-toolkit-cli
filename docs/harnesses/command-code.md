# ![Command Code logo](https://www.google.com/s2/favicons?domain=commandcode.ai&sz=64){ .harness-logo } Command Code

`command-code` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.commandcode/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only — no documented user-level instruction file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [commandcode.ai/features](https://commandcode.ai/features) § "AGENTS.md Project Memory" ("Define project-level instructions, code style guidelines, and architecture notes. Automatically loaded every session.")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.commandcode/skills`
- **Global dir:** `~/.commandcode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.commandcode/agents/<slug>.md` / `.commandcode/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`,`tools`; reserved names blocked
- **Toolkit adapter:** enabled (symlink)
- **Source:** [commandcode.ai/docs/core-concepts/custom-agents](https://commandcode.ai/docs/core-concepts/custom-agents)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
