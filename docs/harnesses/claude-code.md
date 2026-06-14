# ![Claude Code logo](https://www.google.com/s2/favicons?domain=claude.com&sz=64){ .harness-logo } Claude Code

`claude-code` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | pointer symlink (`CLAUDE.md` → `AGENTS.md`) |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.claude/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`CLAUDE.md`) instead of `AGENTS.md`. The [instructions asset type](../asset-types/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `CLAUDE.md`
- **Project / global path:** `./CLAUDE.md` or `./.claude/CLAUDE.md` / `~/.claude/CLAUDE.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory) § "AGENTS.md" ("Claude Code reads `CLAUDE.md`, not `AGENTS.md`")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.claude/skills`
- **Global dir:** `~/.claude/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md` (recursive)
- **Format:** markdown+frontmatter; required `name`,`description`; extra keys ignored; 15 optional fields
- **Toolkit adapter:** enabled (symlink)
- **Source:** [code.claude.com/docs/en/sub-agents](https://code.claude.com/docs/en/sub-agents)

## MCP servers { #mcp-servers }

Supported — the [MCP asset type](../asset-types/mcp.md) projects a library
MCP server into this harness's own config by name (config-injection). `claude-code`
is one of the four harnesses with a config-injection adapter.

- **Mechanism:** config-injection by name (no symlink/copy)
- **Source:** [`mcp_install.py`](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py) — the adapter target-config detection
