# Pi

`pi` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.pi/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | dual-symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | [✅](#pi-extensions) | symlink |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.pi/agent/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md (current upstream README documents AGENTS.md loaded at startup from cwd + parents + `~/.pi/agent/AGENTS.md`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.pi/skills`
- **Global dir:** `~/.pi/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **dual-symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** dual-symlink
- **User / project path:** `~/.pi/agent/agents/<slug>.md` / `.pi/agents/<slug>.md` (legacy `.agents/` fallback)
- **Format:** markdown+frontmatter (all optional); read by 3rd-party `@tintinweb/pi-subagents` ext
- **Toolkit adapter:** enabled (symlink)
- **Source:** github.com/tintinweb/pi-subagents ; pi.dev/packages/pi-subagents

## Pi extensions { #pi-extensions }

Pi is the only harness with an extension-package concept, so the
[pi-extension kind](../kinds/pi-extensions.md) targets Pi alone.
Extensions are git-sourced (branch- or SHA-pinned) and projected by
symlink into Pi's extension directory.
