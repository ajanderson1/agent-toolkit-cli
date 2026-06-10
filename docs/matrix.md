# Compatibility matrix

One row per harness, one column per asset [kind](glossary.md#kind). Every
harness links to its own page with per-kind detail; every tick links straight
to the relevant section. Derived from the machine-read
[SSOT](glossary.md#ssot) (`docs/agent-toolkit/harness-matrix.md`) by
`scripts/gen_harness_docs.py` — edit the SSOT, then regenerate; never edit
this page by hand.

**Legend:** ✅ supported · ❌ not supported (a gap that could be filled) ·
— not applicable (no such concept in the harness, by design) ·
❓ unknown (no public evidence found)

## Main harnesses

| Harness | [Instructions](kinds/instructions.md) | [Skills](kinds/skills.md) | [Agents](kinds/agents.md) | [MCP](kinds/mcp.md) | [Pi extensions](kinds/pi-extensions.md) |
|---|:-:|:-:|:-:|:-:|:-:|
| [Claude Code](harnesses/claude-code.md) | [✅](harnesses/claude-code.md#instructions) | [✅](harnesses/claude-code.md#skills) | [✅](harnesses/claude-code.md#agents) | — | — |
| [Codex](harnesses/codex.md) | [✅](harnesses/codex.md#instructions) | [✅](harnesses/codex.md#skills) | [✅](harnesses/codex.md#agents) | — | — |
| [Gemini CLI](harnesses/gemini-cli.md) | [✅](harnesses/gemini-cli.md#instructions) | [✅](harnesses/gemini-cli.md#skills) | [✅](harnesses/gemini-cli.md#agents) | — | — |
| [OpenCode](harnesses/opencode.md) | [✅](harnesses/opencode.md#instructions) | [✅](harnesses/opencode.md#skills) | [✅](harnesses/opencode.md#agents) | — | — |
| [Pi](harnesses/pi.md) | [✅](harnesses/pi.md#instructions) | [✅](harnesses/pi.md#skills) | [✅](harnesses/pi.md#agents) | — | [✅](harnesses/pi.md#pi-extensions) |
| [Cursor](harnesses/cursor.md) | [✅](harnesses/cursor.md#instructions) | [✅](harnesses/cursor.md#skills) | [✅](harnesses/cursor.md#agents) | — | — |
| [GitHub Copilot](harnesses/github-copilot.md) | [✅](harnesses/github-copilot.md#instructions) | [✅](harnesses/github-copilot.md#skills) | [✅](harnesses/github-copilot.md#agents) | — | — |
| [Windsurf](harnesses/windsurf.md) | [✅](harnesses/windsurf.md#instructions) | [✅](harnesses/windsurf.md#skills) | — | — | — |
| [Cline](harnesses/cline.md) | [✅](harnesses/cline.md#instructions) | [✅](harnesses/cline.md#skills) | [❌](harnesses/cline.md#agents) | — | — |
| [Amp](harnesses/amp.md) | [✅](harnesses/amp.md#instructions) | [✅](harnesses/amp.md#skills) | [❌](harnesses/amp.md#agents) | — | — |
| [Goose](harnesses/goose.md) | [✅](harnesses/goose.md#instructions) | [✅](harnesses/goose.md#skills) | — | — | — |
| [Junie](harnesses/junie.md) | [✅](harnesses/junie.md#instructions) | [✅](harnesses/junie.md#skills) | [✅](harnesses/junie.md#agents) | — | — |

## Others

??? note "All other harnesses (42)"

    | Harness | [Instructions](kinds/instructions.md) | [Skills](kinds/skills.md) | [Agents](kinds/agents.md) | [MCP](kinds/mcp.md) | [Pi extensions](kinds/pi-extensions.md) |
    |---|:-:|:-:|:-:|:-:|:-:|
    | [AdaL](harnesses/adal.md) | [✅](harnesses/adal.md#instructions) | [✅](harnesses/adal.md#skills) | [❓](harnesses/adal.md#agents) | — | — |
    | [AiderDesk](harnesses/aider-desk.md) | [❌](harnesses/aider-desk.md#instructions) | [✅](harnesses/aider-desk.md#skills) | [✅](harnesses/aider-desk.md#agents) | — | — |
    | [Antigravity](harnesses/antigravity.md) | [✅](harnesses/antigravity.md#instructions) | [✅](harnesses/antigravity.md#skills) | [❓](harnesses/antigravity.md#agents) | — | — |
    | [Augment](harnesses/augment.md) | [✅](harnesses/augment.md#instructions) | [✅](harnesses/augment.md#skills) | [✅](harnesses/augment.md#agents) | — | — |
    | [IBM Bob](harnesses/bob.md) | [✅](harnesses/bob.md#instructions) | [✅](harnesses/bob.md#skills) | [❌](harnesses/bob.md#agents) | — | — |
    | [CodeArts Agent](harnesses/codearts-agent.md) | [❓](harnesses/codearts-agent.md#instructions) | [✅](harnesses/codearts-agent.md#skills) | [❓](harnesses/codearts-agent.md#agents) | — | — |
    | [CodeBuddy](harnesses/codebuddy.md) | [✅](harnesses/codebuddy.md#instructions) | [✅](harnesses/codebuddy.md#skills) | [✅](harnesses/codebuddy.md#agents) | — | — |
    | [Codemaker](harnesses/codemaker.md) | — | [✅](harnesses/codemaker.md#skills) | — | — | — |
    | [Code Studio](harnesses/codestudio.md) | [❓](harnesses/codestudio.md#instructions) | [✅](harnesses/codestudio.md#skills) | [❓](harnesses/codestudio.md#agents) | — | — |
    | [Command Code](harnesses/command-code.md) | [✅](harnesses/command-code.md#instructions) | [✅](harnesses/command-code.md#skills) | [✅](harnesses/command-code.md#agents) | — | — |
    | [Continue](harnesses/continue.md) | [❌](harnesses/continue.md#instructions) | [✅](harnesses/continue.md#skills) | [❓](harnesses/continue.md#agents) | — | — |
    | [Cortex Code](harnesses/cortex.md) | [✅](harnesses/cortex.md#instructions) | [✅](harnesses/cortex.md#skills) | [✅](harnesses/cortex.md#agents) | — | — |
    | [Crush](harnesses/crush.md) | [✅](harnesses/crush.md#instructions) | [✅](harnesses/crush.md#skills) | [❌](harnesses/crush.md#agents) | — | — |
    | [Deep Agents](harnesses/deepagents.md) | [❌](harnesses/deepagents.md#instructions) | [✅](harnesses/deepagents.md#skills) | — | — | — |
    | [Devin for Terminal](harnesses/devin.md) | [✅](harnesses/devin.md#instructions) | [✅](harnesses/devin.md#skills) | [✅](harnesses/devin.md#agents) | — | — |
    | [Dexto](harnesses/dexto.md) | [✅](harnesses/dexto.md#instructions) | [✅](harnesses/dexto.md#skills) | [✅](harnesses/dexto.md#agents) | — | — |
    | [Droid](harnesses/droid.md) | [✅](harnesses/droid.md#instructions) | [✅](harnesses/droid.md#skills) | [✅](harnesses/droid.md#agents) | — | — |
    | [Firebender](harnesses/firebender.md) | [✅](harnesses/firebender.md#instructions) | [✅](harnesses/firebender.md#skills) | [✅](harnesses/firebender.md#agents) | — | — |
    | [ForgeCode](harnesses/forgecode.md) | [✅](harnesses/forgecode.md#instructions) | [✅](harnesses/forgecode.md#skills) | [✅](harnesses/forgecode.md#agents) | — | — |
    | [Hermes Agent](harnesses/hermes-agent.md) | [✅](harnesses/hermes-agent.md#instructions) | [✅](harnesses/hermes-agent.md#skills) | — | — | — |
    | [iFlow CLI](harnesses/iflow-cli.md) | [✅](harnesses/iflow-cli.md#instructions) | [✅](harnesses/iflow-cli.md#skills) | [❌](harnesses/iflow-cli.md#agents) | — | — |
    | [Kilo Code](harnesses/kilo.md) | [✅](harnesses/kilo.md#instructions) | [✅](harnesses/kilo.md#skills) | [✅](harnesses/kilo.md#agents) | — | — |
    | [Kimi Code CLI](harnesses/kimi-cli.md) | [✅](harnesses/kimi-cli.md#instructions) | [✅](harnesses/kimi-cli.md#skills) | [❌](harnesses/kimi-cli.md#agents) | — | — |
    | [Kiro CLI](harnesses/kiro-cli.md) | [✅](harnesses/kiro-cli.md#instructions) | [✅](harnesses/kiro-cli.md#skills) | [✅](harnesses/kiro-cli.md#agents) | — | — |
    | [Kode](harnesses/kode.md) | [✅](harnesses/kode.md#instructions) | [✅](harnesses/kode.md#skills) | [✅](harnesses/kode.md#agents) | — | — |
    | [MCPJam](harnesses/mcpjam.md) | — | [✅](harnesses/mcpjam.md#skills) | — | — | — |
    | [Mistral Vibe](harnesses/mistral-vibe.md) | [✅](harnesses/mistral-vibe.md#instructions) | [✅](harnesses/mistral-vibe.md#skills) | [✅](harnesses/mistral-vibe.md#agents) | — | — |
    | [Mux](harnesses/mux.md) | [✅](harnesses/mux.md#instructions) | [✅](harnesses/mux.md#skills) | [✅](harnesses/mux.md#agents) | — | — |
    | [Neovate](harnesses/neovate.md) | [✅](harnesses/neovate.md#instructions) | [✅](harnesses/neovate.md#skills) | [✅](harnesses/neovate.md#agents) | — | — |
    | [OpenClaw](harnesses/openclaw.md) | [✅](harnesses/openclaw.md#instructions) | [✅](harnesses/openclaw.md#skills) | [❌](harnesses/openclaw.md#agents) | — | — |
    | [OpenHands](harnesses/openhands.md) | [✅](harnesses/openhands.md#instructions) | [✅](harnesses/openhands.md#skills) | [❌](harnesses/openhands.md#agents) | — | — |
    | [Pochi](harnesses/pochi.md) | [✅](harnesses/pochi.md#instructions) | [✅](harnesses/pochi.md#skills) | [✅](harnesses/pochi.md#agents) | — | — |
    | [Qoder](harnesses/qoder.md) | [✅](harnesses/qoder.md#instructions) | [✅](harnesses/qoder.md#skills) | [✅](harnesses/qoder.md#agents) | — | — |
    | [Qwen Code](harnesses/qwen-code.md) | [✅](harnesses/qwen-code.md#instructions) | [✅](harnesses/qwen-code.md#skills) | [✅](harnesses/qwen-code.md#agents) | — | — |
    | [Replit](harnesses/replit.md) | [✅](harnesses/replit.md#instructions) | [✅](harnesses/replit.md#skills) | [❌](harnesses/replit.md#agents) | — | — |
    | [Roo Code](harnesses/roo.md) | [✅](harnesses/roo.md#instructions) | [✅](harnesses/roo.md#skills) | [❌](harnesses/roo.md#agents) | — | — |
    | [Rovo Dev](harnesses/rovodev.md) | [✅](harnesses/rovodev.md#instructions) | [✅](harnesses/rovodev.md#skills) | [✅](harnesses/rovodev.md#agents) | — | — |
    | [Tabnine CLI](harnesses/tabnine-cli.md) | [✅](harnesses/tabnine-cli.md#instructions) | [✅](harnesses/tabnine-cli.md#skills) | — | — | — |
    | [Trae](harnesses/trae.md) | [❌](harnesses/trae.md#instructions) | [✅](harnesses/trae.md#skills) | — | — | — |
    | [Trae CN](harnesses/trae-cn.md) | [✅](harnesses/trae-cn.md#instructions) | [✅](harnesses/trae-cn.md#skills) | — | — | — |
    | [Warp](harnesses/warp.md) | [✅](harnesses/warp.md#instructions) | [✅](harnesses/warp.md#skills) | [❌](harnesses/warp.md#agents) | — | — |
    | [Zencoder](harnesses/zencoder.md) | [✅](harnesses/zencoder.md#instructions) | [✅](harnesses/zencoder.md#skills) | — | — | — |

## The kinds

- **[Instructions](kinds/instructions.md)** — one canonical `AGENTS.md`,
  pointer symlinks for harnesses that read an own-name file.
- **[Skills](kinds/skills.md)** — `SKILL.md` folders projected into each
  harness's skills directory.
- **[Agents (subagents)](kinds/agents.md)** — subagent definitions projected
  per-harness (symlink, translate, or registry mechanisms).
- **[MCP servers](kinds/mcp.md)** — placeholder; not yet a managed kind.
- **[Pi extensions](kinds/pi-extensions.md)** — Pi-only extension packages.
