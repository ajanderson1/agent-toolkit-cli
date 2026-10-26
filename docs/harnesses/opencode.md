# ![OpenCode logo](https://www.google.com/s2/favicons?domain=opencode.ai&sz=64){ .harness-logo } OpenCode

`opencode` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.config/opencode/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [opencode.ai/docs/rules/](https://opencode.ai/docs/rules/)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** `~/.config/opencode/AGENTS.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.config/opencode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/opencode/{agent,agents}/**/*.md` / `.opencode/{agent,agents}/**/*.md`
- **Format:** markdown+frontmatter; inject `mode: subagent`; name from filename; glob singular+plural
- **Toolkit adapter:** enabled (translate)
- **Source:** [`packages/opencode/src/config/agent.ts`](https://github.com/sst/opencode/blob/dev/packages/opencode/src/config/agent.ts) load(); [`agent/agent.ts:32`](https://github.com/sst/opencode/blob/dev/packages/opencode/src/agent/agent.ts)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found

## MCP servers { #mcp-servers }

Supported — the [MCP asset type](../asset-types/mcp.md) projects a library
MCP server into this harness's own config by name (config-injection). `opencode`
is one of the four harnesses with a config-injection adapter. Project
Standard covers Claude Code and Pi only; global uses concrete targets.
Bearer-token environment-name authentication is Pi-only; other targets refuse it.

- **Mechanism:** config-injection by name (no symlink/copy)
- **Source:** [`mcp_install.py`](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py) — the adapter target-config detection
