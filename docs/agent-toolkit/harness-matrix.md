# Harness compatibility matrix

Single source of truth for which (asset-kind × harness) pairs are supported and
how each is projected. As of v3.0.0 Phase A this doc covers the **`agent`
(subagent) kind only**; the legacy multi-kind grid (the v1 `skill | command |
hook | plugin | mcp | pi-extension` table, removed in the strip-back) returns in
Phase B alongside the projection adapters. A parity test
(`tests/test_subagent_matrix.py`) fails if this doc and the harness catalog
(`src/agent_toolkit_cli/skill_agents.py`) disagree.

## Mechanisms

How an `agent` (subagent) asset is projected into a harness:

- **symlink** — per-asset symlink from a harness slot directory into the toolkit
  repo. The harness reads the markdown directly. Used when the harness accepts
  the toolkit's wrapper frontmatter unchanged (Claude-compatible markdown drop-in).
- **translate** — generate a per-harness flavored file in a CLI-managed cache,
  then symlink the harness slot to the cache file. Used when the harness expects
  different runtime frontmatter fields, a different filename suffix, or a
  non-markdown format (TOML/JSON) — e.g. Gemini's zod `.strict()` name+description
  only, OpenCode's injected `mode: subagent`, github-copilot's `.agent.md` suffix,
  mistral-vibe's TOML, kiro-cli's JSON.
- **config_file** — adapter mutates a single named config file to register the
  agent (rather than dropping a file into an auto-scanned directory).
- **config_file+folder** — adapter both mutates a config file AND owns a managed
  sub-folder of artefacts; both surfaces commit/rollback together. Used when the
  harness requires an explicit registry entry pointing at the agent definition —
  e.g. codex's `[agents.<role>]` in `config.toml` pointing to a TOML file,
  firebender's `firebender.json` agents array, aider-desk's per-slug `config.json`
  subdirs, dexto's `agent-spawner` registry.
- **dual-symlink** — per-asset symlinks at two slot directories (primary + alias
  mirror), both pointing at the same toolkit source. Used for `pi` (read by the
  third-party `@tintinweb/pi-subagents` extension).
- **unsupported (gap)** — the harness has a subagent or delegation concept in
  principle, but there is no user-definable file-drop convention to project into
  (runtime-only spawning, UI-only definition, mode-switch rather than spawn, or a
  defunct product). Tracked for possible future work.
- **unsupported (by design)** — the harness has no subagent concept at all
  (single-agent, library-only, or not a coding harness). Not a gap; won't be filled.
- **unknown — no public evidence found** — bounded time-boxed search surfaced no
  public docs or source for a subagent file convention (closed-source binary,
  private repo, unreleased, or unidentifiable product). Absence of evidence, not
  evidence of absence; revisit if the product publishes.

## Subagent (agent kind) support — all harnesses

This table is the v3.0.0 Phase A deliverable: the `agent` (subagent) verdict for
every harness in the catalog (`src/agent_toolkit_cli/skill_agents.py`, excluding
the synthetic `universal` entry). It is the contract Phase B implements against —
each `supported` row (mechanism = `symlink`/`translate`/`config_file`/`config_file+folder`/`dual-symlink`)
becomes one adapter behaviour. Guarded by `tests/test_subagent_matrix.py`.
Per-harness "what I checked" evidence trails and v1 baseline deltas live in
`docs/agent-toolkit/research/subagent-fragments/`.

**Summary (Phase A):** 28 supported · 11 unsupported (gap) · 10 unsupported (by design) · 5 unknown.

**Supported set (Phase B work surface, alphabetical):** `aider-desk`, `augment`,
`claude-code`, `codebuddy`, `codex`, `command-code`, `cortex`, `cursor`, `devin`,
`dexto`, `droid`, `firebender`, `forgecode`, `gemini-cli`, `github-copilot`,
`junie`, `kilo`, `kiro-cli`, `kode`, `mistral-vibe`, `mux`, `neovate`, `opencode`,
`pi`, `pochi`, `qoder`, `qwen-code`, `rovodev`.

