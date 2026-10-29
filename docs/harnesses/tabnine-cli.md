# ![Tabnine CLI logo](https://www.google.com/s2/favicons?domain=tabnine.com&sz=64){ .harness-logo } Tabnine CLI

`tabnine-cli` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project, global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.tabnine/agent/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`TABNINE.md`) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `TABNINE.md`
- **Project / global path:** `./TABNINE.md` / `~/.tabnine/guidelines/AGENTS.md` (Toolkit pointer inside Tabnine's Markdown-guidelines directory)
- **Reads `AGENTS.md` natively:** no
- **Source:** [docs.tabnine.com/main/getting-started/tabnine-cli/getting-started/quickstart](https://docs.tabnine.com/main/getting-started/tabnine-cli/getting-started/quickstart) (project `TABNINE.md`) and [docs.tabnine.com/main/getting-started/tabnine-agent/guidelines](https://docs.tabnine.com/main/getting-started/tabnine-agent/guidelines) (personal/project `.tabnine/guidelines/*.md`)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/TABNINE.md`
- **Toolkit global pointer:** `~/.tabnine/guidelines/AGENTS.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.tabnine/agent/skills`
- **Global dir:** `~/.tabnine/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Enterprise Agent internal mini-agent routing; not user-definable
- **Source:** [docs.tabnine.com/main/getting-started/tabnine-cli](https://docs.tabnine.com/main/getting-started/tabnine-cli)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
