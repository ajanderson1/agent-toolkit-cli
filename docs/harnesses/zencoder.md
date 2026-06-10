# Zencoder

`zencoder` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.zencoder/skills` |
| [Agents (subagents)](../kinds/agents.md) | — | no subagent concept |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none documented (the `.zencoder/rules/*.md` tree is a *directory* of rules, not a global `AGENTS.md`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** Feb 2026 Zencoder changelog reports "AGENTS.md support — agent instructions are now resolved from AGENTS.md files at the CLI level" (https://docs.zencoder.ai/changelog/february-2026, surfaced via search; page returns 403 to anonymous fetch)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.zencoder/skills`
- **Global dir:** `~/.zencoder/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Zen Agents marketplace/UI-defined; no local file-drop dir
- **Source:** https://zencoder.ai/blog/introducing-zen-agents...
