# ![Continue logo](https://www.google.com/s2/favicons?domain=continue.dev&sz=64){ .harness-logo } Continue

`continue` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [—](#instructions) | no pointer-satisfiable root file |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.continue/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [?](#agents) | no public evidence |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Project research verdict:** unsupported (gap)
- **Global research verdict:** unsupported (gap)
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** none (uses `.continue/rules/` directory)
- **Project / global path:** `./.continue/rules/` / `~/.continue/rules/`
- **Reads `AGENTS.md` natively:** no
- **Source:** [docs.continue.dev/customize/deep-dives/rules](https://docs.continue.dev/customize/deep-dives/rules) ; [github.com/continuedev/continue/issues/6716](https://github.com/continuedev/continue/issues/6716)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.continue/skills`
- **Global dir:** `~/.continue/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** subagents in private testing (issue #9550), config.yaml-based; no stable public file spec
- **Source:** [continuedev/continue#9550](https://github.com/continuedev/continue/issues/9550)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
