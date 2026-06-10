# ![Trae logo](https://www.google.com/s2/favicons?domain=trae.ai&sz=64){ .harness-logo } Trae

`trae` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [❌](#instructions) | no pointer-satisfiable root file |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.trae/skills` |
| [Agents (subagents)](../kinds/agents.md) | — | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** `project_rules.md` (in `.trae/rules/` directory)
- **Project / global path:** `./.trae/rules/project_rules.md` / `./.trae/rules/user_rules.md` (workspace-level "user rules", not OS-global)
- **Reads `AGENTS.md` natively:** no
- **Source:** https://docs.trae.ai/ide/rules?_lang=en ; https://github.com/Trae-AI/Trae/issues/1911

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.trae/skills`
- **Global dir:** `~/.trae/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** custom agents UI-configured (Builder), stored server-side; no on-disk file
- **Source:** https://docs.trae.ai/ide/agent
