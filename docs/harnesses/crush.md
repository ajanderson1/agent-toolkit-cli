# ![Crush logo](https://github.com/charmbracelet.png?size=64){ .harness-logo } Crush

`crush` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.crush/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (global-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [charmbracelet/crush `internal/config/config.go`](https://github.com/charmbracelet/crush/blob/main/internal/config/config.go) — `defaultContextPaths` includes `AGENTS.md` / `agents.md` / `Agents.md`; `InitializeAs` JSON-schema `default=AGENTS.md`

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.crush/skills`
- **Global dir:** `~/.config/crush/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** delegation runtime-only (`agent`/`agentic_fetch` tools); no user agent files (issue #1807 open)
- **Source:** [charmbracelet/crush#1807](https://github.com/charmbracelet/crush/issues/1807)
