# ![Neovate logo](https://github.com/neovateai.png?size=64){ .harness-logo } Neovate

`neovate` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.neovate/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (project also walks for `CLAUDE.md`, `NEOVATE.md`; global also checks `NEOVATE.md` and `~/.claude/CLAUDE.md`)
- **Project / global path:** `<cwd>/AGENTS.md` walking up to filesystem root / `~/.neovate/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/neovateai/neovate-code/blob/master/src/rules.ts](https://github.com/neovateai/neovate-code/blob/master/src/rules.ts) (`getLlmsRules`, `projectRuleNames`/`globalRuleNames` starting with `'AGENTS.md'`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.neovate/skills`
- **Global dir:** `~/.neovate/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` (also `~/.neovate/agents/`) / `.claude/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(≤64),`description`(≤1024); Claude-identical
- **Toolkit adapter:** enabled (symlink)
- **Source:** [`neovateai/neovate-code:src/agent/agentManager.ts:162-235`](https://github.com/neovateai/neovate-code/blob/master/src/agent/agentManager.ts)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
