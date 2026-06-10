# ![Roo Code logo](https://www.google.com/s2/favicons?domain=roocode.com&sz=64){ .harness-logo } Roo Code

`roo` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.roo/skills` |
| [Agents (subagents)](../kinds/agents.md) | [❌](#agents) | no file-drop convention |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.roo/rules/` (directory, not single file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://roocodeinc.github.io/Roo-Code/features/custom-instructions

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.roo/skills`
- **Global dir:** `~/.roo/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** custom modes (`.roomodes`) delegation targets via `new_task` but mode-switch, not independent-context spawn
- **Source:** roocodeinc.github.io/Roo-Code/features/custom-modes
