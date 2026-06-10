# ![Replit logo](https://www.google.com/s2/favicons?domain=replit.com&sz=64){ .harness-logo } Replit

`replit` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | pointer symlink (`replit.md` → `AGENTS.md`) |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [❌](#agents) | no file-drop convention |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads a fixed own-name file (`replit.md`) instead of `AGENTS.md`. The [instructions kind](../kinds/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `replit.md`
- **Project / global path:** `./replit.md` (project root only) / none (project-only)
- **Reads `AGENTS.md` natively:** no
- **Source:** https://docs.replit.com/replitai/replit-dot-md

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.config/agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** Agent 3/4 spawns subagents at runtime; no user file-drop convention
- **Source:** https://docs.replit.com/replitai/agent
