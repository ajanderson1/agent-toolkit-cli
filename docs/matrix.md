# Compatibility matrix

One row per harness, one column per asset [kind](glossary.md#kind). Every
harness links to its own page with per-kind detail; every tick links straight
to the relevant section. The main harnesses are pinned at the top — expand the
row beneath them for the rest, alphabetically. Derived from the machine-read
[SSOT](glossary.md#ssot) ([`harness-matrix.md`](agent-toolkit/harness-matrix.md))
by `scripts/gen_harness_docs.py` — edit the SSOT, then regenerate; never edit
this page by hand.

**Legend:** ✅ supported by the harness and the toolkit ·
— gap (the harness supports it; the toolkit hasn't implemented it yet) ·
N/A — the harness has no such concept ·
? unknown (no public evidence of how the harness handles this kind)

<div class="harness-matrix" markdown>
<table markdown>
<thead markdown>
<tr markdown><th markdown>Harness</th><th markdown>[Instructions](kinds/instructions.md)</th><th markdown>[Skills](kinds/skills.md)</th><th markdown>[Agents](kinds/agents.md)</th><th markdown>[MCP](kinds/mcp.md)</th><th markdown>[Pi extensions](kinds/pi-extensions.md)</th></tr>
</thead>
<tbody markdown>
<tr markdown><td markdown>[Claude Code](harnesses/claude-code.md)</td><td markdown>[✅](harnesses/claude-code.md#instructions)</td><td markdown>[✅](harnesses/claude-code.md#skills)</td><td markdown>[✅](harnesses/claude-code.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Pi](harnesses/pi.md)</td><td markdown>[✅](harnesses/pi.md#instructions)</td><td markdown>[✅](harnesses/pi.md#skills)</td><td markdown>[✅](harnesses/pi.md#agents)</td><td markdown>—</td><td markdown>[✅](harnesses/pi.md#pi-extensions)</td></tr>
<tr markdown><td markdown>[Codex](harnesses/codex.md)</td><td markdown>[✅](harnesses/codex.md#instructions)</td><td markdown>[✅](harnesses/codex.md#skills)</td><td markdown>[✅](harnesses/codex.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Gemini CLI](harnesses/gemini-cli.md)</td><td markdown>[✅](harnesses/gemini-cli.md#instructions)</td><td markdown>[✅](harnesses/gemini-cli.md#skills)</td><td markdown>[✅](harnesses/gemini-cli.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[OpenCode](harnesses/opencode.md)</td><td markdown>[✅](harnesses/opencode.md#instructions)</td><td markdown>[✅](harnesses/opencode.md#skills)</td><td markdown>[✅](harnesses/opencode.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
</tbody>
<tbody class="matrix-toggle">
<tr><td colspan="6"><button type="button" data-show="Show 49 more harnesses (A–Z) ▸" data-hide="Show fewer ▴">Show 49 more harnesses (A–Z) ▸</button></td></tr>
</tbody>
<tbody class="matrix-others" markdown hidden>
<tr markdown><td markdown>[AdaL](harnesses/adal.md)</td><td markdown>[✅](harnesses/adal.md#instructions)</td><td markdown>[✅](harnesses/adal.md#skills)</td><td markdown>[?](harnesses/adal.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[AiderDesk](harnesses/aider-desk.md)</td><td markdown>[—](harnesses/aider-desk.md#instructions)</td><td markdown>[✅](harnesses/aider-desk.md#skills)</td><td markdown>[✅](harnesses/aider-desk.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Amp](harnesses/amp.md)</td><td markdown>[✅](harnesses/amp.md#instructions)</td><td markdown>[✅](harnesses/amp.md#skills)</td><td markdown>[—](harnesses/amp.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Antigravity](harnesses/antigravity.md)</td><td markdown>[✅](harnesses/antigravity.md#instructions)</td><td markdown>[✅](harnesses/antigravity.md#skills)</td><td markdown>[?](harnesses/antigravity.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Augment](harnesses/augment.md)</td><td markdown>[✅](harnesses/augment.md#instructions)</td><td markdown>[✅](harnesses/augment.md#skills)</td><td markdown>[✅](harnesses/augment.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[IBM Bob](harnesses/bob.md)</td><td markdown>[✅](harnesses/bob.md#instructions)</td><td markdown>[✅](harnesses/bob.md#skills)</td><td markdown>[—](harnesses/bob.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Cline](harnesses/cline.md)</td><td markdown>[✅](harnesses/cline.md#instructions)</td><td markdown>[✅](harnesses/cline.md#skills)</td><td markdown>[—](harnesses/cline.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[CodeArts Agent](harnesses/codearts-agent.md)</td><td markdown>[?](harnesses/codearts-agent.md#instructions)</td><td markdown>[✅](harnesses/codearts-agent.md#skills)</td><td markdown>[?](harnesses/codearts-agent.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[CodeBuddy](harnesses/codebuddy.md)</td><td markdown>[✅](harnesses/codebuddy.md#instructions)</td><td markdown>[✅](harnesses/codebuddy.md#skills)</td><td markdown>[✅](harnesses/codebuddy.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Codemaker](harnesses/codemaker.md)</td><td markdown>N/A</td><td markdown>[✅](harnesses/codemaker.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Code Studio](harnesses/codestudio.md)</td><td markdown>[?](harnesses/codestudio.md#instructions)</td><td markdown>[✅](harnesses/codestudio.md#skills)</td><td markdown>[?](harnesses/codestudio.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Command Code](harnesses/command-code.md)</td><td markdown>[✅](harnesses/command-code.md#instructions)</td><td markdown>[✅](harnesses/command-code.md#skills)</td><td markdown>[✅](harnesses/command-code.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Continue](harnesses/continue.md)</td><td markdown>[—](harnesses/continue.md#instructions)</td><td markdown>[✅](harnesses/continue.md#skills)</td><td markdown>[?](harnesses/continue.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Cortex Code](harnesses/cortex.md)</td><td markdown>[✅](harnesses/cortex.md#instructions)</td><td markdown>[✅](harnesses/cortex.md#skills)</td><td markdown>[✅](harnesses/cortex.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Crush](harnesses/crush.md)</td><td markdown>[✅](harnesses/crush.md#instructions)</td><td markdown>[✅](harnesses/crush.md#skills)</td><td markdown>[—](harnesses/crush.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Cursor](harnesses/cursor.md)</td><td markdown>[✅](harnesses/cursor.md#instructions)</td><td markdown>[✅](harnesses/cursor.md#skills)</td><td markdown>[✅](harnesses/cursor.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Deep Agents](harnesses/deepagents.md)</td><td markdown>[—](harnesses/deepagents.md#instructions)</td><td markdown>[✅](harnesses/deepagents.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Devin for Terminal](harnesses/devin.md)</td><td markdown>[✅](harnesses/devin.md#instructions)</td><td markdown>[✅](harnesses/devin.md#skills)</td><td markdown>[✅](harnesses/devin.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Dexto](harnesses/dexto.md)</td><td markdown>[✅](harnesses/dexto.md#instructions)</td><td markdown>[✅](harnesses/dexto.md#skills)</td><td markdown>[✅](harnesses/dexto.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Droid](harnesses/droid.md)</td><td markdown>[✅](harnesses/droid.md#instructions)</td><td markdown>[✅](harnesses/droid.md#skills)</td><td markdown>[✅](harnesses/droid.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Firebender](harnesses/firebender.md)</td><td markdown>[✅](harnesses/firebender.md#instructions)</td><td markdown>[✅](harnesses/firebender.md#skills)</td><td markdown>[✅](harnesses/firebender.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[ForgeCode](harnesses/forgecode.md)</td><td markdown>[✅](harnesses/forgecode.md#instructions)</td><td markdown>[✅](harnesses/forgecode.md#skills)</td><td markdown>[✅](harnesses/forgecode.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[GitHub Copilot](harnesses/github-copilot.md)</td><td markdown>[✅](harnesses/github-copilot.md#instructions)</td><td markdown>[✅](harnesses/github-copilot.md#skills)</td><td markdown>[✅](harnesses/github-copilot.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Goose](harnesses/goose.md)</td><td markdown>[✅](harnesses/goose.md#instructions)</td><td markdown>[✅](harnesses/goose.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Hermes Agent](harnesses/hermes-agent.md)</td><td markdown>[✅](harnesses/hermes-agent.md#instructions)</td><td markdown>[✅](harnesses/hermes-agent.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[iFlow CLI](harnesses/iflow-cli.md)</td><td markdown>[✅](harnesses/iflow-cli.md#instructions)</td><td markdown>[✅](harnesses/iflow-cli.md#skills)</td><td markdown>[—](harnesses/iflow-cli.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Junie](harnesses/junie.md)</td><td markdown>[✅](harnesses/junie.md#instructions)</td><td markdown>[✅](harnesses/junie.md#skills)</td><td markdown>[✅](harnesses/junie.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Kilo Code](harnesses/kilo.md)</td><td markdown>[✅](harnesses/kilo.md#instructions)</td><td markdown>[✅](harnesses/kilo.md#skills)</td><td markdown>[✅](harnesses/kilo.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Kimi Code CLI](harnesses/kimi-cli.md)</td><td markdown>[✅](harnesses/kimi-cli.md#instructions)</td><td markdown>[✅](harnesses/kimi-cli.md#skills)</td><td markdown>[—](harnesses/kimi-cli.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Kiro CLI](harnesses/kiro-cli.md)</td><td markdown>[✅](harnesses/kiro-cli.md#instructions)</td><td markdown>[✅](harnesses/kiro-cli.md#skills)</td><td markdown>[✅](harnesses/kiro-cli.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Kode](harnesses/kode.md)</td><td markdown>[✅](harnesses/kode.md#instructions)</td><td markdown>[✅](harnesses/kode.md#skills)</td><td markdown>[✅](harnesses/kode.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[MCPJam](harnesses/mcpjam.md)</td><td markdown>N/A</td><td markdown>[✅](harnesses/mcpjam.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Mistral Vibe](harnesses/mistral-vibe.md)</td><td markdown>[✅](harnesses/mistral-vibe.md#instructions)</td><td markdown>[✅](harnesses/mistral-vibe.md#skills)</td><td markdown>[✅](harnesses/mistral-vibe.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Mux](harnesses/mux.md)</td><td markdown>[✅](harnesses/mux.md#instructions)</td><td markdown>[✅](harnesses/mux.md#skills)</td><td markdown>[✅](harnesses/mux.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Neovate](harnesses/neovate.md)</td><td markdown>[✅](harnesses/neovate.md#instructions)</td><td markdown>[✅](harnesses/neovate.md#skills)</td><td markdown>[✅](harnesses/neovate.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[OpenClaw](harnesses/openclaw.md)</td><td markdown>[✅](harnesses/openclaw.md#instructions)</td><td markdown>[✅](harnesses/openclaw.md#skills)</td><td markdown>[—](harnesses/openclaw.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[OpenHands](harnesses/openhands.md)</td><td markdown>[✅](harnesses/openhands.md#instructions)</td><td markdown>[✅](harnesses/openhands.md#skills)</td><td markdown>[—](harnesses/openhands.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Pochi](harnesses/pochi.md)</td><td markdown>[✅](harnesses/pochi.md#instructions)</td><td markdown>[✅](harnesses/pochi.md#skills)</td><td markdown>[✅](harnesses/pochi.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Qoder](harnesses/qoder.md)</td><td markdown>[✅](harnesses/qoder.md#instructions)</td><td markdown>[✅](harnesses/qoder.md#skills)</td><td markdown>[✅](harnesses/qoder.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Qwen Code](harnesses/qwen-code.md)</td><td markdown>[✅](harnesses/qwen-code.md#instructions)</td><td markdown>[✅](harnesses/qwen-code.md#skills)</td><td markdown>[✅](harnesses/qwen-code.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Replit](harnesses/replit.md)</td><td markdown>[✅](harnesses/replit.md#instructions)</td><td markdown>[✅](harnesses/replit.md#skills)</td><td markdown>[—](harnesses/replit.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Roo Code](harnesses/roo.md)</td><td markdown>[✅](harnesses/roo.md#instructions)</td><td markdown>[✅](harnesses/roo.md#skills)</td><td markdown>[—](harnesses/roo.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Rovo Dev](harnesses/rovodev.md)</td><td markdown>[✅](harnesses/rovodev.md#instructions)</td><td markdown>[✅](harnesses/rovodev.md#skills)</td><td markdown>[✅](harnesses/rovodev.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Tabnine CLI](harnesses/tabnine-cli.md)</td><td markdown>[✅](harnesses/tabnine-cli.md#instructions)</td><td markdown>[✅](harnesses/tabnine-cli.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Trae](harnesses/trae.md)</td><td markdown>[—](harnesses/trae.md#instructions)</td><td markdown>[✅](harnesses/trae.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Trae CN](harnesses/trae-cn.md)</td><td markdown>[✅](harnesses/trae-cn.md#instructions)</td><td markdown>[✅](harnesses/trae-cn.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Warp](harnesses/warp.md)</td><td markdown>[✅](harnesses/warp.md#instructions)</td><td markdown>[✅](harnesses/warp.md#skills)</td><td markdown>[—](harnesses/warp.md#agents)</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Windsurf](harnesses/windsurf.md)</td><td markdown>[✅](harnesses/windsurf.md#instructions)</td><td markdown>[✅](harnesses/windsurf.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
<tr markdown><td markdown>[Zencoder](harnesses/zencoder.md)</td><td markdown>[✅](harnesses/zencoder.md#instructions)</td><td markdown>[✅](harnesses/zencoder.md#skills)</td><td markdown>N/A</td><td markdown>—</td><td markdown>N/A</td></tr>
</tbody>
</table>
</div>

## The kinds

- **[Instructions](kinds/instructions.md)** — one canonical `AGENTS.md`,
  pointer symlinks for harnesses that read an own-name file.
- **[Skills](kinds/skills.md)** — `SKILL.md` folders projected into each
  harness's skills directory.
- **[Agents (subagents)](kinds/agents.md)** — subagent definitions projected
  per-harness (symlink, translate, or registry mechanisms).
- **[MCP servers](kinds/mcp.md)** — placeholder; not yet a managed kind.
- **[Pi extensions](kinds/pi-extensions.md)** — Pi-only extension packages.
