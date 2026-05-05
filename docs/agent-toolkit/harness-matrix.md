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
| **skill** | symlink → `~/.claude/skills/<slug>/` | translate → `~/.codex/skills/<slug>/SKILL.md` (cache: `~/.codex/.agent-toolkit-cache/skill/<slug>/SKILL.md`) — emits codex-shaped frontmatter with top-level `description` and `agent_toolkit` wrapper block | translate → `~/.config/opencode/skills/<slug>/SKILL.md` (cache: `~/.config/opencode/.agent-toolkit-cache/skill/<slug>/SKILL.md`) — slot is a real directory containing a file symlink to the cache; emits opencode-shaped frontmatter with top-level `name` and `description` plus `agent_toolkit` wrapper block | symlink → `~/.pi/agent/skills/<slug>/` |
| **agent** | symlink → `~/.claude/agents/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/agents/` drop-in; agents are plugin-internal, distributed via `codex plugin marketplace add` | translate → `~/.config/opencode/agents/<slug>.md` (cache: `~/.config/opencode/.agent-toolkit-cache/agent/<slug>.md`) — injects `mode: subagent` and strips toolkit wrapper frontmatter | symlink → `~/.pi/agent/agents/<slug>.md` |
| **command** | symlink → `~/.claude/commands/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/commands/`; commands surface as `$skill` invocations from inside skills | translate → `~/.config/opencode/commands/<slug>.md` (cache: `~/.config/opencode/.agent-toolkit-cache/command/<slug>.md`) — emits OpenCode-shaped frontmatter with `description` and `agent_toolkit` wrapper block | unsupported (by design) — Pi has no command concept |
| **hook** | symlink → `~/.claude/hooks/<slug>.<ext>` | unsupported (by design) — Codex has no hooks API at the user level | unsupported (by design) — OpenCode hooks live inside TS plugin files (`session.start`, `tool.execute.before`, etc.); not drop-in markdown | unsupported (by design) — Pi has no hooks API at the user level |
| **plugin** | symlink → `~/.claude/plugins/<slug>/` | unsupported (by design) — Codex plugins are bundles with `.codex-plugin/plugin.json` manifests, installed via `codex plugin marketplace add` (different concept and install path from Claude markdown plugins) | unsupported (by design) — OpenCode plugins are TS/JS files at `~/.config/opencode/plugins/` or npm packages declared in `config.json` (different concept entirely) | unsupported (by design) — Pi extends via `pi-extension`, not a plugin concept |
| **mcp** | config_file → `~/.claude.json` `mcpServers.<name>` | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` | config_file → `~/.config/opencode/opencode.json` `mcp.<name>` | unsupported (by design) — Pi has no MCP concept |
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
frontmatter fields. Pi reads its own frontmatter shape (`name`,
`description`, `tools`, `model`, `extensions`) and falls back gracefully on
extra keys.

The **translate** mechanism (Phase 3) generates harness-flavored frontmatter
for kinds where the runtime fields differ materially. For OpenCode agents,
`mode: subagent` is injected and the toolkit wrapper block is preserved under
`agent_toolkit:`. For OpenCode commands, a `description`-only frontmatter is
emitted alongside the `agent_toolkit:` wrapper block.

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
    functions (e.g. `session.start`, `tool.execute.before`); or an npm
    package declared in `config.json`'s `plugin` array. Neither is a
    markdown file.
  - Pi: extends via the dedicated `pi-extension` kind (TypeScript
    modules using Pi's runtime API), not a "plugin" concept.

  These are not gaps the toolkit can close — they're four genuinely
  different extension models that happen to share the word "plugin".

- **hook** is Claude-only by design. Codex and Pi have no user-level
  hooks API. OpenCode does have hook *behavior* but it's expressed
  inside TypeScript plugin files (`tool.execute.before`,
  `session.error`, etc.) — not as drop-in markdown.

- **command** is Claude+(opencode-via-Phase-3) by design. Codex
  surfaces commands as `$skill-name` invocations from inside skills;
  there is no `~/.codex/commands/` drop-in path. Pi has no command
  concept at all. OpenCode does support drop-in commands but with a
  different frontmatter shape than Claude — Phase 3 will bridge.

- **agent** is Claude+Pi+(opencode-via-Phase-3) by design. Codex
  exposes agents only through plugin bundles; there's no
  `~/.codex/agents/` drop-in. OpenCode supports drop-in markdown
  agents but defaults missing `mode:` to `all` (primary), which
  silently mis-classifies our subagents — Phase 3 injects the right
  mode at link time.

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
