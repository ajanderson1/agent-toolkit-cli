# ![Trae CN logo](https://www.google.com/s2/favicons?domain=trae.cn&sz=64){ .harness-logo } Trae CN

`trae-cn` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.trae/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (alongside `.trae/rules/project_rules.md`)
- **Project / global path:** `./AGENTS.md` (and nested sub-directory `AGENTS.md`) / `./.trae/rules/user_rules.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [forum.trae.cn/t/topic/52](https://forum.trae.cn/t/topic/52) ; Trae CN changelog 2026-04-15 ("Rules 支持嵌套：子仓目录下的 Rule 文件（包括 AGENTS.md）")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.trae/skills`
- **Global dir:** `~/.trae-cn/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** same product as Trae (diff models); identical UI-agent architecture, no file
- **Source:** [technode.com 2025-03-04: ByteDance Trae CN](https://technode.com/2025/03/04/)
