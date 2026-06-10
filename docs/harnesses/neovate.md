# ![Neovate logo](https://github.com/neovateai.png?size=64){ .harness-logo } Neovate

`neovate` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.neovate/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (project also walks for `CLAUDE.md`, `NEOVATE.md`; global also checks `NEOVATE.md` and `~/.claude/CLAUDE.md`)
- **Project / global path:** `<cwd>/AGENTS.md` walking up to filesystem root / `~/.neovate/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/neovateai/neovate-code/blob/master/src/rules.ts](https://github.com/neovateai/neovate-code/blob/master/src/rules.ts) (`getLlmsRules`, `projectRuleNames`/`globalRuleNames` starting with `'AGENTS.md'`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.neovate/skills`
- **Global dir:** `~/.neovate/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` (also `~/.neovate/agents/`) / `.claude/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(≤64),`description`(≤1024); Claude-identical
- **Toolkit adapter:** enabled (symlink)
- **Source:** [`neovateai/neovate-code:src/agent/agentManager.ts:162-235`](https://github.com/neovateai/neovate-code/blob/master/src/agent/agentManager.ts)
