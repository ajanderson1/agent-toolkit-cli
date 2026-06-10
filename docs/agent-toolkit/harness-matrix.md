# Harness compatibility matrix

Single source of truth for which (asset-kind × harness) pairs are supported and
how each is projected. Machine-read by the CLI (shipped in the wheel) and
guarded by parity tests; the human-friendly [matrix](../matrix.md) and the
per-harness pages are generated views of this file
(`scripts/gen_harness_docs.py`). This doc currently covers two kinds, each in
its own section below:

- the **`agent` (subagent) kind** — v3.0.0 Phase A deliverable for #252
  (v3.1.0 milestone). Parity test: `tests/test_subagent_matrix.py`.
- the **`instructions` kind** — v3.0.0 Phase A deliverable for #269
  (v3.0.0 milestone). Parity test: `tests/test_instructions_matrix.py`.

The legacy multi-kind grid (the v1 `skill | command | hook | plugin | mcp |
pi-extension` table, removed in the strip-back) returns alongside the
projection adapters as each kind lands.

## Mechanisms — agent (subagent) kind

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
the synthetic `standard` entry). It is the contract Phase B implements against —
each `supported` row (mechanism = `symlink`/`translate`/`config_file`/`config_file+folder`/`dual-symlink`)
becomes one adapter behaviour. Guarded by `tests/test_subagent_matrix.py`.
Per-harness "what I checked" evidence trails and v1 baseline deltas live in
`docs/agent-toolkit/research/subagent-fragments/`. Tracked in #252.

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
| `adal` | unknown — no public evidence found |  |  | AdaL CLI codebase private; public repo docs-only; no public subagent file convention | [codingagents.md/agents/adal](https://codingagents.md/agents/adal/) |
| `aider-desk` | config_file+folder | config_file+folder | `~/.aider-desk/agents/<slug>/config.json` / `.aider-desk/agents/<slug>/config.json` | JSON; required `id`,`name`,`provider`,`model`,`subagent.enabled`,`subagent.systemPrompt`,`subagent.invocationMode`; `subagent.enabled:true` = spawnable | [hotovo/aider-desk src/main/agent/agent-profile-manager.ts](https://github.com/hotovo/aider-desk/blob/main/src/main/agent/agent-profile-manager.ts) + constants.ts |
| `amp` | unsupported (gap) |  |  | Task tool spawns at runtime; `.agents/commands/`+`AGENT.md` guide main agent only | https://ampcode.com/manual |
| `antigravity` | unknown — no public evidence found |  |  | dynamic orchestrator-spawned only; closed-source Go binary; community `agent.json` unconfirmed | [google-gemini/gemini-cli discussion #27305](https://github.com/google-gemini/gemini-cli/discussions/27305) |
| `augment` | symlink | symlink | `~/.augment/agents/<slug>.md` / `.augment/agents/<slug>.md` | markdown+frontmatter; required `name`; optional `description`,`color`,`model`,`tools`/`disabled_tools` (denylist wins) | https://docs.augmentcode.com/cli/subagents |
| `bob` | unsupported (gap) |  |  | `.bob/rules*/` + modes only; no `agents/` dir; orchestration IBM-internal | https://bob.ibm.com/docs/ide/configuration/rules |
| `claude-code` | symlink | symlink | `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md` (recursive) | markdown+frontmatter; required `name`,`description`; extra keys ignored; 15 optional fields | https://code.claude.com/docs/en/sub-agents |
| `cline` | unsupported (gap) |  |  | `use_subagents` = read-only runtime research agents; no file-drop | https://docs.cline.bot/features/subagents |
| `codearts-agent` | unknown — no public evidence found |  |  | Huawei CodeArts beta; mentions MCP+Skills, no public subagent file dir | [huaweicloud.com/intl/en-us/product/codearts/ai.html](https://www.huaweicloud.com/intl/en-us/product/codearts/ai.html) |
| `codebuddy` | symlink | symlink | `~/.codebuddy/agents/<slug>.md` / `.codebuddy/agents/<slug>.md` | markdown+frontmatter; required `name`(lc+hyphens),`description`; optional `tools`,`model`,`permissionMode`,`skills` | https://www.codebuddy.ai/docs/cli/sub-agents |
| `codemaker` | unsupported (by design) |  |  | batch code-gen CLI; no subagent concept | https://github.com/codemakerai/codemaker-cli |
| `codestudio` | unknown — no public evidence found |  |  | no product 'codestudio' found across vendors/GitHub/roundups; may be placeholder | exhaustive search, no source |
| `codex` | config_file+folder | config_file+folder | `~/.codex/agents/<slug>.toml` + `[agents.<role>]` in `~/.codex/config.toml` / `.codex/agents/<slug>.toml` | TOML; role decl req `description`; file req `developer_instructions`; registered via `config_file=` | [developers.openai.com/codex/subagents](https://developers.openai.com/codex/subagents) + [`codex-rs/config/src/config_toml.rs:649-691`](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs) |
| `command-code` | symlink | symlink | `~/.commandcode/agents/<slug>.md` / `.commandcode/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`,`tools`; reserved names blocked | https://commandcode.ai/docs/core-concepts/custom-agents |
| `continue` | unknown — no public evidence found |  |  | subagents in private testing (issue #9550), config.yaml-based; no stable public file spec | [continuedev/continue#9550](https://github.com/continuedev/continue/issues/9550) |
| `cortex` | symlink | symlink | `~/.snowflake/cortex/agents/` or `~/.claude/agents/` / `.cortex/agents/` or `.claude/agents/` | markdown+frontmatter; required `name`,`description`,`tools`(array or `*`); optional `model` | https://docs.snowflake.com/en/user-guide/cortex-code/extensibility |
| `crush` | unsupported (gap) |  |  | delegation runtime-only (`agent`/`agentic_fetch` tools); no user agent files (issue #1807 open) | [charmbracelet/crush#1807](https://github.com/charmbracelet/crush/issues/1807) |
| `cursor` | symlink | symlink | `~/.cursor/agents/<slug>.md` / `.cursor/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`; optional `model`,`readonly`,`is_background` | https://cursor.com/docs/subagents |
| `deepagents` | unsupported (by design) |  |  | Python library; subagents are code `SubAgent` TypedDicts; no file-drop convention | [langchain-ai/deepagents libs/deepagents/deepagents/middleware/subagents.py](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/subagents.py) |
| `devin` | translate | translate | `~/.config/devin/agents/{profile}/AGENT.md` / `.devin/agents/{profile}/AGENT.md` | markdown+frontmatter; req `name`,`description`; per-profile-dir `AGENT.md`; also reads `.claude/agents/*.md` | https://cli.devin.ai/docs/subagents |
| `dexto` | config_file+folder | config_file+folder | `agents/<name>.yml` (project; global unconfirmed) / `agents/<name>.yml` | YAML; req `systemPrompt`,`llm.*`; spawn via `tools[].type: agent-spawner` registry | [docs.dexto.ai/docs/guides/configuring-dexto/agent-yml](https://docs.dexto.ai/docs/guides/configuring-dexto/agent-yml) |
| `droid` | symlink | symlink | `~/.factory/droids/<slug>.md` / `.factory/droids/<slug>.md` | markdown+frontmatter; required `name`(lc/digits/-/_)+non-empty body; optional `description`(≤500),`model`,`tools` | https://docs.factory.ai/cli/configuration/custom-droids |
| `firebender` | config_file+folder | config_file+folder | `~/.firebender/firebender.json`→md / `firebender.json`→`.firebender/agents/<slug>.md` | markdown+frontmatter req `name`,`description`,`callable:true` to spawn; registered in `firebender.json` array | https://docs.firebender.com/multi-agent/subagents |
| `forgecode` | symlink | symlink | `~/.forge/agents/<slug>.md` (legacy `~/forge/agents/`) / `.forge/agents/<slug>.md` | markdown+frontmatter; `id` auto from filename, all else optional; project overrides global | [antinomyhq/forgecode crates/forge_repo/src/agent.rs](https://github.com/antinomyhq/forgecode/blob/main/crates/forge_repo/src/agent.rs) |
| `gemini-cli` | translate | translate | `~/.gemini/agents/<slug>.md` / `.gemini/agents/<slug>.md` | markdown+frontmatter; ONLY `name`+`description` (zod `.strict()` rejects extras) | [`packages/core/src/agents/agentLoader.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/agents/agentLoader.ts) localAgentSchema.strict() + `storage.ts:117-118,309-310` |
| `github-copilot` | translate | translate | `~/.copilot/agents/<name>.agent.md` / `.github/agents/<name>.agent.md` | markdown+frontmatter; `.agent.md` suffix; required `description`; optional `name`,`tools`,`mcp-servers`,`model`,`target` | https://docs.github.com/en/copilot/reference/custom-agents-configuration |
| `goose` | unsupported (by design) |  |  | subagents transient (no def file); subrecipes are session presets, not spawnable assistants | [goose blog 2025-09-26: subagents vs subrecipes](https://goose-docs.ai/blog/2025/09/26/subagents-vs-subrecipes/) |
| `hermes-agent` | unsupported (by design) |  |  | `delegate_task` tool runtime-only; config only `~/.hermes/config.yaml`; no file-drop | [hermes-agent.nousresearch.com/docs/user-guide/features/delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation) |
| `iflow-cli` | unsupported (gap) |  |  | DEFUNCT (shut 2026-04-17); was `.iflow/agents/<slug>.md` req `agentType`/`systemPrompt`/`whenToUse` | [platform.iflow.cn/en/cli/examples/subagent](https://platform.iflow.cn/en/cli/examples/subagent) (archived) |
| `junie` | symlink | symlink | `~/.junie/agents/<slug>.md` (also `~/.agents/`) / `.junie/agents/<slug>.md` | markdown+frontmatter; required `description`; Claude-compatible optional fields | https://junie.jetbrains.com/docs/junie-cli-subagents.html |
| `kilo` | translate | translate | `~/.config/kilo/agent/<slug>.md` / `.kilo/agents/<slug>.md` | markdown+frontmatter; required `description`,`mode`(inject `subagent`); optional `model`,`permission` | https://kilo.ai/docs/agent-behavior/custom-modes |
| `kimi-cli` | unsupported (gap) |  |  | YAML via explicit `--agent-file` flag only; no auto-scanned dir | [moonshotai.github.io/kimi-cli/en/customization/agents.html](https://moonshotai.github.io/kimi-cli/en/customization/agents.html) |
| `kiro-cli` | translate | translate | `~/.kiro/agents/<name>.json` / `.kiro/agents/<name>.json` | JSON (not markdown); filename=agent ID; optional `name`,`description`,`prompt`,`model`,`tools` | https://kiro.dev/docs/cli/custom-agents/configuration-reference/ |
| `kode` | symlink | symlink | `~/.claude/agents/<slug>.md` (also `~/.kode/agents/`) / `.claude/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`; `model_name` (not `model`) | https://github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md |
| `mcpjam` | unsupported (by design) |  |  | MCP inspector/testing tool, not a coding harness; no subagent concept | [github.com/MCPJam/inspector](https://github.com/MCPJam/inspector) |
| `mistral-vibe` | translate | translate | `~/.vibe/agents/<name>.toml` / `.vibe/agents/<name>.toml` | TOML; req `agent_type=subagent`,`display_name`,`description`,`safety`,`enabled_tools` | https://docs.mistral.ai/mistral-vibe/agents-skills |
| `mux` | translate | translate | `~/.mux/agents/<slug>.md` / `.mux/agents/<slug>.md` (non-recursive) | markdown+frontmatter; required `name`; nested `subagent` block (`runnable`) | https://mux.coder.com/agents |
| `neovate` | symlink | symlink | `~/.claude/agents/<slug>.md` (also `~/.neovate/agents/`) / `.claude/agents/<slug>.md` | markdown+frontmatter; required `name`(≤64),`description`(≤1024); Claude-identical | [`neovateai/neovate-code:src/agent/agentManager.ts:162-235`](https://github.com/neovateai/neovate-code/blob/master/src/agent/agentManager.ts) |
| `openclaw` | unsupported (gap) |  |  | messaging-gateway personas (`~/.openclaw/agents/<id>/soul.md`), not coding subagents | https://docs.openclaw.ai/concepts/multi-agent |
| `opencode` | translate | translate | `~/.config/opencode/{agent,agents}/**/*.md` / `.opencode/{agent,agents}/**/*.md` | markdown+frontmatter; inject `mode: subagent`; name from filename; glob singular+plural | [`packages/opencode/src/config/agent.ts`](https://github.com/sst/opencode/blob/dev/packages/opencode/src/config/agent.ts) load(); [`agent/agent.ts:32`](https://github.com/sst/opencode/blob/dev/packages/opencode/src/agent/agent.ts) |
| `openhands` | unsupported (gap) |  |  | microagents/skills = prompt injection on keyword, not spawn; `.openhands/skills/` | https://docs.openhands.dev/overview/skills |
| `pi` | dual-symlink | dual-symlink | `~/.pi/agent/agents/<slug>.md` / `.pi/agents/<slug>.md` (legacy `.agents/` fallback) | markdown+frontmatter (all optional); read by 3rd-party `@tintinweb/pi-subagents` ext | [github.com/tintinweb/pi-subagents](https://github.com/tintinweb/pi-subagents) ; [pi.dev/packages/pi-subagents](https://pi.dev/packages/pi-subagents) |
| `pochi` | symlink | symlink | `~/.pochi/agents/<name>.md` / `.pochi/agents/<name>.md` | markdown+frontmatter; required `description`; optional `name`,`tools`; spawn via `newTask(<name>)` | https://docs.getpochi.com/custom-agent |
| `qoder` | symlink | symlink | `~/.qoder/agents/<name>.md` / `.qoder/agents/<name>.md` | markdown+frontmatter; required `name`,`description`; optional `tools`,`skills`,`mcpServers` | https://docs.qoder.com/extensions/subagent |
| `qwen-code` | translate | translate | `~/.qwen/agents/<slug>.md` / `.qwen/agents/<slug>.md` | markdown+frontmatter; required `name`,`description`,`systemPrompt` | [`packages/core/src/subagents/subagent-manager.ts:930-931`](https://github.com/QwenLM/qwen-code/blob/main/packages/core/src/subagents/subagent-manager.ts), `validation.ts:34-36` |
| `replit` | unsupported (gap) |  |  | Agent 3/4 spawns subagents at runtime; no user file-drop convention | https://docs.replit.com/replitai/agent |
| `roo` | unsupported (gap) |  |  | custom modes (`.roomodes`) delegation targets via `new_task` but mode-switch, not independent-context spawn | [roocodeinc.github.io/Roo-Code/features/custom-modes](https://roocodeinc.github.io/Roo-Code/features/custom-modes) |
| `rovodev` | symlink | symlink | `~/.rovodev/subagents/<slug>.md` / `.rovodev/subagents/<slug>.md` | markdown+frontmatter; required `name`,`description`,`tools`(list); body=system prompt | https://support.atlassian.com/rovo/docs/use-subagents-in-rovo-dev-cli/ |
| `tabnine-cli` | unsupported (by design) |  |  | Enterprise Agent internal mini-agent routing; not user-definable | https://docs.tabnine.com/main/getting-started/tabnine-cli |
| `trae` | unsupported (by design) |  |  | custom agents UI-configured (Builder), stored server-side; no on-disk file | https://docs.trae.ai/ide/agent |
| `trae-cn` | unsupported (by design) |  |  | same product as Trae (diff models); identical UI-agent architecture, no file | [technode.com 2025-03-04: ByteDance Trae CN](https://technode.com/2025/03/04/) |
| `warp` | unsupported (gap) |  |  | Oz spawns named harnesses as children; `AGENTS.md`=context; no user subagent file | https://docs.warp.dev/agent-platform/capabilities/skills/ |
| `windsurf` | unsupported (by design) |  |  | Cascade single-agent; parallel sessions are full agents not file-defined; AGENTS.md=context | https://docs.windsurf.com/windsurf/cascade/agents-md |
| `zencoder` | unsupported (by design) |  |  | Zen Agents marketplace/UI-defined; no local file-drop dir | https://zencoder.ai/blog/introducing-zen-agents-mcp-library-and-marketplace |

## Notes for Phase B — agent (subagent) kind

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

## Instruction-file (`instructions` kind) support — all harnesses

This table is the **v3.0.0 Phase A deliverable** for the `instructions` kind:
for every harness in the catalog, what file does the harness load by **default**
(no flags, no config) as its root project/global instruction context, and can a
per-harness pointer symlink to a canonical `AGENTS.md` satisfy it? It is the
contract Phase B implements against — each `symlink`-verdict row becomes one
pointer (e.g. `CLAUDE.md → AGENTS.md`). Guarded by
`tests/test_instructions_matrix.py`. Per-harness "what I checked" evidence
trails live in `docs/agent-toolkit/research/instructions-fragments/`. Tracked in
#269.

### Mechanisms (instructions kind)

> **Terminology:** *standard* — formerly "general" (v3), earlier "universal" (pre-v3). The old token spellings still work for one cycle with a deprecation warning and are removed in v4.

This kind has only **one action verdict**. The five-cell vocabulary is:

- **native** — harness reads `AGENTS.md` by default at one or both scopes. No
  pointer needed; this set is the per-kind "standard" column.
- **symlink** — harness reads a fixed own-name file by default (e.g.
  `CLAUDE.md`, `GEMINI.md`, `IFLOW.md`). Adapter creates a same-name pointer
  symlink → `AGENTS.md`.
- **unsupported (gap)** — harness reads only via config opt-in or explicit flag,
  OR reads a directory (not a single root file), OR support is unshipped/
  defunct. A same-name pointer can't satisfy it and we don't mutate config.
- **unsupported (by design)** — no root instruction-file concept at all.
- **unknown — no public evidence found** — bounded search surfaced no default
  instruction-file convention.

There is no `translate`, no `config_file`, no `dual-symlink` for this kind.
Pointer symlinks only.

**Summary (Phase A):** 39 native · 7 symlink · 4 unsupported (gap) · 2 unsupported (by design) · 2 unknown.

**Symlink set (Phase B work surface, alphabetical):** `augment`, `claude-code`, `codebuddy`, `gemini-cli`, `iflow-cli`, `replit`, `tabnine-cli`.

These 7 are the per-harness pointer targets the `instructions` kind will create.
All 39 native readers cost zero adapter work — the canonical `AGENTS.md` 
satisfies them as-is.

| Harness | Verdict | Default file | Project / Global path | Reads AGENTS.md natively? | Mechanism | Citation |
|---|---|---|---|---|---|---|
| `adal` | native | `AGENTS.md` | `./AGENTS.md` (nearest while walking up from cwd) / none documented (project-only auto-load) | yes |  | https://codingagents.md/agents/adal/ ; https://docs.sylph.ai/ |
| `aider-desk` | unsupported (gap) | none (rule files toggled via UI / External Rules extension) | n/a — rule files live under user-chosen folders, enabled per-profile via UI | no |  | [hotovo/aider-desk README](https://github.com/hotovo/aider-desk#readme) — "Rule Files" / "External Rules extension"; no auto-loaded root file documented in README or main `AGENTS.md` |
| `amp` | native | `AGENTS.md` | `./AGENTS.md` / `~/.config/amp/AGENTS.md` (global rules via Amp settings, AGENTS.md primary) | yes |  | https://ampcode.com/agent.md (Amp publishes the AGENTS.md spec page) |
| `antigravity` | native | `AGENTS.md` + `GEMINI.md` | `./AGENTS.md` (workspace root) / `~/.gemini/AGENTS.md` | yes |  | [Antigravity 1.20.3 changelog (2026-03-05)](https://discuss.ai.google.dev/t/antigravity-update-1-20-3-2026-3-5/129320): "Added support for reading rules from AGENTS.md in addition to GEMINI.md." |
| `augment` | symlink | `CLAUDE.md` (with `AGENTS.md` as documented fallback) | `./CLAUDE.md` (workspace root) / `~/.augment/rules/` (directory loader; no fixed root file at user scope) | no (CLAUDE.md takes precedence over AGENTS.md per official rule chain) | symlink | https://docs.augmentcode.com/cli/rules |
| `bob` | native | `AGENTS.md` | `./AGENTS.md` / none (global-only) — global is `~/.bob/rules/*.md` (a *rules* directory, not AGENTS.md) | yes |  | https://bob.ibm.com/docs/ide/configuration/rules ("`AGENTS.md` file in your workspace root … Automatically loaded by default") and https://bob.ibm.com/docs/ide/getting-started/tutorials/start-a-project ("Bob automatically applies the `AGENTS.md` to new conversations") |
| `claude-code` | symlink | `CLAUDE.md` | `./CLAUDE.md` or `./.claude/CLAUDE.md` / `~/.claude/CLAUDE.md` | no | symlink | https://code.claude.com/docs/en/memory § "AGENTS.md" ("Claude Code reads `CLAUDE.md`, not `AGENTS.md`") |
| `cline` | native | `AGENTS.md` | `./AGENTS.md` / none (global-only-via-UI; no global file path) | yes |  | https://github.com/cline/cline/pull/7437 merged 2025-11-13; CHANGELOG entry "Add AGENTS.md support" in v3.37.0 (https://github.com/cline/cline/blob/main/CHANGELOG.md) |
| `codearts-agent` | unknown — no public evidence found | none | none / none | no |  | Searched `support.huaweicloud.com` CodeArts docs, JetBrains Marketplace listing, Pandaily/Tiger Brokers public-beta coverage, Baidu-wiki entries — no documented default root instruction-file convention |
| `codebuddy` | symlink | `CODEBUDDY.md` | `./CODEBUDDY.md` (recursive up from cwd) / `~/.codebuddy/CODEBUDDY.md` | no (own-name preferred; AGENTS.md only as fallback when CODEBUDDY.md absent) | symlink | https://www.codebuddy.ai/docs/cli/memory |
| `codemaker` | unsupported (by design) | none | none / none | no |  | https://github.com/codemakerai/codemaker-cli README ("Context-aware source code generation … Generating source code documentation … Fixing syntax"; usage is `codemaker generate docs **/*.java`) |
| `codestudio` | unknown — no public evidence found | none | none / none | no |  | (exhaustive search: ByteDance/Trae, Alibaba/Qoder, Baidu/Comate, Tencent/CodeBuddy, Volcano Engine — no product literally named "codestudio" found) |
| `codex` | native | `AGENTS.md` | `<git-root>/AGENTS.md` (walks git-root → cwd) / `~/.codex/AGENTS.md` (or `AGENTS.override.md`; honors `$CODEX_HOME`) | yes |  | https://developers.openai.com/codex/guides/agents-md |
| `command-code` | native | `AGENTS.md` | `./AGENTS.md` / none (project-only — no documented user-level instruction file) | yes |  | https://commandcode.ai/features § "AGENTS.md Project Memory" ("Define project-level instructions, code style guidelines, and architecture notes. Automatically loaded every session.") |
| `continue` | unsupported (gap) | none (uses `.continue/rules/` directory) | `./.continue/rules/` / `~/.continue/rules/` | no |  | https://docs.continue.dev/customize/deep-dives/rules ; https://github.com/continuedev/continue/issues/6716 |
| `cortex` | native | `AGENTS.md` | `./AGENTS.md` / none (project-only) | yes |  | https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight ("Create an `AGENTS.md` file … Cortex Code will automatically include in every conversation. Copy it to the root directory of your workspace"); `~/.snowflake/cortex/` CLI-config tree documents `skills/`, `agents/`, `commands/` but no global `AGENTS.md` |
| `crush` | native | `AGENTS.md` | `./AGENTS.md` / none (global-only) | yes |  | [charmbracelet/crush `internal/config/config.go`](https://github.com/charmbracelet/crush/blob/main/internal/config/config.go) — `defaultContextPaths` includes `AGENTS.md` / `agents.md` / `Agents.md`; `InitializeAs` JSON-schema `default=AGENTS.md` |
| `cursor` | native | `AGENTS.md` (also `.cursor/rules/*.mdc`) | `./AGENTS.md` / Cursor Settings > Rules (UI, not file) | yes |  | https://cursor.com/docs/rules |
| `deepagents` | unsupported (gap) | none (memory middleware requires explicit `agentId` + source paths) | none (no auto-load) / none (no auto-load) | no |  | https://deepagentsdk.dev/docs/guides/agent-memory ("Create memory middleware" requires `createAgentMemoryMiddleware({ agentId })`; project memory only loads via `requestProjectApproval`) |
| `devin` | native | `AGENTS.md` | `./AGENTS.md` / none (project-only) | yes |  | https://docs.devin.ai/onboard-devin/agents-md ("Just put an `AGENTS.md` file in your project root … Devin will look for the file before it starts coding") and https://docs.devin.ai/onboard-devin/knowledge-onboarding (Knowledge is the user/global-scope mechanism, separate from `AGENTS.md`) |
| `dexto` | native | `AGENTS.md` (priority over `CLAUDE.md`, then `GEMINI.md`) | `<workspaceRoot>/AGENTS.md` / none (global-only AGENTS.md not auto-loaded; only `~/.dexto/commands/` is global) | yes |  | https://github.com/truffle-ai/dexto/blob/main/packages/agent-management/src/config/discover-prompts.ts (`AGENT_INSTRUCTION_FILES = ['agents.md', 'claude.md', 'gemini.md']`, `discoverAgentInstructionFile`) |
| `droid` | native | `AGENTS.md` | `./AGENTS.md` / `~/.factory/AGENTS.md` | yes |  | https://docs.factory.ai/cli/configuration/agents-md ("Agents look for AGENTS.md in this order (first match wins): 1. `./AGENTS.md` in the current working directory … 4. Personal override: `~/.factory/AGENTS.md`. Agents read it automatically; no extra flags required.") |
| `firebender` | native | `AGENTS.md` | `./AGENTS.md` (also `./.firebender/AGENTS.md`) / `~/.firebender/AGENTS.md` | yes |  | https://docs.firebender.com/api-reference/agents-md.md ("automatically discovered… No configuration in `firebender.json` is required"); changelog v0.15.5 (2026-01-28) https://docs.firebender.com/about/changelog |
| `forgecode` | native | `AGENTS.md` | `./AGENTS.md` (recursively: env `base_path` → git root → cwd) / `none (project-only)` | yes |  | https://forgecode.dev/docs/custom-rules-guide/ |
| `gemini-cli` | symlink | `GEMINI.md` | `./GEMINI.md` / `~/.gemini/GEMINI.md` | no | symlink | [`packages/core/src/tools/memoryTool.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/memoryTool.ts) — `export const DEFAULT_CONTEXT_FILENAME = 'GEMINI.md';` + [`docs/cli/gemini-md.md`](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md) |
| `github-copilot` | native | `AGENTS.md` | `./AGENTS.md` (repo root) / `$HOME/.copilot/copilot-instructions.md` (different name at user scope) | yes (project scope) |  | https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions ; https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/ |
| `goose` | native | `.goosehints` (and `AGENTS.md`) | `./.goosehints` and `./AGENTS.md` / `~/.config/goose/.goosehints` and `~/.config/goose/AGENTS.md` (XDG; on macOS `~/Library/Application Support/Block/goose/`) | yes |  | [block/goose `crates/goose/src/hints/load_hints.rs`](https://github.com/block/goose/blob/main/crates/goose/src/hints/load_hints.rs) — `get_context_filenames()` defaults to `[".goosehints", "AGENTS.md"]`; `load_hints_from_directory` reads both project-cwd and `Paths::in_config_dir(...)` |
| `hermes-agent` | native | `AGENTS.md` | `./AGENTS.md` (cwd top-level only; nested injected lazily via tool results) / `none (project-only — global persona uses separate `~/.hermes/SOUL.md`)` | yes |  | https://hermes-agent.nousresearch.com/docs/guides/tips |
| `iflow-cli` | symlink | `IFLOW.md` | `./IFLOW.md` / `~/.iflow/IFLOW.md` | no | symlink | [`platform.iflow.cn` Memory docs](https://platform.iflow.cn/en/cli/configuration/iflow) — default name `IFLOW.md`, custom names require `contextFileName` setting; confirmed in DeepWiki Command Reference |
| `junie` | native | `AGENTS.md` | `./.junie/AGENTS.md` (preferred) or `./AGENTS.md` (fallback) / `~/.junie/AGENTS.md` | yes |  | https://junie.jetbrains.com/docs/guidelines-and-memory.html |
| `kilo` | native | `AGENTS.md` | `./AGENTS.md` / none (project-only) | yes |  | https://kilo.ai/docs/agent-behavior/agents-md |
| `kimi-cli` | native | `AGENTS.md` | `<git-root>/AGENTS.md` (walks git-root → cwd, plus `.kimi/AGENTS.md`) / none (global-only AGENTS.md not documented; user config lives at `~/.kimi/config.toml`) | yes |  | https://moonshotai.github.io/kimi-cli/en/release-notes/changelog.html (v1.29.0 2026-04-01) |
| `kiro-cli` | native | `AGENTS.md` | `./AGENTS.md` (workspace root) / `~/.kiro/steering/AGENTS.md` | yes |  | https://kiro.dev/docs/cli/steering/ |
| `kode` | native | `AGENTS.md` | `./AGENTS.md` (prefers `AGENTS.override.md`) / none (project-only; `~/.kode.json` is JSON config, not an instruction file) | yes |  | https://github.com/shareAI-lab/Kode-cli README § "AGENTS.md Standard Support" ("Native support for the OpenAI-initiated standard format … prefers `AGENTS.override.md` over `AGENTS.md`") |
| `mcpjam` | unsupported (by design) | none | none / none | no |  | https://www.mcpjam.com/ ; https://github.com/MCPJam/inspector |
| `mistral-vibe` | native | `AGENTS.md` | `./AGENTS.md` (walk up from cwd, trusted dirs only) / `~/.vibe/AGENTS.md` (or `$VIBE_HOME/AGENTS.md`) | yes |  | https://docs.mistral.ai/mistral-vibe/agents-skills |
| `mux` | native | `AGENTS.md` | `<workspace>/AGENTS.md` / `~/.mux/AGENTS.md` | yes |  | https://mux.coder.com/agents/instruction-files ("Mux picks the first matching base file: 1. AGENTS.md 2. AGENT.md 3. CLAUDE.md"; "Precedence: workspace … then global `~/.mux/AGENTS.md`") |
| `neovate` | native | `AGENTS.md` (project also walks for `CLAUDE.md`, `NEOVATE.md`; global also checks `NEOVATE.md` and `~/.claude/CLAUDE.md`) | `<cwd>/AGENTS.md` walking up to filesystem root / `~/.neovate/AGENTS.md` | yes |  | https://github.com/neovateai/neovate-code/blob/master/src/rules.ts (`getLlmsRules`, `projectRuleNames`/`globalRuleNames` starting with `'AGENTS.md'`) |
| `openclaw` | native | `AGENTS.md` | none (global/workspace-only) / `~/.openclaw/workspace/AGENTS.md` | yes |  | https://docs.openclaw.ai/concepts/system-prompt + https://github.com/openclaw/openclaw README ("Injected prompt files: `AGENTS.md`, `SOUL.md`, `TOOLS.md`"; "Workspace root: `~/.openclaw/workspace`") |
| `opencode` | native | `AGENTS.md` | `./AGENTS.md` / `~/.config/opencode/AGENTS.md` | yes |  | https://opencode.ai/docs/rules/ |
| `openhands` | native | `AGENTS.md` | `./AGENTS.md` (workspace root) / none documented (project-only auto-load) | yes |  | https://docs.openhands.dev/sdk/guides/skill |
| `pi` | native | `AGENTS.md` | `./AGENTS.md` / `~/.pi/agent/AGENTS.md` | yes |  | https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md (current upstream README documents AGENTS.md loaded at startup from cwd + parents + `~/.pi/agent/AGENTS.md`) |
| `pochi` | native | `README.pochi.md` OR `AGENTS.md` (treated identically) | `./AGENTS.md` (or `./README.pochi.md`) / `~/.pochi/README.pochi.md` (AGENTS.md alternative implied — docs say files are "treated identically") | yes |  | https://docs.getpochi.com/rules/ |
| `qoder` | native | `AGENTS.md` | `./AGENTS.md` (also `.qoder/rules/`) / none (project-only) | yes |  | https://docs.qoder.com/user-guide/rules |
| `qwen-code` | native | `QWEN.md` + `AGENTS.md` | `./AGENTS.md` (or `./QWEN.md`) / `~/.qwen/AGENTS.md` (or `~/.qwen/QWEN.md`) | yes |  | [PR #2018](https://github.com/QwenLM/qwen-code/pull/2018) merged 2026-03-02 in `packages/core/src/tools/memoryTool.ts` adds `AGENT_CONTEXT_FILENAME = 'AGENTS.md'` and sets `currentGeminiMdFilename = [DEFAULT_CONTEXT_FILENAME, AGENT_CONTEXT_FILENAME]` (closes [#2006](https://github.com/QwenLM/qwen-code/issues/2006)) |
| `replit` | symlink | `replit.md` | `./replit.md` (project root only) / none (project-only) | no | symlink | https://docs.replit.com/replitai/replit-dot-md |
| `roo` | native | `AGENTS.md` | `./AGENTS.md` / `~/.roo/rules/` (directory, not single file) | yes |  | https://roocodeinc.github.io/Roo-Code/features/custom-instructions |
| `rovodev` | native | `AGENTS.md` | `./AGENTS.md` / `~/.rovodev/AGENTS.md` | yes |  | https://paul-hackenberger.medium.com/atlassian-rovodev-the-king-of-kontext-6bd7a77b5b37 ("Place an `AGENTS.md` file in your repository root … Rovo Dev reads this automatically" and "Create an `AGENTS.md` file in your `~/.rovodev` folder … Rovo Dev reads these files automatically, giving every interaction team-specific context") |
| `tabnine-cli` | symlink | `TABNINE.md` | `./TABNINE.md` / unclear (no documented global `TABNINE.md` path; `~/.tabnine/guidelines/*.md` is a *directory* of guidelines, not the same file) | no | symlink | https://docs.tabnine.com/main/getting-started/tabnine-cli/getting-started/quickstart ("Add project context with a `TABNINE.md` file in your project root") and https://docs.tabnine.com/main/getting-started/tabnine-cli/features/agent-skills ("Unlike `TABNINE.md` project instructions (which load automatically on every session), skills load only when relevant") |
| `trae` | unsupported (gap) | `project_rules.md` (in `.trae/rules/` directory) | `./.trae/rules/project_rules.md` / `./.trae/rules/user_rules.md` (workspace-level "user rules", not OS-global) | no |  | https://docs.trae.ai/ide/rules?_lang=en ; https://github.com/Trae-AI/Trae/issues/1911 |
| `trae-cn` | native | `AGENTS.md` (alongside `.trae/rules/project_rules.md`) | `./AGENTS.md` (and nested sub-directory `AGENTS.md`) / `./.trae/rules/user_rules.md` | yes |  | https://forum.trae.cn/t/topic/52 ; Trae CN changelog 2026-04-15 ("Rules 支持嵌套：子仓目录下的 Rule 文件（包括 AGENTS.md）") |
| `warp` | native | `AGENTS.md` | `./AGENTS.md` (all caps required) / none (global-only-via-UI; Warp Drive Personal > Rules) | yes |  | https://docs.warp.dev/agent-platform/capabilities/rules/ ("Project Rules… stored in an `AGENTS.md` file… filename must be in all caps") |
| `windsurf` | native | `AGENTS.md` | `./AGENTS.md` (project root) / Cascade memories UI + `global_rules.md` via "Manage memories" | yes |  | https://docs.windsurf.com/windsurf/cascade/agents-md |
| `zencoder` | native | `AGENTS.md` | `./AGENTS.md` / none documented (the `.zencoder/rules/*.md` tree is a *directory* of rules, not a global `AGENTS.md`) | yes |  | Feb 2026 Zencoder changelog reports "AGENTS.md support — agent instructions are now resolved from AGENTS.md files at the CLI level" (https://docs.zencoder.ai/changelog/february-2026, surfaced via search; page returns 403 to anonymous fetch) |

## Notes for Phase B — instructions kind

- **Massively native-skewed result.** 39/54 harnesses (72%) read `AGENTS.md`
  natively at one or both scopes. The `AGENTS.md` standard has become the
  cross-harness default since the spec was drafted (2026-05-27) — the priors
  table understated this. The Phase B implementation surface is just the 7
  `symlink`-verdict harnesses, not the larger set the spec anticipated.
- **Project-only natives.** Several `native` harnesses (e.g. `command-code`,
  `kode`) read `AGENTS.md` at project scope but have no documented global/user
  instruction-file path. The lockfile must allow `scope="project"` entries
  with no global pointer, even when the harness is `native`.
- **Workspace-bound natives.** `openclaw` reads `AGENTS.md` only from its single
  global workspace (`~/.openclaw/workspace/AGENTS.md`), not from per-project
  cwd. Treated as `native` because the bucket discriminator is "reads AGENTS.md
  by default with no flags" — the global-only scoping is documented in the
  fragment.
- **Both-by-default natives.** Some `native` harnesses (e.g. `qwen-code`,
  `antigravity`) load both `AGENTS.md` AND a legacy own-name file by default.
  No pointer needed; the legacy file remains harmless.
- **`continue` reclassified `gap`.** The spec's priors list assumed `continue`
  was unsupported; current upstream loads `.continue/rules/*.md` directories
  but no single root file → file-vs-directory rule → `gap`.
- **Per-kind "standard" set is large.** Per the sibling spec's per-kind standard
  model, the 39 `native` readers ARE the "standard" column for this kind —
  rendered in the TUI as informational (always satisfied, no toggle).
