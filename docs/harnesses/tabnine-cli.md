# ![Tabnine CLI logo](https://www.google.com/s2/favicons?domain=tabnine.com&sz=64){ .harness-logo } Tabnine CLI

`tabnine-cli` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | pointer symlink (`TABNINE.md` → `AGENTS.md`) |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.tabnine/agent/skills` |
| [Agents (subagents)](../kinds/agents.md) | — | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads a fixed own-name file (`TABNINE.md`) instead of `AGENTS.md`. The [instructions kind](../kinds/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `TABNINE.md`
- **Project / global path:** `./TABNINE.md` / unclear (no documented global `TABNINE.md` path; `~/.tabnine/guidelines/*.md` is a *directory* of guidelines, not the same file)
- **Reads `AGENTS.md` natively:** no
- **Source:** https://docs.tabnine.com/main/getting-started/tabnine-cli/getting-started/quickstart ("Add project context with a `TABNINE.md` file in your project root") and https://docs.tabnine.com/main/getting-started/tabnine-cli/features/agent-skills ("Unlike `TABNINE.md` project instructions (which load automatically on every session), skills load only when relevant")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.tabnine/agent/skills`
- **Global dir:** `~/.tabnine/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Enterprise Agent internal mini-agent routing; not user-definable
- **Source:** https://docs.tabnine.com/main/getting-started/tabnine-cli
