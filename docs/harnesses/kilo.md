# ![Kilo Code logo](https://www.google.com/s2/favicons?domain=kilo.ai&sz=64){ .harness-logo } Kilo Code

`kilo` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.kilocode/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [kilo.ai/docs/agent-behavior/agents-md](https://kilo.ai/docs/agent-behavior/agents-md)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.kilocode/skills`
- **Global dir:** `~/.kilocode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/kilo/agent/<slug>.md` / `.kilo/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `description`,`mode`(inject `subagent`); optional `model`,`permission`
- **Toolkit adapter:** enabled (translate)
- **Source:** [kilo.ai/docs/agent-behavior/custom-modes](https://kilo.ai/docs/agent-behavior/custom-modes)
