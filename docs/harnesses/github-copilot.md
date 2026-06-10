# GitHub Copilot

`github-copilot` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (repo root) / `$HOME/.copilot/copilot-instructions.md` (different name at user scope)
- **Reads `AGENTS.md` natively:** yes (project scope)
- **Source:** https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions ; https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.copilot/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.copilot/agents/<name>.agent.md` / `.github/agents/<name>.agent.md`
- **Format:** markdown+frontmatter; `.agent.md` suffix; required `description`; optional `name`,`tools`,`mcp-servers`,`model`,`target`
- **Toolkit adapter:** enabled (translate)
- **Source:** https://docs.github.com/en/copilot/reference/custom-agents-configuration
