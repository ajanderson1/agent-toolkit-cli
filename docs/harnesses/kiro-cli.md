# ![Kiro CLI logo](https://www.google.com/s2/favicons?domain=kiro.dev&sz=64){ .harness-logo } Kiro CLI

`kiro-cli` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.kiro/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (workspace root) / `~/.kiro/steering/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://kiro.dev/docs/cli/steering/

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.kiro/skills`
- **Global dir:** `~/.kiro/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.kiro/agents/<name>.json` / `.kiro/agents/<name>.json`
- **Format:** JSON (not markdown); filename=agent ID; optional `name`,`description`,`prompt`,`model`,`tools`
- **Toolkit adapter:** enabled (translate)
- **Source:** https://kiro.dev/docs/cli/custom-agents/configuration-reference/
