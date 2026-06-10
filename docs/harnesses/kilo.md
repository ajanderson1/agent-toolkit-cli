# ![Kilo Code logo](https://www.google.com/s2/favicons?domain=kilo.ai&sz=64){ .harness-logo } Kilo Code

`kilo` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.kilocode/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [kilo.ai/docs/agent-behavior/agents-md](https://kilo.ai/docs/agent-behavior/agents-md)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.kilocode/skills`
- **Global dir:** `~/.kilocode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/kilo/agent/<slug>.md` / `.kilo/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `description`,`mode`(inject `subagent`); optional `model`,`permission`
- **Toolkit adapter:** enabled (translate)
- **Source:** [kilo.ai/docs/agent-behavior/custom-modes](https://kilo.ai/docs/agent-behavior/custom-modes)
