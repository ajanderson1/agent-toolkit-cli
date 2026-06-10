# ![Devin for Terminal logo](https://www.google.com/s2/favicons?domain=devin.ai&sz=64){ .harness-logo } Devin for Terminal

`devin` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.devin/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.devin.ai/onboard-devin/agents-md](https://docs.devin.ai/onboard-devin/agents-md) ("Just put an `AGENTS.md` file in your project root … Devin will look for the file before it starts coding") and [docs.devin.ai/onboard-devin/knowledge-onboarding](https://docs.devin.ai/onboard-devin/knowledge-onboarding) (Knowledge is the user/global-scope mechanism, separate from `AGENTS.md`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.devin/skills`
- **Global dir:** `~/.config/devin/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/devin/agents/{profile}/AGENT.md` / `.devin/agents/{profile}/AGENT.md`
- **Format:** markdown+frontmatter; req `name`,`description`; per-profile-dir `AGENT.md`; also reads `.claude/agents/*.md`
- **Toolkit adapter:** enabled (translate)
- **Source:** [cli.devin.ai/docs/subagents](https://cli.devin.ai/docs/subagents)
