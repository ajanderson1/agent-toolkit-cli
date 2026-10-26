# ![Claude Code logo](https://www.google.com/s2/favicons?domain=claude.com&sz=64){ .harness-logo } Claude Code

`claude-code` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project, global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.claude/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [✅](#commands) | shared Standard slot (`.claude/commands`) |
| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`CLAUDE.md`) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `CLAUDE.md`
- **Project / global path:** `./CLAUDE.md` or `./.claude/CLAUDE.md` / `~/.claude/CLAUDE.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory) § "AGENTS.md" ("Claude Code reads `CLAUDE.md`, not `AGENTS.md`")

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/CLAUDE.md`
- **Toolkit global pointer:** `~/.claude/CLAUDE.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.claude/skills`
- **Global dir:** `~/.claude/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md` (recursive)
- **Format:** markdown+frontmatter; required `name`,`description`; extra keys ignored; 15 optional fields
- **Toolkit adapter:** enabled (symlink)
- **Source:** [code.claude.com/docs/en/sub-agents](https://code.claude.com/docs/en/sub-agents)

## Commands { #commands }

Supported by the [commands asset type](../asset-types/commands.md).

- **Support:** ✅
- **How:** shared Standard slot (`.claude/commands`)

## MCP servers { #mcp-servers }

Supported — the [MCP asset type](../asset-types/mcp.md) projects a library
MCP server into this harness's own config by name (config-injection). `claude-code`
is one of the four harnesses with a config-injection adapter. Project
Standard covers Claude Code and Pi only; global uses concrete targets.
Bearer-token environment-name authentication is Pi-only; other targets refuse it.

- **Mechanism:** config-injection by name (no symlink/copy)
- **Source:** [`mcp_install.py`](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py) — the adapter target-config detection
