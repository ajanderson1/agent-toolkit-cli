# ![Cursor logo](https://www.google.com/s2/favicons?domain=cursor.com&sz=64){ .harness-logo } Cursor

`cursor` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (also `.cursor/rules/*.mdc`)
- **Project / global path:** `./AGENTS.md` / Cursor Settings > Rules (UI, not file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://cursor.com/docs/rules

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.cursor/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.cursor/agents/<slug>.md` / `.cursor/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; optional `model`,`readonly`,`is_background`
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://cursor.com/docs/subagents
