# ![Rovo Dev logo](https://www.google.com/s2/favicons?domain=atlassian.com&sz=64){ .harness-logo } Rovo Dev

`rovodev` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.rovodev/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.rovodev/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [paul-hackenberger.medium.com/atlassian-rovodev-the-king-of-kontext-6bd7a77b5b37](https://paul-hackenberger.medium.com/atlassian-rovodev-the-king-of-kontext-6bd7a77b5b37) ("Place an `AGENTS.md` file in your repository root … Rovo Dev reads this automatically" and "Create an `AGENTS.md` file in your `~/.rovodev` folder … Rovo Dev reads these files automatically, giving every interaction team-specific context")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.rovodev/skills`
- **Global dir:** `~/.rovodev/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.rovodev/subagents/<slug>.md` / `.rovodev/subagents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`,`tools`(list); body=system prompt
- **Toolkit adapter:** enabled (symlink)
- **Source:** [support.atlassian.com/rovo/docs/use-subagents-in-rovo-dev-cli/](https://support.atlassian.com/rovo/docs/use-subagents-in-rovo-dev-cli/)
