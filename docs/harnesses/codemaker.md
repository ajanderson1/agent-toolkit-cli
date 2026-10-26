# ![Codemaker logo](https://github.com/codemakerai.png?size=64){ .harness-logo } Codemaker

`codemaker` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | N/A | no instruction-file concept |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.codemaker/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not applicable — no root instruction-file concept at all.

- **Project research verdict:** unsupported (by design)
- **Global research verdict:** unsupported (by design)
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** [github.com/codemakerai/codemaker-cli](https://github.com/codemakerai/codemaker-cli) README ("Context-aware source code generation … Generating source code documentation … Fixing syntax"; usage is `codemaker generate docs **/*.java`)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.codemaker/skills`
- **Global dir:** `~/.codemaker/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** batch code-gen CLI; no subagent concept
- **Source:** [github.com/codemakerai/codemaker-cli](https://github.com/codemakerai/codemaker-cli)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
