# OpenHands

`openhands` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.openhands/skills` |
| [Agents (subagents)](../kinds/agents.md) | [❌](#agents) | no file-drop convention |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (workspace root) / none documented (project-only auto-load)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://docs.openhands.dev/sdk/guides/skill

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.openhands/skills`
- **Global dir:** `~/.openhands/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** microagents/skills = prompt injection on keyword, not spawn; `.openhands/skills/`
- **Source:** https://docs.openhands.dev/overview/skills
