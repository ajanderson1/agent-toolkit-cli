# ![Augment logo](https://www.google.com/s2/favicons?domain=augmentcode.com&sz=64){ .harness-logo } Augment

`augment` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project, global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.augment/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`CLAUDE.md` (with `AGENTS.md` as documented fallback)) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `CLAUDE.md` (with `AGENTS.md` as documented fallback)
- **Project / global path:** `./CLAUDE.md` (workspace root) / `~/.augment/rules/` (directory loader; no fixed root file at user scope)
- **Reads `AGENTS.md` natively:** no (CLAUDE.md takes precedence over AGENTS.md per official rule chain)
- **Source:** [docs.augmentcode.com/cli/rules](https://docs.augmentcode.com/cli/rules)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/CLAUDE.md`
- **Toolkit global pointer:** `~/.augment/CLAUDE.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.augment/skills`
- **Global dir:** `~/.augment/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.augment/agents/<slug>.md` / `.augment/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`; optional `description`,`color`,`model`,`tools`/`disabled_tools` (denylist wins)
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.augmentcode.com/cli/subagents](https://docs.augmentcode.com/cli/subagents)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
