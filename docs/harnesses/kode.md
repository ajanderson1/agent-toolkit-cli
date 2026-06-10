# Kode

`kode` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.kode/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (prefers `AGENTS.override.md`) / none (project-only; `~/.kode.json` is JSON config, not an instruction file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://github.com/shareAI-lab/Kode-cli README § "AGENTS.md Standard Support" ("Native support for the OpenAI-initiated standard format … prefers `AGENTS.override.md` over `AGENTS.md`")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.kode/skills`
- **Global dir:** `~/.kode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` (also `~/.kode/agents/`) / `.claude/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; `model_name` (not `model`)
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md
