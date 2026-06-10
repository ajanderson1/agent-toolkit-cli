# ![Continue logo](https://www.google.com/s2/favicons?domain=continue.dev&sz=64){ .harness-logo } Continue

`continue` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [—](#instructions) | no pointer-satisfiable root file |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.continue/skills` |
| [Agents (subagents)](../kinds/agents.md) | [?](#agents) | no public evidence |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** none (uses `.continue/rules/` directory)
- **Project / global path:** `./.continue/rules/` / `~/.continue/rules/`
- **Reads `AGENTS.md` natively:** no
- **Source:** [docs.continue.dev/customize/deep-dives/rules](https://docs.continue.dev/customize/deep-dives/rules) ; [github.com/continuedev/continue/issues/6716](https://github.com/continuedev/continue/issues/6716)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.continue/skills`
- **Global dir:** `~/.continue/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** subagents in private testing (issue #9550), config.yaml-based; no stable public file spec
- **Source:** [continuedev/continue#9550](https://github.com/continuedev/continue/issues/9550)
