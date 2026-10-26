# ![Neovate logo](https://github.com/neovateai.png?size=64){ .harness-logo } Neovate

`neovate` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.neovate/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [✅](#commands) | shared Standard slot (`.claude/commands`), both scopes |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md` (project also walks for `CLAUDE.md`, `NEOVATE.md`; global also checks `NEOVATE.md` and `~/.claude/CLAUDE.md`)
- **Project / global path:** `<cwd>/AGENTS.md` walking up to filesystem root / `~/.neovate/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/neovateai/neovate-code/blob/master/src/rules.ts](https://github.com/neovateai/neovate-code/blob/master/src/rules.ts) (`getLlmsRules`, `projectRuleNames`/`globalRuleNames` starting with `'AGENTS.md'`)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.neovate/skills`
- **Global dir:** `~/.neovate/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` (also `~/.neovate/agents/`) / `.claude/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(≤64),`description`(≤1024); Claude-identical
- **Toolkit adapter:** enabled (symlink)
- **Source:** [`neovateai/neovate-code:src/agent/agentManager.ts:162-235`](https://github.com/neovateai/neovate-code/blob/master/src/agent/agentManager.ts)

## Commands { #commands }

Supported by the [commands asset type](../asset-types/commands.md).

- **Support:** ✅
- **How:** shared Standard slot (`.claude/commands`), both scopes
