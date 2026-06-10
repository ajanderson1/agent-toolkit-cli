# ![Trae logo](https://www.google.com/s2/favicons?domain=trae.ai&sz=64){ .harness-logo } Trae

`trae` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [—](#instructions) | no pointer-satisfiable root file |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.trae/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** `project_rules.md` (in `.trae/rules/` directory)
- **Project / global path:** `./.trae/rules/project_rules.md` / `./.trae/rules/user_rules.md` (workspace-level "user rules", not OS-global)
- **Reads `AGENTS.md` natively:** no
- **Source:** [docs.trae.ai/ide/rules?_lang=en](https://docs.trae.ai/ide/rules?_lang=en) ; [github.com/Trae-AI/Trae/issues/1911](https://github.com/Trae-AI/Trae/issues/1911)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.trae/skills`
- **Global dir:** `~/.trae/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** custom agents UI-configured (Builder), stored server-side; no on-disk file
- **Source:** [docs.trae.ai/ide/agent](https://docs.trae.ai/ide/agent)
