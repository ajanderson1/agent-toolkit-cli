# ![Gemini CLI logo](https://github.com/google-gemini.png?size=64){ .harness-logo } Gemini CLI

`gemini-cli` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project, global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [Commands](../asset-types/commands.md) | [✅](#commands) | TOML custom commands (`.gemini/commands`) |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`GEMINI.md`) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `GEMINI.md`
- **Project / global path:** `./GEMINI.md` / `~/.gemini/GEMINI.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** [`packages/core/src/tools/memoryTool.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/memoryTool.ts) — `export const DEFAULT_CONTEXT_FILENAME = 'GEMINI.md';` + [`docs/cli/gemini-md.md`](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/GEMINI.md`
- **Toolkit global pointer:** `~/.gemini/GEMINI.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.gemini/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.gemini/agents/<slug>.md` / `.gemini/agents/<slug>.md`
- **Format:** markdown+frontmatter; ONLY `name`+`description` (zod `.strict()` rejects extras)
- **Toolkit adapter:** enabled (translate)
- **Source:** [`packages/core/src/agents/agentLoader.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/agents/agentLoader.ts) localAgentSchema.strict() + `storage.ts:117-118,309-310`

## Commands { #commands }

Supported by the [commands asset type](../asset-types/commands.md).

- **Support:** ✅
- **How:** TOML custom commands (`.gemini/commands`)
