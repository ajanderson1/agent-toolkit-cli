# ![Codex logo](https://www.google.com/s2/favicons?domain=openai.com&sz=64){ .harness-logo } Codex

`codex` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths; global pointer slot |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | config_file+folder |
| [Commands](../asset-types/commands.md) | [✅](#commands) | deprecated custom prompts; global only (`~/.codex/prompts`) |
| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `<git-root>/AGENTS.md` (walks git-root → cwd) / `~/.codex/AGENTS.md` (or `AGENTS.override.md`; honors `$CODEX_HOME`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [developers.openai.com/codex/guides/agents-md](https://developers.openai.com/codex/guides/agents-md)

A global pointer slot is managed separately from project native reading; install links it to user-authored `~/.agent-toolkit/AGENTS.md`. Only supported/requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.codex/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **config_file+folder**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `~/.codex/agents/<slug>.toml` + `[agents.<role>]` in `~/.codex/config.toml` / `.codex/agents/<slug>.toml`
- **Format:** TOML; role decl req `description`; file req `developer_instructions`; registered via `config_file=`
- **Toolkit adapter:** currently disabled — registry-gated shared config.toml — no safe escape hatch; pending AJ decision (PR5a)
- **Source:** [developers.openai.com/codex/subagents](https://developers.openai.com/codex/subagents) + [`codex-rs/config/src/config_toml.rs:649-691`](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs)

## Commands { #commands }

Supported by the [commands asset type](../asset-types/commands.md).

- **Support:** ✅
- **How:** deprecated custom prompts; global only (`~/.codex/prompts`)

## MCP servers { #mcp-servers }

Supported — the [MCP asset type](../asset-types/mcp.md) projects a library
MCP server into this harness's own config by name (config-injection). `codex`
is one of the four harnesses with a config-injection adapter. Project
Standard covers Claude Code and Pi only; global uses concrete targets.
Bearer-token environment-name authentication is Pi-only; other targets refuse it.

- **Mechanism:** config-injection by name (no symlink/copy)
- **Source:** [`mcp_install.py`](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py) — the adapter target-config detection
