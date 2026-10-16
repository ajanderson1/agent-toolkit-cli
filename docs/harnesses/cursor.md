# ![Cursor logo](https://www.google.com/s2/favicons?domain=cursor.com&sz=64){ .harness-logo } Cursor

`cursor` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [—](#commands) | research gap; forum evidence only, no deterministic adapter yet |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md` (also `.cursor/rules/*.mdc`)
- **Project / global path:** `./AGENTS.md` / Cursor Settings > Rules (UI, not file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [cursor.com/docs/rules](https://cursor.com/docs/rules)

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.cursor/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.cursor/agents/<slug>.md` (also `~/.claude/agents/`, `~/.codex/agents/`) / `.cursor/agents/<slug>.md` (also `.claude/agents/`, `.codex/agents/`)
- **Format:** markdown+frontmatter; required `name`,`description`; optional `model`,`readonly`,`is_background`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [cursor.com/docs/subagents](https://cursor.com/docs/subagents) (re-verified 2026-06-10: `.claude/agents/` + `~/.claude/agents/` are default discovery locations)

## Commands { #commands }

Not supported by the toolkit yet — tracked as a researched gap.

- **Support:** —
- **How:** research gap; forum evidence only, no deterministic adapter yet