By mechanism: **symlink** (Claude-compatible markdown drop-in) — `augment`,
`claude-code`, `codebuddy`, `command-code`, `cortex`, `cursor`, `droid`,
`forgecode`, `junie`, `kode`, `neovate`, `pochi`, `qoder`, `rovodev`;
**translate** (reshaped frontmatter / non-md format) — `devin`, `gemini-cli`,
`github-copilot`, `kilo`, `kiro-cli`, `mistral-vibe`, `mux`, `opencode`,
`qwen-code`; **config_file+folder** (registry-pointed) — `aider-desk`, `codex`,
`dexto`, `firebender`; **dual-symlink** — `pi`.

| Harness | Verdict | Mechanism | User path / Project path | Format (required/forbidden fields) | Citation |
|---|---|---|---|---|---|
| `adal` | unknown — no public evidence found |  |  | AdaL CLI codebase private; public repo docs-only; no public subagent file convention | codingagents.md/agents/adal/ |
| `aider-desk` | config_file+folder | config_file+folder | `~/.aider-desk/agents/<slug>/config.json` / `.aider-desk/agents/<slug>/config.json` | JSON; required `id`,`name`,`provider`,`model`,`subagent.enabled`,`subagent.systemPrompt`,`subagent.invocationMode`; `subagent.enabled:true` = spawnable | github.com/hotovo/aider-desk .../agent-profile-manager.ts + constants.ts |
| `amp` | unsupported (gap) |  |  | Task tool spawns at runtime; `.agents/commands/`+`AGENT.md` guide main agent only | https://ampcode.com/manual |
| `antigravity` | unknown — no public evidence found |  |  | dynamic orchestrator-spawned only; closed-source Go binary; community `agent.json` unconfirmed | GitHub discussion #27305 (gemini-cli) |
| `augment` | symlink | symlink | `~/.augment/agents/<slug>.md` / `.augment/agents/<slug>.md` | markdown+frontmatter; required `name`; optional `description`,`color`,`model`,`tools`/`disabled_tools` (denylist wins) | https://docs.augmentcode.com/cli/subagents |
| `bob` | unsupported (gap) |  |  | `.bob/rules*/` + modes only; no `agents/` dir; orchestration IBM-internal | https://bob.ibm.com/docs/ide/configuration/rules |
| `claude-code` | symlink | symlink | `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md` (recursive) | markdown+frontmatter; required `name`,`description`; extra keys ignored; 15 optional fields | https://code.claude.com/docs/en/sub-agents |
| `cline` | unsupported (gap) |  |  | `use_subagents` = read-only runtime research agents; no file-drop | https://docs.cline.bot/features/subagents |
| `codearts-agent` | unknown — no public evidence found |  |  | Huawei CodeArts beta; mentions MCP+Skills, no public subagent file dir | huaweicloud.com/intl/en-us/product/codearts/ai.html |
| `codebuddy` | symlink | symlink | `~/.codebuddy/agents/<slug>.md` / `.codebuddy/agents/<slug>.md` | markdown+frontmatter; required `name`(lc+hyphens),`description`; optional `tools`,`model`,`permissionMode`,`skills` | https://www.codebuddy.ai/docs/cli/sub-agents |
| `codemaker` | unsupported (by design) |  |  | batch code-gen CLI; no subagent concept | https://github.com/codemakerai/codemaker-cli |
| `codestudio` | unknown — no public evidence found |  |  | no product 'codestudio' found across vendors/GitHub/roundups; may be placeholder | exhaustive search, no source |
| `codex` | config_file+folder | config_file+folder | `~/.codex/agents/<slug>.toml` + `[agents.<role>]` in `~/.codex/config.toml` / `.codex/agents/<slug>.toml` | TOML; role decl req `description`; file req `developer_instructions`; registered via `config_file=` | developers.openai.com/codex/subagents + `codex-rs/config/src/config_toml.rs:649-691` |
| `command-code` | symlink | symlink | `~/.commandcode/agents/<slug>.md` / `.commandcode/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`,`tools`; reserved names blocked | https://commandcode.ai/docs/core-concepts/custom-agents |
| `continue` | unknown — no public evidence found |  |  | subagents in private testing (issue #9550), config.yaml-based; no stable public file spec | github.com/continuedev/continue/issues/9550 |
| `cortex` | symlink | symlink | `~/.snowflake/cortex/agents/` or `~/.claude/agents/` / `.cortex/agents/` or `.claude/agents/` | markdown+frontmatter; required `name`,`description`,`tools`(array or `*`); optional `model` | https://docs.snowflake.com/en/user-guide/cortex-code/extensibility |
| `crush` | unsupported (gap) |  |  | delegation runtime-only (`agent`/`agentic_fetch` tools); no user agent files (issue #1807 open) | github.com/charmbracelet/crush#1807 |
| `cursor` | symlink | symlink | `~/.cursor/agents/<slug>.md` / `.cursor/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`; optional `model`,`readonly`,`is_background` | https://cursor.com/docs/subagents |
| `deepagents` | unsupported (by design) |  |  | Python library; subagents are code `SubAgent` TypedDicts; no file-drop convention | github.com/langchain-ai/deepagents .../middleware/subagents.py |
| `devin` | translate | translate | `~/.config/devin/agents/{profile}/AGENT.md` / `.devin/agents/{profile}/AGENT.md` | markdown+frontmatter; req `name`,`description`; per-profile-dir `AGENT.md`; also reads `.claude/agents/*.md` | https://cli.devin.ai/docs/subagents |
| `dexto` | config_file+folder | config_file+folder | `agents/<name>.yml` (project; global unconfirmed) / `agents/<name>.yml` | YAML; req `systemPrompt`,`llm.*`; spawn via `tools[].type: agent-spawner` registry | docs.dexto.ai/docs/guides/configuring-dexto/agent-yml |
| `droid` | symlink | symlink | `~/.factory/droids/<slug>.md` / `.factory/droids/<slug>.md` | markdown+frontmatter; required `name`(lc/digits/-/_)+non-empty body; optional `description`(≤500),`model`,`tools` | https://docs.factory.ai/cli/configuration/custom-droids |
| `firebender` | config_file+folder | config_file+folder | `~/.firebender/firebender.json`→md / `firebender.json`→`.firebender/agents/<slug>.md` | markdown+frontmatter req `name`,`description`,`callable:true` to spawn; registered in `firebender.json` array | https://docs.firebender.com/multi-agent/subagents |
| `forgecode` | symlink | symlink | `~/.forge/agents/<slug>.md` (legacy `~/forge/agents/`) / `.forge/agents/<slug>.md` | markdown+frontmatter; `id` auto from filename, all else optional; project overrides global | github.com/antinomyhq/forgecode crates/forge_repo/src/agent.rs |
| `gemini-cli` | translate | translate | `~/.gemini/agents/<slug>.md` / `.gemini/agents/<slug>.md` | markdown+frontmatter; ONLY `name`+`description` (zod `.strict()` rejects extras) | `agentLoader.ts` localAgentSchema.strict() + `storage.ts:117-118,309-310` |
| `github-copilot` | translate | translate | `~/.copilot/agents/<name>.agent.md` / `.github/agents/<name>.agent.md` | markdown+frontmatter; `.agent.md` suffix; required `description`; optional `name`,`tools`,`mcp-servers`,`model`,`target` | https://docs.github.com/en/copilot/reference/custom-agents-configuration |
| `goose` | unsupported (by design) |  |  | subagents transient (no def file); subrecipes are session presets, not spawnable assistants | block/goose blog 2025-09-26-subagents-vs-subrecipes |
| `hermes-agent` | unsupported (by design) |  |  | `delegate_task` tool runtime-only; config only `~/.hermes/config.yaml`; no file-drop | hermes-agent.nousresearch.com/docs/user-guide/features/delegation |
| `iflow-cli` | unsupported (gap) |  |  | DEFUNCT (shut 2026-04-17); was `.iflow/agents/<slug>.md` req `agentType`/`systemPrompt`/`whenToUse` | platform.iflow.cn/en/cli/examples/subagent (archived) |
| `junie` | symlink | symlink | `~/.junie/agents/<slug>.md` (also `~/.agents/`) / `.junie/agents/<slug>.md` | markdown+frontmatter; required `description`; Claude-compatible optional fields | https://junie.jetbrains.com/docs/junie-cli-subagents.html |
| `kilo` | translate | translate | `~/.config/kilo/agent/<slug>.md` / `.kilo/agents/<slug>.md` | markdown+frontmatter; required `description`,`mode`(inject `subagent`); optional `model`,`permission` | https://kilo.ai/docs/agent-behavior/custom-modes |
| `kimi-cli` | unsupported (gap) |  |  | YAML via explicit `--agent-file` flag only; no auto-scanned dir | moonshotai.github.io/kimi-cli/en/customization/agents.html |
| `kiro-cli` | translate | translate | `~/.kiro/agents/<name>.json` / `.kiro/agents/<name>.json` | JSON (not markdown); filename=agent ID; optional `name`,`description`,`prompt`,`model`,`tools` | https://kiro.dev/docs/cli/custom-agents/configuration-reference/ |
| `kode` | symlink | symlink | `~/.claude/agents/<slug>.md` (also `~/.kode/agents/`) / `.claude/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`; `model_name` (not `model`) | https://github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md |
| `mcpjam` | unsupported (by design) |  |  | MCP inspector/testing tool, not a coding harness; no subagent concept | github.com/MCPJam/inspector |
| `mistral-vibe` | translate | translate | `~/.vibe/agents/<name>.toml` / `.vibe/agents/<name>.toml` | TOML; req `agent_type=subagent`,`display_name`,`description`,`safety`,`enabled_tools` | https://docs.mistral.ai/mistral-vibe/agents-skills |
| `mux` | translate | translate | `~/.mux/agents/<slug>.md` / `.mux/agents/<slug>.md` (non-recursive) | markdown+frontmatter; required `name`; nested `subagent` block (`runnable`) | https://mux.coder.com/agents |
| `neovate` | symlink | symlink | `~/.claude/agents/<slug>.md` (also `~/.neovate/agents/`) / `.claude/agents/<slug>.md` | markdown+frontmatter; required `name`(≤64),`description`(≤1024); Claude-identical | `neovateai/neovate-code:src/agent/agentManager.ts:162-235` |
| `openclaw` | unsupported (gap) |  |  | messaging-gateway personas (`~/.openclaw/agents/<id>/soul.md`), not coding subagents | https://docs.openclaw.ai/concepts/multi-agent |
| `opencode` | translate | translate | `~/.config/opencode/{agent,agents}/**/*.md` / `.opencode/{agent,agents}/**/*.md` | markdown+frontmatter; inject `mode: subagent`; name from filename; glob singular+plural | `packages/opencode/src/config/agent.ts` load(); `agent/agent.ts:32` |
| `openhands` | unsupported (gap) |  |  | microagents/skills = prompt injection on keyword, not spawn; `.openhands/skills/` | https://docs.openhands.dev/overview/skills |
| `pi` | dual-symlink | dual-symlink | `~/.pi/agent/agents/<slug>.md` / `.pi/agents/<slug>.md` (legacy `.agents/` fallback) | markdown+frontmatter (all optional); read by 3rd-party `@tintinweb/pi-subagents` ext | github.com/tintinweb/pi-subagents ; pi.dev/packages/pi-subagents |
| `pochi` | symlink | symlink | `~/.pochi/agents/<name>.md` / `.pochi/agents/<name>.md` | markdown+frontmatter; required `description`; optional `name`,`tools`; spawn via `newTask(<name>)` | https://docs.getpochi.com/custom-agent |
| `qoder` | symlink | symlink | `~/.qoder/agents/<name>.md` / `.qoder/agents/<name>.md` | markdown+frontmatter; required `name`,`description`; optional `tools`,`skills`,`mcpServers` | https://docs.qoder.com/extensions/subagent |
| `qwen-code` | translate | translate | `~/.qwen/agents/<slug>.md` / `.qwen/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`,`systemPrompt` | `subagent-manager.ts:930-931`, `validation.ts:34-36` |
| `replit` | unsupported (gap) |  |  | Agent 3/4 spawns subagents at runtime; no user file-drop convention | https://docs.replit.com/replitai/agent |
| `roo` | unsupported (gap) |  |  | custom modes (`.roomodes`) delegation targets via `new_task` but mode-switch, not independent-context spawn | roocodeinc.github.io/Roo-Code/features/custom-modes |
| `rovodev` | symlink | symlink | `~/.rovodev/subagents/<slug>.md` / `.rovodev/subagents/<slug>.md` | markdown+frontmatter; required `name`,`description`,`tools`(list); body=system prompt | https://support.atlassian.com/rovo/docs/use-subagents-in-rovo-dev-cli/ |
| `tabnine-cli` | unsupported (by design) |  |  | Enterprise Agent internal mini-agent routing; not user-definable | https://docs.tabnine.com/main/getting-started/tabnine-cli |
| `trae` | unsupported (by design) |  |  | custom agents UI-configured (Builder), stored server-side; no on-disk file | https://docs.trae.ai/ide/agent |
| `trae-cn` | unsupported (by design) |  |  | same product as Trae (diff models); identical UI-agent architecture, no file | technode.com/2025/03/04 ByteDance Trae CN |
| `warp` | unsupported (gap) |  |  | Oz spawns named harnesses as children; `AGENTS.md`=context; no user subagent file | https://docs.warp.dev/agent-platform/capabilities/skills/ |
| `windsurf` | unsupported (by design) |  |  | Cascade single-agent; parallel sessions are full agents not file-defined; AGENTS.md=context | https://docs.windsurf.com/windsurf/cascade/agents-md |
| `zencoder` | unsupported (by design) |  |  | Zen Agents marketplace/UI-defined; no local file-drop dir | https://zencoder.ai/blog/introducing-zen-agents... |

## Notes for Phase B

- **Mechanism normalization:** the research fragments labelled several
  Claude-compatible markdown drop-ins as `config_file+folder`; that was the
  agent's loose reading of "reads a directory". In this matrix's vocabulary a
  plain markdown file dropped into an auto-scanned directory is `symlink` (if
  frontmatter passes unchanged) or `translate` (if reshaping is required).
  `config_file`/`config_file+folder` is reserved for harnesses that need an
  explicit registry entry (codex `[agents.<role>]`, firebender/dexto registries,
  aider-desk per-slug JSON). The fragments retain the raw findings.
- **Baseline deltas vs v1.0.0** (full detail in the fragments):
  - `claude-code` — still `symlink`; discovery is now recursive and the optional
    frontmatter set is much larger.
  - `codex` — v1 modelled this as pure `translate` (#140). Current source requires
    an `[agents.<role>]` declaration in `config.toml` pointing at the TOML via
    `config_file=` → reclassified `config_file+folder`. #140's translate-only
    adapter is insufficient.
  - `pi` — the user-scope `~/.agents/` alias appears to be a *skills* path now,
    not an agent-discovery path; project `.agents/` survives only as a legacy
    fallback. Verify against the installed `@tintinweb/pi-subagents` before
    relying on the dual user-scope alias.
- **Cross-harness convergence:** `~/.claude/agents/` is read natively by
  `kode`, `neovate`, `cortex`, and `devin` (Claude-compatibility layers). A single
  symlink into `~/.claude/agents/` may satisfy multiple harnesses — a Phase B
  optimization to weigh against per-harness slot explicitness.
