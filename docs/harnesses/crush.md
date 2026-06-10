# ![Crush logo](https://github.com/charmbracelet.png?size=64){ .harness-logo } Crush

`crush` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.crush/skills` |
| [Agents (subagents)](../kinds/agents.md) | [❌](#agents) | no file-drop convention |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (global-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** charmbracelet/crush `internal/config/config.go` — `defaultContextPaths` includes `AGENTS.md` / `agents.md` / `Agents.md`; `InitializeAs` JSON-schema `default=AGENTS.md`

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.crush/skills`
- **Global dir:** `~/.config/crush/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** delegation runtime-only (`agent`/`agentic_fetch` tools); no user agent files (issue #1807 open)
- **Source:** github.com/charmbracelet/crush#1807
