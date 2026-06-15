# ![Cortex Code logo](https://www.google.com/s2/favicons?domain=snowflake.com&sz=64){ .harness-logo } Cortex Code

`cortex` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.cortex/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight) ("Create an `AGENTS.md` file … Cortex Code will automatically include in every conversation. Copy it to the root directory of your workspace"); `~/.snowflake/cortex/` CLI-config tree documents `skills/`, `agents/`, `commands/` but no global `AGENTS.md`

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.cortex/skills`
- **Global dir:** `~/.snowflake/cortex/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.snowflake/cortex/agents/` or `~/.claude/agents/` / `.cortex/agents/` or `.claude/agents/`
- **Format:** markdown+frontmatter; required `name`,`description`,`tools`(array or `*`); optional `model`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.snowflake.com/en/user-guide/cortex-code/extensibility](https://docs.snowflake.com/en/user-guide/cortex-code/extensibility)
