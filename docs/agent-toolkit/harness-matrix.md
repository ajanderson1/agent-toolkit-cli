# Harness compatibility matrix

This is the single source of truth for which (asset-kind × harness) pairs are
supported and how each is projected. Both the Python code (`_support.py`,
`harness_adapters/*.py`) and asset metadata (`spec.harnesses`) defer to this
table. A parity test (`tests/test_harness_matrix.py`) fails if this doc and
the code disagree.

## Mechanisms

- **symlink** — per-asset symlink from a harness slot directory into the
  toolkit repo. The harness reads markdown directly. Used when the harness
  accepts the toolkit's wrapper frontmatter without translation.
- **config_file** — adapter mutates a single named config file (e.g.
  `~/.codex/config.toml`). Used for MCPs and any kind that registers via
  config rather than file drop-in.
- **plugin_folder** — adapter owns a whole subfolder (e.g.
  `~/.claude/plugins/agent-toolkit/`). Currently unused; reserved for future
  kinds that own a directory rather than a config file.
- **translate** — generate a per-harness flavored file in a CLI-managed
  cache (`~/.config/opencode/.agent-toolkit-cache/` for user scope), then
  symlink the harness slot to the cache file. Used when the harness expects
  different runtime frontmatter fields than Claude's.
- **unsupported (gap)** — harness supports this kind in principle but the
  CLI hasn't wired the adapter yet. Tracked in matching GitHub issue.
- **unsupported (by design)** — the kind has no equivalent concept in this
  harness. Not a gap, won't be filled.

### Translation cache layout

The `translate` mechanism writes flavored markdown into a per-scope cache,
then the harness slot symlinks to the cache file. Cache layout:

| Scope | Cache root |
|---|---|
| user | `~/.config/<harness>/.agent-toolkit-cache/<kind>/<slug>.md` |
| project | `<project>/.<harness>/.agent-toolkit-cache/<kind>/<slug>.md` |

The output preserves the toolkit's wrapper frontmatter under a nested
`agent_toolkit:` key (with `apiVersion`, `metadata`, `spec`) for SSOT
traceability — the harness ignores this key, but `agent-toolkit` and
human readers can trace any cache file back to its source asset.

`unlink` removes both the slot symlink and its cache file together.

## Matrix

