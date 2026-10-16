# ![Devin for Terminal logo](https://www.google.com/s2/favicons?domain=devin.ai&sz=64){ .harness-logo } Devin for Terminal

`devin` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.devin/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [Commands](../asset-types/commands.md) | [✅](#commands) | project Standard slot (`.claude/commands`), imported as skills; no global command adapter |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.devin.ai/onboard-devin/agents-md](https://docs.devin.ai/onboard-devin/agents-md) ("Just put an `AGENTS.md` file in your project root … Devin will look for the file before it starts coding") and [docs.devin.ai/onboard-devin/knowledge-onboarding](https://docs.devin.ai/onboard-devin/knowledge-onboarding) (Knowledge is the user/global-scope mechanism, separate from `AGENTS.md`)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.devin/skills`
- **Global dir:** `~/.config/devin/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/devin/agents/{profile}/AGENT.md` / `.devin/agents/{profile}/AGENT.md` (also `.agents/agents/{profile}/AGENT.md`)
- **Format:** markdown+frontmatter; req `name`,`description`; per-profile-dir `AGENT.md`; also imports project-relative `.claude/agents/*.md` (project scope only)
- **Toolkit adapter:** enabled (translate)
- **Source:** [docs.devin.ai/cli/subagents](https://docs.devin.ai/cli/subagents) (cli.devin.ai/docs/subagents now 301s here; re-verified 2026-06-10)

## Commands { #commands }

Supported by the [commands asset type](../asset-types/commands.md).

- **Support:** ✅
- **How:** project Standard slot (`.claude/commands`), imported as skills; no global command adapter
