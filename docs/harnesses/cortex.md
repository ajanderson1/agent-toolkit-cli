# ![Cortex Code logo](https://www.google.com/s2/favicons?domain=snowflake.com&sz=64){ .harness-logo } Cortex Code

`cortex` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.cortex/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight) ("Create an `AGENTS.md` file … Cortex Code will automatically include in every conversation. Copy it to the root directory of your workspace"); `~/.snowflake/cortex/` CLI-config tree documents `skills/`, `agents/`, `commands/` but no global `AGENTS.md`

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.cortex/skills`
- **Global dir:** `~/.snowflake/cortex/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.snowflake/cortex/agents/` or `~/.claude/agents/` / `.cortex/agents/` or `.claude/agents/`
- **Format:** markdown+frontmatter; required `name`,`description`,`tools`(array or `*`); optional `model`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.snowflake.com/en/user-guide/cortex-code/extensibility](https://docs.snowflake.com/en/user-guide/cortex-code/extensibility)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
