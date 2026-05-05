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
  `~/.claude/plugins/agent-toolkit/`). Currently used for MCPs in Claude.
- **translate** *(Phase 3, not yet implemented)* — generate a per-harness
  flavored file in a CLI-managed cache, then symlink the harness slot to
  the cache. Used when the harness expects different runtime frontmatter
  fields than Claude's.
- **unsupported (gap)** — harness supports this kind in principle but the
  CLI hasn't wired the adapter yet. Tracked in matching GitHub issue.
- **unsupported (by design)** — the kind has no equivalent concept in this
  harness. Not a gap, won't be filled.

## Matrix

| Kind \\ Harness | Claude | Codex | OpenCode | Pi |
|---|---|---|---|---|
| **skill** | symlink → `~/.claude/skills/<slug>/` | symlink → `~/.codex/skills/<slug>/` | symlink → `~/.config/opencode/skills/<slug>/` | symlink → `~/.pi/agent/skills/<slug>/` |
| **agent** | symlink → `~/.claude/agents/<slug>.md` | unsupported (by design) — agents are plugin-internal in Codex | unsupported (gap) — slot exists at `~/.config/opencode/agents/<slug>.md`, Phase 2 wires it | symlink → `~/.pi/agent/agents/<slug>.md` |
| **command** | symlink → `~/.claude/commands/<slug>.md` | unsupported (by design) — commands surface as `$skill` invocations | unsupported (gap) — slot exists at `~/.config/opencode/commands/<slug>.md`, Phase 2 wires it | unsupported (by design) |
| **hook** | symlink → `~/.claude/hooks/<slug>.<ext>` | unsupported (by design) | unsupported (by design) — opencode hooks are TS plugin internals | unsupported (by design) |
| **plugin** | symlink → `~/.claude/plugins/<slug>/` | unsupported (by design) — Codex plugins are bundles installed via `codex plugin marketplace add` | unsupported (by design) — OpenCode plugins are TS files or npm packages | unsupported (by design) |
| **mcp** | unsupported (gap) — adapter not yet implemented | config_file → `~/.codex/config.toml` `[mcp_servers.<name>]` | unsupported (gap) — adapter not yet implemented | unsupported (gap) — adapter not yet implemented |
| **pi-extension** | unsupported (by design) | unsupported (by design) | unsupported (by design) | symlink → `~/.pi/agent/extensions/<slug>/` |

## Project-scope target paths

The matrix above shows user-scope paths. Project-scope paths (when an
allowlist lives at `<repo>/.agent-toolkit.yaml`) drop the `~/` prefix and
use the same relative paths under the project root, e.g. `.claude/skills/`,
`.config/opencode/skills/` → `.opencode/skills/` (note: project scope uses
`.opencode/`, not `.config/opencode/` which is user-scope only).

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

The Phase 3 **translate** mechanism will introduce harness-flavored
frontmatter generation for kinds where the runtime fields differ
materially (notably `agent` for OpenCode, where `mode: subagent` is
required).

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
