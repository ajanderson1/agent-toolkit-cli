# claude/plugin asset kind — design

Status: draft (auto-mode)
Date: 2026-05-20
Issue: #149
Milestone: v1.0.0

## Context

The `plugin` kind already exists in the codebase as a recognized asset
kind, but its harness mapping is wrong:

- `harness-matrix.md` declares `(claude, plugin) = symlink → ~/.claude/plugins/<slug>/`.
- `_support.py` mirrors that target.
- `walker.py` discovers plugins as `plugins/<slug>/.claude-plugin/{plugin,marketplace}.json` with metadata in an inline `agent_toolkit_cli` JSON key.
- There is no per-plugin adapter; the linker falls through to the
  generic `symlink` mechanism.

But Claude Code's plugin runtime **does not auto-discover**
`~/.claude/plugins/<slug>/`. It reads two JSON files:

- `~/.claude/plugins/installed_plugins.json` (schema `version: 2`) — keyed by `<plugin>@<marketplace>`, lists installed entries per scope.
- `~/.claude/plugins/known_marketplaces.json` — keyed by marketplace short name, declares the `source` block and cached `installLocation`.

The actual plugin tree is cloned by Claude into
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` on next start.

The toolkit's current symlink projection produces files that Claude
never reads. The fix is to convert `(claude, plugin)` to a `config_file`
adapter that mutates the two JSON files (mirroring the Codex MCP
adapter's discipline) and lets Claude's runtime do the clone-on-start.

## Goal

Make `(claude, plugin)` a working `config_file` cell. All other harnesses
remain `unsupported (by design)` — same shape as `pi-extension`. The
existing CLI verbs (`link`/`unlink`/`list`/`diff`/`check`/`fix`/`doctor`)
and TUI all light up for plugins automatically once the adapter is wired.

## Non-goals

- **Project-scope plugins.** Every `installed_plugins.json` entry
  observed has `scope: "user"`. `link project claude plugin:<slug>` will
  return `unsupported scope` cleanly. Revisit if Claude adds project
  scope upstream.
- **Other harnesses.** Codex, OpenCode, Gemini, Pi all stay
  `unsupported (by design)` for plugins (each has its own different
  extension model — see harness-matrix.md prose).
- **Cloning plugin contents.** The CLI does **not** clone. It writes
  declarative entries; Claude clones lazily on next start.
- **Migrating the four existing physical submodules** under
  `plugins/` (`atomic-agents`, `companion-html`, `figma`,
  `anthropic-agent-skills`). They predate this kind. They stay as-is
  for v1; revisit separately.
- **The `plugins/registry.json` flat suggestion list.** Retiring or
  repurposing it is a follow-up.

## Design

### Asset shape (sidecar-only)

A toolkit plugin asset is **sidecar-only** — no vendored content. The
sidecar lives at `plugins/<slug>.toolkit.yaml` in the toolkit repo
(mirroring `mcps/<slug>.toolkit.yaml`):

```yaml
apiVersion: agent-toolkit/v1alpha2
kind: plugin
metadata:
  name: superpowers
  description: TDD, debugging, collaboration patterns
spec:
  harnesses: [claude]
  source:
    marketplace: claude-plugins-official
    marketplaceSource:
      source: git         # git | github | directory  (matches Claude's on-disk key)
      url: https://github.com/anthropics/claude-plugins-official.git
      # repo: anthropics/claude-plugins-official    # for source: github
      # path: /absolute/path                         # for source: directory
    plugin: superpowers
    version: "latest"   # or a pinned semver string
