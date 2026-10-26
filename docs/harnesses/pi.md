# ![Pi logo](https://www.google.com/s2/favicons?domain=pi.dev&sz=64){ .harness-logo } Pi

`pi` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | dual-symlink |
| [Commands](../asset-types/commands.md) | [✅](#commands) | prompt templates (`.pi/agent/prompts`, `.pi/prompts`) |
| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |
| [Pi extensions](../asset-types/pi-extensions.md) | [✅](#pi-extensions) | symlink |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.pi/agent/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md) (current upstream README documents AGENTS.md loaded at startup from cwd + parents + `~/.pi/agent/AGENTS.md`)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** `~/.pi/agent/AGENTS.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **dual-symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

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
is one of the four harnesses with a config-injection adapter. Project
Standard covers Claude Code and Pi only; global uses concrete targets.
Bearer-token environment-name authentication is Pi-only; other targets refuse it.

- **Mechanism:** config-injection by name (no symlink/copy)
- **Source:** [`mcp_install.py`](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py) — the adapter target-config detection

## Pi extensions { #pi-extensions }

The [Pi extensions asset type](../asset-types/pi-extensions.md) targets Pi alone;
this does not classify other harnesses' unrelated plugin systems.
Git-backed extensions project into Pi's extension directory. Inventory also
includes npm packages and unmanaged local extensions; not every visible row is toggleable.

- **Source:** [pi.dev/docs/latest/extensions](https://pi.dev/docs/latest/extensions) — Pi's extension docs (packages, load paths)
