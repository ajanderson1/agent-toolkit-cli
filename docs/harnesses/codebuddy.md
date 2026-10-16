# ![CodeBuddy logo](https://www.google.com/s2/favicons?domain=codebuddy.ai&sz=64){ .harness-logo } CodeBuddy

`codebuddy` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project, global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.codebuddy/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`CODEBUDDY.md`) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `CODEBUDDY.md`
- **Project / global path:** `./CODEBUDDY.md` (recursive up from cwd) / `~/.codebuddy/CODEBUDDY.md`
- **Reads `AGENTS.md` natively:** no (own-name preferred; AGENTS.md only as fallback when CODEBUDDY.md absent)
- **Source:** [www.codebuddy.ai/docs/cli/memory](https://www.codebuddy.ai/docs/cli/memory)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/CODEBUDDY.md`
- **Toolkit global pointer:** `~/.codebuddy/CODEBUDDY.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.codebuddy/skills`
- **Global dir:** `~/.codebuddy/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.codebuddy/agents/<slug>.md` / `.codebuddy/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(lc+hyphens),`description`; optional `tools`,`model`,`permissionMode`,`skills`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [www.codebuddy.ai/docs/cli/sub-agents](https://www.codebuddy.ai/docs/cli/sub-agents)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
