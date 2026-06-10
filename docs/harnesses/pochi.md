# ![Pochi logo](https://www.google.com/s2/favicons?domain=getpochi.com&sz=64){ .harness-logo } Pochi

`pochi` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.pochi/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `README.pochi.md` OR `AGENTS.md` (treated identically)
- **Project / global path:** `./AGENTS.md` (or `./README.pochi.md`) / `~/.pochi/README.pochi.md` (AGENTS.md alternative implied — docs say files are "treated identically")
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://docs.getpochi.com/rules/

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.pochi/skills`
- **Global dir:** `~/.pochi/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.pochi/agents/<name>.md` / `.pochi/agents/<name>.md`
- **Format:** markdown+frontmatter; required `description`; optional `name`,`tools`; spawn via `newTask(<name>)`
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://docs.getpochi.com/custom-agent
