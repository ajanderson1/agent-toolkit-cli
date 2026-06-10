# Cortex Code

`cortex` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.cortex/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight ("Create an `AGENTS.md` file … Cortex Code will automatically include in every conversation. Copy it to the root directory of your workspace"); `~/.snowflake/cortex/` CLI-config tree documents `skills/`, `agents/`, `commands/` but no global `AGENTS.md`

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.cortex/skills`
- **Global dir:** `~/.snowflake/cortex/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.snowflake/cortex/agents/` or `~/.claude/agents/` / `.cortex/agents/` or `.claude/agents/`
- **Format:** markdown+frontmatter; required `name`,`description`,`tools`(array or `*`); optional `model`
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://docs.snowflake.com/en/user-guide/cortex-code/extensibility