```

**Coexistence with existing inline-JSON discovery.** The walker today
recognizes `plugins/<slug>/.claude-plugin/{plugin,marketplace}.json`
with an `agent_toolkit_cli` JSON block. That path is **deprecated by
this spec** — the canonical metadata location for `plugin` becomes the
sidecar `plugins/<slug>.toolkit.yaml`. The walker keeps the legacy
JSON-block reader as a fall-back during a one-release deprecation
window so the four existing physical submodules don't fall off the
inventory immediately; `check` emits a one-time warning when the legacy
path is the source. The deprecation removal is a follow-up issue.

Per AGENTS.md's "Asset identity / one asset, one metadata location"
rule, the **mutex** stays: a sidecar `.toolkit.yaml` AND an inline
`agent_toolkit_cli` JSON block for the same slug is a `check` exit 2.

### Schema additions

`schemas/asset-frontmatter.v1alpha2.json` and its mirror at
`src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` gain a
new branch for `kind: plugin` sidecars. Required:

- `apiVersion: agent-toolkit/v1alpha2`
- `kind: plugin`
- `metadata.name` (matches on-disk slug; existing rule applies)
- `metadata.description`
- `spec.harnesses` containing `claude` (and only `claude`)
- `spec.source.marketplace` (string, marketplace short name)
- `spec.source.marketplaceSource` (object with `source` key ∈ {git, github, directory} — matches Claude's on-disk shape verbatim, including the repeated `source` nesting)
  - `source: git` requires `url`
  - `source: github` requires `repo` (e.g. `org/name`)
  - `source: directory` requires `path` (absolute)
- `spec.source.plugin` (string, plugin name as known to the marketplace)
- `spec.source.version` (string; `"latest"` or pinned semver — no semver enforcement in schema)

The `schema-vendor-check` lefthook enforces parity between the two
vendored copies.

### Harness matrix changes

Update `docs/agent-toolkit/harness-matrix.md`:

- Replace the `(claude, plugin)` cell text:
  - **From:** `symlink → ~/.claude/plugins/<slug>/`
  - **To:** `config_file → ~/.claude/plugins/installed_plugins.json + ~/.claude/plugins/known_marketplaces.json`
- The other four columns (`Codex`, `OpenCode`, `Gemini`, `Pi`) stay
  `unsupported (by design)` — text unchanged.
- Update the "Why some pairs are 'by design' unsupported" → **plugin**
  prose: replace the "Claude: a markdown directory at
  `~/.claude/plugins/<slug>/` (what this toolkit projects)" line with
  the accurate description of the two JSON files and the lazy-clone
  behavior.

`tests/test_harness_matrix.py` will fail until the matrix doc and the
code (`_support.py` removal + adapter registration) agree.

### Adapter

New file: `src/agent_toolkit_cli/harness_adapters/claude_plugin.py`.

Implements the `config_file` adapter interface (model:
`harness_adapters/codex.py`):

- `name = "claude"`, `strategy = "config_file"`. (The dispatcher uses
  `(harness, kind)` to pick the adapter, so naming-wise this is the
  `claude_plugin` module; the registered adapter participates only
  for `kind == "plugin"`.)
- `config_target(scope, project_root)` — returns the
  `installed_plugins.json` path at user scope; returns `None` at
  project scope (signals `unsupported scope`).
- `secondary_target(scope)` — returns `known_marketplaces.json` path
  (or inlined per the adapter Protocol — see "Two-file write" below).
- `list_installed(scope, project_root)` — set of `<plugin>@<marketplace>`
  keys recorded for this scope.
- `entry_drift(scope, project_root, entry)` — True iff the recorded
  entry's toolkit-owned fields (`scope`, `version`) diverge from the
  sidecar's declared values.
- `diff(scope, project_root, entries, previously_allowed)` — returns a
  list of `WriteAction` items spanning both files.
- `apply(actions)` — atomic write per file, preserving sibling entries
  and unrelated top-level keys (round-trip via `json` with sorted-key
  discipline matching what Claude writes).
- `revert(scope, project_root, slug)` — remove the
  `installed_plugins.<plugin>@<marketplace>` entry for this scope; if
  the marketplace no longer has any installed plugin pointing at it,
  remove it from `known_marketplaces.json` too.

**Round-trip discipline:**

- Preserve every sibling entry and every top-level key the adapter
  does not own.
- For new `installed_plugins` entries, write only the toolkit-owned
  fields (`scope`, `version`). Do **not** write `installedAt`,
  `gitCommitSha`, `lastUpdated`, or `installPath` — Claude fills those
  on first launch. (This is the Codex MCP adapter's discipline applied
  to JSON.)
- For existing entries where the recorded version drifts from the
  sidecar:
  - `version: "latest"` in the sidecar → do **not** touch the
    recorded `version` field. ("latest" means "let Claude decide.")
  - Pinned semver in the sidecar → force-write the recorded `version`;
    Claude reconciles on next start (it will re-clone if the cache for
    that version is absent).
- On marketplace name collision (existing `known_marketplaces.<name>`
  with a different `source`), refuse with a clear
  `CannotInstall("plugin <slug>: marketplace <name> already recorded with different source")`.
- On `revert`, marketplace is removed only when no other installed
  plugin references it.

**Two-file write atomicity.** The dispatcher's atomic-write helper
operates per-file. For this adapter, we emit two `WriteAction`s
(one per file) inside a single `diff()` call and rely on the
dispatcher's existing per-file atomic write. A torn write across the
two files is recoverable — the next `check` / `fix` cycle will
reconcile because the source of truth is the toolkit sidecar, not the
on-disk state.

### CLI surface

No new commands. All existing verbs work via the matrix wiring:

- `agent-toolkit-cli link user claude plugin:superpowers`
- `agent-toolkit-cli link user claude --all` (picks up plugins via the matrix)
- `agent-toolkit-cli unlink user claude plugin:superpowers`
- `agent-toolkit-cli list plugin claude` — four-glyph status per slug
- `agent-toolkit-cli diff user claude`
- `agent-toolkit-cli check` / `fix`
- `agent-toolkit-cli doctor --group plugins --harness claude` — verifies marketplace entry present, installed_plugins entry present. Warns (does not fail) when `installPath` does not exist on disk (Claude clones lazily; warn-only matches the deferred-clone reality).
- `agent-toolkit-cli inventory plugin`
- TUI: plugins surface in the kind sidebar with the standard `[☑] [≁] [☐] [!]` glyphs.

Project scope: `link project claude plugin:<slug>` returns the existing
`unsupported scope` outcome (per `config_target` returning `None`).

### Code-path cleanup

The current code has plugin-aware branches that assume the symlink +
inline-JSON-block path. Each gets reviewed:

- `_support.py` — remove `(claude, plugin)` entries from `_USER_TARGETS`
  and `_PROJECT_TARGETS` (the adapter owns the targets now).
- `walker.py` — sidecar walker for `plugins/*.toolkit.yaml` added; the
  legacy `.claude-plugin/*.json` walker stays as a deprecation
  fall-back (emits a one-time warning in `check`).
- `schema.py` — branch for `kind == "plugin"` reads the sidecar; the
  legacy inline-block reader stays gated on legacy discovery.
- `_link_lib.py` — remove the symlink branches for `kind == "plugin"`
  (lines 300, 322); dispatch goes through the new adapter.
- `_list_json.py` — the `kind == "plugin"` branch keeps its purpose
  but reads adapter state instead of filesystem presence.
- `doctor/symlinks.py` — replace the symlink-aware plugin branch with
  adapter-driven checks (marketplace + installed_plugins entries
  present; cache path warn-only).
- `ingest/finalize.py`, `ingest/research.py` — currently treat plugin
  alongside skill/mcp/pi-extension. Continue to do so (ingest produces
  a sidecar instead of an inline-JSON block).

### Sample real sidecar

The PR lands at least one usable example sidecar in the toolkit repo so
the feature ships with a working demonstration. Candidate:

```yaml
# ~/GitHub/agent-toolkit/plugins/superpowers.toolkit.yaml
apiVersion: agent-toolkit/v1alpha2
kind: plugin
metadata:
  name: superpowers
  description: TDD, debugging, brainstorming, plan-writing — Anthropic's official engineering-discipline plugin
spec:
  harnesses: [claude]
  source:
    marketplace: claude-plugins-official
    marketplaceSource:
      source: git
      url: https://github.com/anthropics/claude-plugins-official.git
    plugin: superpowers
    version: "latest"
```

This lives in the **toolkit repo** (`~/GitHub/agent-toolkit/`), not in
this CLI repo. The CLI PR therefore lands sidecar-shape support; the
example sidecar lands as a separate toolkit-repo PR. The PR description
notes the cross-repo handoff.

### Tests

Unit (`tests/`):

- `test_claude_plugin_adapter.py` — new:
  - Round-trip preservation of unrelated sibling entries in both JSON files.
  - Idempotent `apply` (running twice produces no second-pass diff).
  - Shared-marketplace `revert` (don't delete marketplace still used by another plugin).
  - Marketplace name collision refusal.
  - `version: "latest"` leaves recorded version alone; pinned forces a rewrite.
  - User scope works; project scope returns `unsupported scope`.
- `test_walker.py` — add cases for sidecar discovery + legacy
  inline-JSON discovery + mutex refusal when both exist.
- `test_schema.py` — new sidecar branch validates; old inline-block
  shape continues to validate during deprecation window.
- `test_harness_matrix.py` — parity test exercises the updated row.

Integration (`tests/integration/` or bats, matching existing layout):

- `link → list → diff → unlink → list` cycle for `plugin:superpowers`
  against a fixture HOME with a pre-existing
  `installed_plugins.json` containing an unrelated sibling.

### Docs updates

- `docs/agent-toolkit/harness-matrix.md` — row + prose (as above).
- `docs/agent-toolkit/cli.md` — short paragraph under "Asset kinds"
  noting plugins are Claude-only and managed declaratively via the two
  JSON files; the CLI does not clone.
- `docs/agent-toolkit/schema.md` — document the new `kind: plugin`
  sidecar shape with example.
- `README.md` — one-line note.
- `AGENTS.md` — update "Asset identity / one asset, one metadata
  location" to add `plugin — sidecar plugins/<slug>.toolkit.yaml
  (preferred) OR inline agent_toolkit_cli JSON key in
  plugin.json (legacy). Never both.`

## Definition of done

- `kind: plugin` sidecar validates in both schema copies (parity hook clean).
- `(claude, plugin)` row in harness-matrix.md + parity test reflects the `config_file` mechanism against the two JSON files.
- `harness_adapters/claude_plugin.py` implements `diff`/`apply`/`revert` with the round-trip discipline above, marketplace shared-use guard on revert, and collision refusal on apply.
- `_support.py`, `walker.py`, `schema.py`, `_link_lib.py`, `_list_json.py`, `doctor/symlinks.py` reflect the new flow; legacy inline-JSON discovery stays as a deprecation fall-back with warning.
- `link`/`unlink`/`list`/`diff`/`check`/`fix`/`doctor`/`inventory` and TUI all surface plugin assets correctly.
- Tests: unit (round-trip, idempotency, shared-marketplace, collision refusal, version-pinning) + integration cycle + matrix parity, all green.
- Docs updated as above.
- Sidecar example PR queued in the toolkit repo (linked from the CLI PR description).

## Open items for plan-phase-0

These are clarifications the plan phase resolves before code lands:

1. **Exact JSON-write style** — `json.dumps(..., indent=2, sort_keys=False)` vs preserving Claude's exact whitespace. Plan spike: round-trip a real `installed_plugins.json` and diff bytes.
2. **Where the sidecar lives in the toolkit repo** — `plugins/<slug>.toolkit.yaml` vs `plugins/<slug>/<slug>.toolkit.yaml`. Lean: flat (matches `mcps/`).
3. **`version` field write semantics under `"latest"`** — confirmed in the spec above but verify against Claude Code's behavior when the recorded `version` is missing entirely.
4. **`config_file+folder` vs two-file `config_file`** — does the existing `config_file+folder` mechanism extend naturally to "two files, no folder"? Plan-phase-0 decides whether to introduce a new mechanism label (`config_file+config_file`?) or keep "config_file" loose and document the multi-file behavior in adapter docstring.

## Cross-repo follow-ups (not blockers for this PR)

- Toolkit repo: add a sidecar for `superpowers` (and optionally
  `compound-engineering`) so the feature ships with a usable example.
- Retire or repurpose `plugins/registry.json` in the toolkit repo.
- Decide the fate of the four existing physical submodules under
  `plugins/` (`atomic-agents`, `companion-html`, `figma`,
  `anthropic-agent-skills`).