| Kind \\ Harness | Claude | Codex | OpenCode | Pi |
|---|---|---|---|---|
| **skill** | symlink → `~/.claude/skills/<slug>/` | translate → `~/.codex/skills/<slug>/SKILL.md` (cache: `~/.codex/.agent-toolkit-cache/skill/<slug>/SKILL.md`) — emits codex-shaped frontmatter with top-level `description` and `agent_toolkit` wrapper block. NOTE: `~/.codex/skills/` is the **deprecated-but-loaded** path per `codex-rs/core-skills/src/loader.rs`; the canonical user path is `~/.agents/skills/<slug>/SKILL.md`. CLI migration pending | translate → `~/.config/opencode/skills/<slug>/SKILL.md` (cache: `~/.config/opencode/.agent-toolkit-cache/skill/<slug>/SKILL.md`) — slot is a real directory containing a file symlink to the cache; emits opencode-shaped frontmatter with top-level `name` and `description` plus `agent_toolkit` wrapper block | symlink → `~/.pi/agent/skills/<slug>/` (Pi also auto-discovers `~/.agents/skills/` and ancestor `.agents/skills/` — cross-harness convergence point) |
| **agent** | symlink → `~/.claude/agents/<slug>.md` | unsupported (gap) — Codex now supports `~/.codex/agents/<name>.toml` (TOML, not Markdown) since `developers.openai.com/codex/subagents`; CLI translate adapter pending | translate → `~/.config/opencode/agents/<slug>.md` (cache: `~/.config/opencode/.agent-toolkit-cache/agent/<slug>.md`) — injects `mode: subagent` and strips toolkit wrapper frontmatter | symlink → `~/.pi/agent/agents/<slug>.md` (also auto-loaded from `~/.agents/<slug>.md` by the `pi-subagents` extension; both paths are read) |
| **command** | symlink → `~/.claude/commands/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/commands/` drop-in; user "commands" surface as skills invoked via `$skill-name` mention or implicit description match | translate → `~/.config/opencode/commands/<slug>.md` (cache: `~/.config/opencode/.agent-toolkit-cache/command/<slug>.md`) — emits OpenCode-shaped frontmatter (optional `description`, `agent`, `model`, `subtask` — all optional) plus `agent_toolkit` wrapper block | unsupported (by design) — Pi has no command concept |
| **hook** | symlink → `~/.claude/hooks/<slug>.<ext>` (storage convention only — Claude does not auto-discover this directory; hooks must be referenced from `settings.json` via `$CLAUDE_PROJECT_DIR/.claude/hooks/...`) | unsupported (gap) — stable in Codex v0.125.0 (2026-04-24) via `[hooks]` in `~/.codex/config.toml` or `~/.codex/hooks.json`; CLI config_file adapter pending | unsupported (by design) — OpenCode hooks live inside TS plugin files (`tool.execute.before`, `session.created`, `session.error`, etc.); not drop-in markdown | unsupported (by design) — Pi has no hooks API at the user level |
| **plugin** | symlink → `~/.claude/plugins/<slug>/` | unsupported (by design) — Codex plugins are bundles with `.codex-plugin/plugin.json` manifests, installed via `codex plugin marketplace add` (different concept and install path from Claude markdown plugins) | unsupported (by design) — OpenCode plugins are TS/JS files at `~/.config/opencode/plugins/` or npm packages declared in `config.json` (different concept entirely) | unsupported (by design) — Pi extends via `pi-extension`, not a plugin concept |
| **mcp** | config_file → `~/.claude.json` `mcpServers.<name>` (NOT `~/.claude/settings.json`; user/local servers both stored in `~/.claude.json`; project scope is checked-in `.mcp.json`) | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` (TOML; stdio fields `command`/`args`/`env`). **Adapter stdio-only** (`codex.py:43-49` raises `CannotInstall` for non-stdio), even though Codex's schema accepts HTTP `url`/`http_headers`/`bearer_token_env_var` | config_file → `~/.config/opencode/opencode.json` `mcp.<name>` (uses `type` discriminator: `local` with `command` as ARRAY and `environment` (NOT `env`); or `remote` with `url`+`headers`) | unsupported (by design) — Pi has no MCP concept |
| **pi-extension** | unsupported (by design) | unsupported (by design) | unsupported (by design) | symlink → `~/.pi/agent/extensions/<slug>/` |

## Project-scope target paths

The matrix above shows user-scope paths. Project-scope paths (when an
allowlist lives at `<repo>/.agent-toolkit.yaml`) drop the `~/` prefix and
use the same relative paths under the project root with two harness-specific
deviations:

- **OpenCode** project scope uses `.opencode/`, not `.config/opencode/`
  (which is user-scope only).
- **Pi** project scope uses `.pi/<kind>/` — no `/agent/` infix, even though
  user-scope is `~/.pi/agent/<kind>/`. This matches pi's own runtime layout
  (`globalBaseDir = ~/.pi/agent`, `projectBaseDir = <cwd>/.pi`) — see
  `@mariozechner/pi-coding-agent` `dist/core/package-manager.js:669-686`.

See `_PROJECT_TARGETS` in `src/agent_toolkit/_support.py` for the canonical
table.

## Frontmatter compatibility

When a kind is projected via **symlink**, the harness reads the same
markdown file the toolkit owns. The asset's wrapper frontmatter
(`apiVersion: agent-toolkit/v1alpha2`, `metadata`, `spec`) is exposed as-is.
Claude Code, Codex (for skills), and OpenCode (for skills) ignore unknown
frontmatter fields.

Pi's frontmatter expectations differ by kind:

- **Skills** (loaded by Pi core, `dist/core/skills.js:212-249`): only
  `name`, `description`, and `disable-model-invocation` are read. Name must
  match the parent directory and follow `^[a-z0-9-]+$` (max 64 chars);
  description max 1024 chars (agentskills.io spec).
- **Agents** (loaded by the third-party `pi-subagents` extension, NOT Pi
  core): required `name` and `description`; optional `tools` (CSV;
  `mcp:<name>` prefix routes to MCP-direct tools), `model`,
  `fallbackModels`, `thinking`, `systemPromptMode` (`replace`|`append`),
  `inheritProjectContext`, `inheritSkills`, `skill`/`skills`, `extensions`,
  `output`, `defaultReads`, `defaultProgress`, `interactive`,
  `maxSubagentDepth`. Unknown keys captured in `extraFields`. Note: the
  parser is line-based and does NOT handle YAML lists — use comma-separated
  strings.

Both fall back gracefully on extra keys, so the toolkit's wrapper
frontmatter is preserved unharmed.

The **translate** mechanism generates harness-flavored frontmatter
for kinds where the runtime fields differ materially. For OpenCode agents,
`mode: subagent` is injected and the toolkit wrapper block is preserved under
`agent_toolkit:`. For OpenCode commands, frontmatter with optional
`description`, `agent`, `model`, `subtask` (all optional in OpenCode) is
emitted alongside the `agent_toolkit:` wrapper block. For Codex skills,
frontmatter with top-level `description` is emitted plus the wrapper.

## Why some pairs are "by design" unsupported

The matrix has two flavors of "unsupported": **gap** (the harness
supports the kind but the CLI hasn't wired it yet) and **by design**
(the kind has no equivalent concept in that harness, so projection is
not meaningful). Per kind:

- **plugin** is Claude-only by design. Each harness has a different
  notion of "plugin":
  - Claude: a markdown directory at `~/.claude/plugins/<slug>/` (what
    this toolkit projects).
  - Codex: a bundle with a `.codex-plugin/plugin.json` manifest plus
    optional skills/MCP/app-connector subfolders, installed via
    `codex plugin marketplace add <name>`. Different shape, different
    install verb — symlinking a markdown file would not register.
  - OpenCode: a TypeScript or JavaScript file at
    `~/.config/opencode/plugins/<slug>.{ts,js}` exporting hook
    functions (e.g. `session.created`, `tool.execute.before`); or an npm
    package declared in `opencode.json`'s `plugin` array. Neither is a
    markdown file.
  - Pi: extends via the dedicated `pi-extension` kind (TypeScript
    modules using Pi's runtime API), not a "plugin" concept.

  These are not gaps the toolkit can close — they're four genuinely
  different extension models that happen to share the word "plugin".

- **hook** has by-design and gap flavors mixed:
  - **By design** for Pi (no hooks API at all) and OpenCode (hook
    *behavior* exists but is expressed inside TypeScript plugin files,
    `tool.execute.before`, `session.error`, `session.created`, etc. —
    not as drop-in markdown).
  - **Gap** for Codex: hooks went stable in v0.125.0 (2026-04-24).
    Configured via `[hooks]` table in `~/.codex/config.toml` or via a
    standalone `~/.codex/hooks.json`. Events: `SessionStart`,
    `PreToolUse`, `PostToolUse`, `PermissionRequest`,
    `UserPromptSubmit`, `Stop`. Plugin bundles can also ship
    `hooks/hooks.json`. CLI config_file adapter pending.
  - For Claude: hooks ARE user-level but the slot directory
    `~/.claude/hooks/` is a *script-storage convention*, not an
    auto-discovery path — Claude reads hooks from JSON in
    `~/.claude/settings.json` (or settings.local.json, plugin
    `hooks/hooks.json`, scoped frontmatter in skill/agent files). The
    toolkit's symlink to `~/.claude/hooks/<slug>.<ext>` only fires if
    `settings.json` references `$CLAUDE_PROJECT_DIR/.claude/hooks/...`.

- **command** is Claude+OpenCode by design. Codex
  surfaces commands as `$skill-name` invocations from inside skills;
  there is no `~/.codex/commands/` drop-in path. Pi has no command
  concept at all. OpenCode supports drop-in commands but with
  different frontmatter (`description`, `agent`, `model`, `subtask` —
  all optional) — the toolkit translates at link time.

- **agent** has by-design and gap flavors:
  - **By design** for Codex's plugin-bundled agents (those ship via
    plugin marketplace, not drop-in).
  - **Gap** for Codex's user-level drop-in: `~/.codex/agents/<name>.toml`
    is supported per `developers.openai.com/codex/subagents`. Required
    fields: `name`, `description`, `developer_instructions`. Optional:
    `nickname_candidates[]`, `model`, `model_reasoning_effort`,
    `sandbox_mode`, `mcp_servers`, `skills.config`. Format is TOML, not
    Markdown — translation requires a kind→TOML transform, not just
    frontmatter injection. CLI translate adapter pending.
  - **Translated** for OpenCode: drop-in markdown agents are supported
    but missing `mode:` defaults to `all` (primary), which silently
    mis-classifies subagents — the translator injects `mode: subagent`.
  - **Symlinked** for Claude and Pi.
  - **Note for Pi:** the `pi-subagents` extension reads from BOTH
    `~/.pi/agent/agents/<slug>.md` (legacy) AND `~/.agents/<slug>.md`
    (new), concatenating results. Project-scope reads both
    `<root>/.agents/` and `<root>/.pi/agents/`.

- **pi-extension** is Pi-only by definition: TypeScript modules using
  the Pi runtime API. No other harness can load them.

- **mcp** is supported on three of four harnesses (claude, codex,
  opencode) via `config_file` adapters. Pi has no MCP concept — it
  loads tools from its own extension API instead, see the
  `pi-extension` row.

When in doubt, the rule is: declaring `harnesses:` includes a
genuinely-unsupported pair will trip `agent-toolkit link --all`'s
hard-stop on `UnsupportedPair`. So the asset metadata stays honest.

## Cross-asset dependencies (`spec.requires`)

An asset can declare peer dependencies under `spec.requires.<harness>`.
Example: a Pi agent that needs a paired Pi extension.

```yaml
spec:
  harnesses: [pi]
  requires:
    pi: ["pi-extension:pi-subagents"]
```

The peer strings follow the schema pattern
`^(skill|agent|command|hook|plugin|mcp|pi-extension):[a-z0-9][a-z0-9-]*$`.
The kind token MUST be the full schema kind name — `pi-extension`, not the
shorthand `extension`.

The linker (Phase 2) refuses to project an asset whose `requires` peers
are absent from the allowlist for that scope.  Exit code is 2.  The error
message names the missing peer and provides a fix command:

```
agent:ceo requires pi-extension:pi-subagents on pi — add it to the allowlist
under [pi_extensions] or run `agent-toolkit link user pi pi-extension:pi-subagents` first.
```

## How to add a new pair

1. Decide the mechanism (symlink, config_file, plugin_folder, translate).
2. For symlink: add to `_USER_TARGETS` and `_PROJECT_TARGETS` in
   `src/agent_toolkit/_support.py`.
3. For config_file or plugin_folder: implement an adapter under
   `src/agent_toolkit/harness_adapters/<harness>.py`.
4. Update this matrix.
5. The parity test (`tests/test_harness_matrix.py`) will fail until both
   sides agree.
