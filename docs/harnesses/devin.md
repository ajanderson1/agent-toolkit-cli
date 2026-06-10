# Devin for Terminal

`devin` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.devin/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://docs.devin.ai/onboard-devin/agents-md ("Just put an `AGENTS.md` file in your project root … Devin will look for the file before it starts coding") and https://docs.devin.ai/onboard-devin/knowledge-onboarding (Knowledge is the user/global-scope mechanism, separate from `AGENTS.md`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.devin/skills`
- **Global dir:** `~/.config/devin/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/devin/agents/{profile}/AGENT.md` / `.devin/agents/{profile}/AGENT.md`
- **Format:** markdown+frontmatter; req `name`,`description`; per-profile-dir `AGENT.md`; also reads `.claude/agents/*.md`
- **Toolkit adapter:** enabled (translate)
- **Source:** https://cli.devin.ai/docs/subagents
