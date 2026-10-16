# ![Kimi Code CLI logo](https://github.com/moonshotai.png?size=64){ .harness-logo } Kimi Code CLI

`kimi-cli` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `<git-root>/AGENTS.md` (walks git-root → cwd, plus `.kimi/AGENTS.md`) / none (global-only AGENTS.md not documented; user config lives at `~/.kimi/config.toml`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [moonshotai.github.io/kimi-cli/en/release-notes/changelog.html](https://moonshotai.github.io/kimi-cli/en/release-notes/changelog.html) (v1.29.0 2026-04-01)

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.config/agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** YAML via explicit `--agent-file` flag only; no auto-scanned dir
- **Source:** [moonshotai.github.io/kimi-cli/en/customization/agents.html](https://moonshotai.github.io/kimi-cli/en/customization/agents.html)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
