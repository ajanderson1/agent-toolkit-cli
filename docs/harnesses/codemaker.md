# ![Codemaker logo](https://github.com/codemakerai.png?size=64){ .harness-logo } Codemaker

`codemaker` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | N/A | no instruction-file concept |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.codemaker/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not applicable — no root instruction-file concept at all.

- **Verdict:** unsupported (by design)
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** [github.com/codemakerai/codemaker-cli](https://github.com/codemakerai/codemaker-cli) README ("Context-aware source code generation … Generating source code documentation … Fixing syntax"; usage is `codemaker generate docs **/*.java`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.codemaker/skills`
- **Global dir:** `~/.codemaker/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** batch code-gen CLI; no subagent concept
- **Source:** [github.com/codemakerai/codemaker-cli](https://github.com/codemakerai/codemaker-cli)
