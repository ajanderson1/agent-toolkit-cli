# ![Pi logo](https://www.google.com/s2/favicons?domain=pi.dev&sz=64){ .harness-logo } Pi

`pi` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | shared `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | dual-symlink |
| [Commands](../asset-types/commands.md) | [✅](#commands) | prompt templates (`.pi/agent/prompts`, `.pi/prompts`) |
| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |
| [Pi extensions](../asset-types/pi-extensions.md) | [✅](#pi-extensions) | symlink |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.pi/agent/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md) (current upstream README documents AGENTS.md loaded at startup from cwd + parents + `~/.pi/agent/AGENTS.md`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes
- **TUI:** included in the shared Standard Skills column, not a separate Pi column.
- **Source:** Pi native Agent Skills discovery. This deliberately differs from the vendored upstream directory catalog.

`skill doctor` offers cleanup of legacy `.pi/skills` and `~/.pi/agent/skills` symlinks only when they point to the same scope's toolkit canonical skill. Foreign links, real files/directories, symlinked legacy roots, and declared external projections remain untouched. Other Pi asset paths do not change.

## Agents (subagents) { #agents }

Supported via the **dual-symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** dual-symlink
- **User / project path:** `~/.pi/agent/agents/<slug>.md` / `.pi/agents/<slug>.md` (legacy `.agents/` fallback)
- **Format:** markdown+frontmatter (all optional); read by 3rd-party `@tintinweb/pi-subagents` ext
- **Toolkit adapter:** enabled (symlink)
- **Source:** [github.com/tintinweb/pi-subagents](https://github.com/tintinweb/pi-subagents) ; [pi.dev/packages/pi-subagents](https://pi.dev/packages/pi-subagents)

## Commands { #commands }

Supported by the [commands asset type](../asset-types/commands.md).

- **Support:** ✅
- **How:** prompt templates (`.pi/agent/prompts`, `.pi/prompts`)

## MCP servers { #mcp-servers }

Supported — the [MCP asset type](../asset-types/mcp.md) projects a library
MCP server into this harness's own config by name (config-injection). `pi`
is one of the four harnesses with a config-injection adapter.

- **Mechanism:** config-injection by name (no symlink/copy)
- **Source:** [`mcp_install.py`](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py) — the adapter target-config detection

## Pi extensions { #pi-extensions }

Pi is the only harness with an extension-package concept, so the
[pi-extension asset type](../asset-types/pi-extensions.md) targets Pi alone.
Extensions are git-sourced (branch- or SHA-pinned) and projected by
symlink into Pi's extension directory.

- **Source:** [pi.dev/docs/latest/extensions](https://pi.dev/docs/latest/extensions) — Pi's extension docs (packages, load paths)
