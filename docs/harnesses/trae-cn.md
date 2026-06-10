# Trae CN

`trae-cn` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.trae/skills` |
| [Agents (subagents)](../kinds/agents.md) | — | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (alongside `.trae/rules/project_rules.md`)
- **Project / global path:** `./AGENTS.md` (and nested sub-directory `AGENTS.md`) / `./.trae/rules/user_rules.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://forum.trae.cn/t/topic/52 ; Trae CN changelog 2026-04-15 ("Rules 支持嵌套：子仓目录下的 Rule 文件（包括 AGENTS.md）")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.trae/skills`
- **Global dir:** `~/.trae-cn/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** same product as Trae (diff models); identical UI-agent architecture, no file
- **Source:** technode.com/2025/03/04 ByteDance Trae CN
