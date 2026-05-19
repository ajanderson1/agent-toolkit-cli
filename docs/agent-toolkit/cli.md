# agent-toolkit CLI reference

The `agent-toolkit` CLI wires assets from `~/GitHub/agent-toolkit/` into per-harness
directories on the current machine. Bash subcommands (`link`, `unlink`, `list`, `diff`)
run with zero dependencies. Python subcommands (`check`, `fix`, `doctor`, `new`) require
`uv` and the installed package.

## Repo discovery — the two-flag contract

Every subcommand accepts up to two repo-pointing flags:

| Flag | Means | Default |
|---|---|---|
| `--toolkit-repo PATH` | The agent-toolkit SSOT (the library that ships assets) | resolved via four-step order below |
| `--project PATH` | The consumer project being acted on (allow-lists, project-scope symlinks) | `.` (CWD) |

`--toolkit-repo` resolves in four steps, first match wins:

1. The explicit `--toolkit-repo` flag value.
2. The `AGENT_TOOLKIT_REPO` environment variable.
3. Walk up from the current directory looking for an `.agent-toolkit-source` marker file.
4. The default `~/GitHub/agent-toolkit/` path.

If nothing resolves, the CLI exits with an actionable error pointing at the install instructions.

`--project` is simpler: it defaults to the current directory and is only
relevant for subcommands that act on the consumer project (`link`, `unlink`,
`list`, `diff`). SSOT-only subcommands (`check`, `fix`, `new`, `doctor`,
`inventory`, `ingest`) take only `--toolkit-repo`.

The four supported harnesses and their per-harness skills directories:

| Harness | Skills target |
|---|---|
| `claude` | `~/.claude/skills/` |
| `codex` | `~/.codex/skills/` |
| `opencode` | `~/.config/opencode/skills/` |
| `pi` | `~/.pi/agent/skills/` |

Claude also supports `agents/`, `commands/`, `hooks/`, and `plugins/`. Pi additionally
supports `agents/` and TypeScript-based extensions at `~/.pi/agent/extensions/`
(asset kind `pi-extension`, sourced from `extensions/<slug>/extension.meta.yaml` in the
toolkit repo — distinct from Claude Code's `plugins/`). Codex and OpenCode
support MCPs via their own config files. The CLI silently skips asset-type / harness
combinations that have no target slot.

## Output conventions

Every command prints a short header to **stderr** before doing its work and a one-sentence summary to **stderr** after. The actual data the command produces (symlink listings, validation results, scaffolded files) goes to **stdout**, so pipes work the same as before:

```bash
agent-toolkit list | awk '{print $1}'
```

If you need silence (CI, scripts, fixtures), set `AGENT_TOOLKIT_QUIET=1` or pass `--quiet` / `-q`:

```bash
AGENT_TOOLKIT_QUIET=1 agent-toolkit list
agent-toolkit link user claude --quiet
```

The summary line typically includes a next-step hint (e.g. "run 'agent-toolkit check'"). Hints are part of the contract — if a hint becomes stale, fix it in the same commit that breaks it.

---

## link

Project assets per the allow-list at `~/.agent-toolkit.yaml` (user scope) or
`<project>/.agent-toolkit.yaml` (project scope). Both files share the same shape.

```
Usage:
  agent-toolkit link <user|project> <harness>                     # project current allow-list
  agent-toolkit link <user|project> <harness> --all [-y]          # snapshot all compatible, then project
  agent-toolkit link <user|project> <harness> <kind>:<slug>       # add one slug, then project
```

| Flag | Description |
|---|---|
| `--all` | Snapshot every harness-compatible asset into the allow-list, replacing existing content. |
| `-y`, `--yes` | Skip the confirmation prompt under `--all` when the file is non-empty. |
| `--toolkit-repo DIR` | Path to the agent-toolkit repo (resolves via the four-step order if omitted) |
| `--project DIR` | Path to the consumer project (default: `$PWD`) |
| `--dry-run` | Print what would change; make no changes |

**Bare form** reads the allow-list and projects every listed slug whose
`spec.harnesses` contains the requested harness. If the file is missing,
errors with a hint pointing at `--all` or `<kind>:<slug>` — there is no silent
default-on.

**`--all`** captures the current toolkit state into the YAML file, then
projects. If the file already has slugs, prompts before overwriting (skip with
`-y`). In a non-TTY environment without `-y`, refuses with a TTY message.

**`<kind>:<slug>`** adds one slug to the relevant section of the YAML file,
creating the file if missing, and projects. Idempotent — running twice has the
same effect as running once. Errors out if the slug doesn't exist or if the
asset doesn't declare the requested harness.

### MCPs

`mcp:<name>` is recognised the same as other kinds (`skill:`, `agent:`, etc.). The
allow-list YAML is updated under the `mcps:` section; per-harness MCP adapters
write the appropriate config file on `link`:

| Harness                    | Status (this release)                                 | Target |
|----------------------------|--------------------------------------------------------|--------|
| `codex`                    | ✓ implemented                                          | `~/.codex/config.toml` (user); `<project>/.codex/config.toml` (project, only if `.codex/` exists) |
| `claude`, `opencode`, `pi` | not yet — `link`/`unlink` print a loud skip message    | —      |

For `codex`, `link` mutates `[mcp_servers.<name>]` tables via a round-trip
`tomlkit` parse, preserving every other section, comment, and key order.
The adapter refuses MCPs whose `spec.mcp.transport` is not `stdio`.

**Four-glyph status** in `list` (and the TUI):

| Status (JSON)              | Glyph | Meaning |
|----------------------------|-------|---------|
| `linked-matches`           | `☑`   | allow-listed, installed, no drift |
| `linked-drifted`           | `≁`   | allow-listed, installed, structural drift |
| `unlinked-allowlisted`     | `☐`   | allow-listed, not installed (run `link` to fix) |
| `installed-not-allowlisted`| `!`   | hand-rolled — never touched by this CLI |

`agent-toolkit list mcp` (or `--format=json`) renders the four-glyph status.
The human-readable text output shows `user:` and `project:` columns with these
glyphs; JSON includes a `status` field with the string values above.

```bash
agent-toolkit link project codex mcp:context7
# → .codex/config.toml written (or skipped if harness unimplemented)

agent-toolkit list mcp codex
#   context7              [codex]                user:☑ project:☐
```

**Examples:**

```bash
# Bootstrap a fresh machine — opt every compatible asset in:
agent-toolkit link user claude --all

# Or curate by hand:
$EDITOR ~/.agent-toolkit.yaml
agent-toolkit link user claude

# Add one asset incrementally:
agent-toolkit link user claude skill:figma

# Same shape at project scope:
agent-toolkit link project claude skill:figma
```

### Plan mode (`--plan -`)

Apply a batch of `<kind>:<slug>` entries from stdin in a single invocation:

```
agent-toolkit link <user|project> <harness> --plan -
```

Format: one `<kind>:<slug>` per line, `#`-prefixed lines and blanks ignored,
EOF terminates. Each entry is applied independently — a failure on one line
does not abort the rest; per-line errors are reported on stderr.

Exit codes:

- `0` — every entry applied successfully.
- `1` — at least one entry failed (allow-list write or symlink creation).
- `2` — grammar error (e.g. combined with `--all`, missing `-` after `--plan`,
  malformed `<kind>:<slug>`).

Cannot be combined with `--all` or with a positional `<kind>:<slug>`. Used by
the TUI's batch-apply path; also handy for scripted bootstraps.

```bash
agent-toolkit link user claude --plan - <<'EOF'
skill:journal
skill:conventions
agent:scout
EOF
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## unlink

Remove symlinks (and optionally remove from the allow-list).

```
Usage:
  agent-toolkit unlink <user|project> <harness>                   # error — explicit target required
  agent-toolkit unlink <user|project> <harness> --all             # remove every symlink, preserve YAML
  agent-toolkit unlink <user|project> <harness> <kind>:<slug>     # remove from YAML, prune symlink
```

| Flag | Description |
|---|---|
| `--all` | Remove every symlink in the scope+harness target dir that points into the toolkit repo. The allow-list YAML is untouched (intent preserved). |
| `--toolkit-repo DIR` | Path to the agent-toolkit repo (resolves via the four-step order if omitted) |
| `--project DIR` | Path to the consumer project (default: `$PWD`) |
| `--dry-run` | Print what would be removed; make no changes |

The bare form errors with a hint because its blast radius differs from `--all`.
The mental model: the YAML file is the user's *authored intent*; the symlinks
are the *projection of intent*. `unlink --all` resets the projection;
`unlink <kind>:<slug>` resets both. Neither form deletes the YAML file.

To rebuild after `unlink --all`, run `link <scope> <harness>` (re-projects the
existing file).

**Examples:**

```bash
agent-toolkit unlink user claude --all              # blow away all claude symlinks
agent-toolkit unlink user claude skill:figma        # opt one skill out
```

### Plan mode (`--plan -`)

Apply a batch of `<kind>:<slug>` entries from stdin in a single invocation:

```
agent-toolkit unlink <user|project> <harness> --plan -
```

Format: one `<kind>:<slug>` per line, `#`-prefixed lines and blanks ignored,
EOF terminates. Each entry is applied independently — a failure on one line
does not abort the rest; per-line errors are reported on stderr.

Exit codes:

- `0` — every entry unlinked successfully.
- `1` — at least one entry failed (allow-list write or symlink removal).
- `2` — grammar error (e.g. combined with `--all`, missing `-` after `--plan`,
  malformed `<kind>:<slug>`).

Cannot be combined with `--all` or with a positional `<kind>:<slug>`. Used by
the TUI's batch-apply path; also handy for scripted teardowns.

```bash
agent-toolkit unlink user claude --plan - <<'EOF'
skill:journal
skill:conventions
EOF
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## list

Print the asset library with install-state columns for each scope.

```
Usage:
  agent-toolkit list [<kind>] [<harness>]
```

| Argument | Description |
|---|---|
| `<kind>` | One of `skill`, `agent`, `command`, `hook`, `plugin`, `mcp`, `pi-extension`. Optional. |
| `<harness>` | One of `claude`, `codex`, `opencode`, `pi`. Optional. |

| Flag | Description |
|---|---|
| `--toolkit-repo DIR` | Path to the agent-toolkit repo (resolves via the four-step order if omitted) |
| `--project DIR` | Path to the consumer project (default: `$PWD`) |

Output is grouped by kind. Each row carries `[harnesses]` brackets (omitted
when filtering by harness) and two install-state columns:

- `user:✓` — the slug appears in `~/.agent-toolkit.yaml` AND a symlink exists
  in `~/<harness-target>/<kind>/`.
- `project:✓` — same logic against `<cwd>/.agent-toolkit.yaml` and
  `<cwd>/.<harness>/`. Outside a project (no `.agent-toolkit.yaml` in CWD),
  the column is always `—`.

Disambiguation: position-1 is `<kind>` if it matches a known kind, else
`<harness>` if it matches a known harness, else error. MCPs use the four-glyph
status described above; they do not create symlinks (config-file entries instead).

**Examples:**

```bash
agent-toolkit list                      # full inventory
agent-toolkit list skill                # skills only
agent-toolkit list claude               # claude-compatible assets
agent-toolkit list skill claude         # both filters
```

### Cross-scope coverage indicator

When the same asset is linked at both user and project scope, the project
segment of the row carries a 🌐 suffix to flag the redundancy. Example:

    alpha                [claude]                       user:✓ project:✓ 🌐

The indicator is informational only — it does not block or warn. (Policy
enforcement of cross-scope installs is tracked separately in
[#69](https://github.com/ajanderson1/agent-toolkit-cli/issues/69).) The same
marker appears in the TUI's project-scope grid view and is summarised in the
`agent-toolkit doctor user-scope-coverage` group.

### JSON output (`--format=json`)

Machine-readable view of the same inventory data the human-formatted output
covers, with explicit per-cell install state. Consumed by the TUI and any
external tooling.

```
agent-toolkit list --format=json [--toolkit-repo DIR] [--project DIR] [<kind>] [<harness>]
```

Top-level shape:

```json
{
  "toolkit_root": "/path/to/agent-toolkit",
  "harnesses": ["claude", "codex", "opencode", "pi"],
  "assets": [
    {
      "kind": "skill",
      "slug": "journal",
      "origin": "first-party",
      "description": "Journal Skill.",
      "path": "/.../skills/journal/SKILL.md",
      "declared_harnesses": ["claude"],
      "cells": [
        {"harness": "claude", "scope": "user",
         "status": "linked", "target": "/.../skills/journal", "allowlisted": true},
        {"harness": "codex",  "scope": "user",
         "status": "unsupported", "target": null, "allowlisted": false}
      ]
    }
  ]
}
```

For symlink-based kinds (`skill`, `agent`, etc.), cell `status` is one of:
`linked`, `unlinked`, `broken`, `unsupported`. The `target` field is the
**raw `os.readlink()`** value when the symlink exists (both `linked` and
`broken`) — consumers see one consistent representation regardless of whether
the link resolves correctly. `unlinked` and `unsupported` cells have `target: null`.

For `mcp` kind, cell `status` is one of: `linked-matches`, `linked-drifted`,
`unlinked-allowlisted`, `installed-not-allowlisted`. The `target` field is the
config file path (e.g. `~/.codex/config.toml`) when the entry is installed
(both `linked-*` statuses); `unlinked-allowlisted` and `installed-not-allowlisted`
cells have `target: null`.

### Human-readable report (`--report`)

Grouped, plain-text view of the same inventory data: harness → scope → kind
→ asset entries. Deterministic ordering — two runs against the same state
produce byte-identical output, so the report diffs cleanly in CI logs.

```
agent-toolkit list --report [--toolkit-repo DIR] [--project DIR] [<kind>] [<harness>]
```

Example:

```
Asset inventory report

Toolkit:  /Users/aj/GitHub/agent-toolkit
Project:  /Users/aj/code/myproj

claude
  user
    skill
      alpha        linked       /Users/aj/GitHub/agent-toolkit/skills/alpha
      beta         unlinked
```

`--report` is mutually exclusive with `--format=json`. Pass either, not both.

`allowlisted` reflects the YAML allow-list (`~/.agent-toolkit.yaml` for
`scope: user`, `<cwd>/.agent-toolkit.yaml` for `scope: project`) and is
reported truthfully even for `unsupported` cells: the allow-list is
harness-independent, so a slug can be allow-listed for a harness that does
not support it. The TUI uses this to render the cell as "blocked by harness"
rather than "user opted out".

Output is sorted by `(kind, slug)` for stable, diffable JSON. Pretty-printed
with two-space indent.

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## diff

Preview what `link` would change without making any changes.

```
Usage: agent-toolkit diff <user|project> <harness>
```

| Flag | Description |
|---|---|
| `--toolkit-repo DIR` | Path to the agent-toolkit repo (resolves via the four-step order if omitted) |
| `--project DIR` | Path to the consumer project (default: `$PWD`) |

Alias for `link --dry-run`. Lines prefixed `+` would be created; lines prefixed `-` would
be removed.

**Example:**
```bash
agent-toolkit diff project opencode
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## tui

Launch the Textual cockpit:

    agent-toolkit-cli tui

The TUI is a visual cockpit over `link`/`unlink`/`list`. It never writes to the
filesystem directly — every mutation goes through `agent-toolkit-cli`. See the
TUI design spec at `docs/superpowers/specs/2026-05-03-agent-toolkit-tui-design.md`
for the full contract.

### Keyboard bindings

| Key | Action |
|---|---|
| `Enter` | Toggle the focused cell (link ↔ unlink) |
| `Tab` | Cycle focus between the kinds sidebar and the asset grid |
| `Ctrl+S` | Apply all pending changes |
| `Ctrl+D` | Diff (dry-run) pending changes |
| `Ctrl+R` | Refresh state from disk |
| `q` | Quit |

### Headless mode

For scripted use and Layer-3 smoke tests:

    agent-toolkit-tui --headless --plan plan.txt --apply --scope user --harness claude --op link

`plan.txt` is a kind:slug-per-line file (same format as `link --plan -`). Without
`--apply`, runs in dry-run mode. Exits 0 on full success, 1 on any failure.

---

## check

Validate every asset's frontmatter against the v1alpha2 schema and detect AGENTS.md drift.

```
Usage: uv run agent-toolkit-cli check [--exit-code]
```

| Flag | Description |
|---|---|
| `--exit-code` | Exit non-zero if any errors or drift are found (required for CI/lefthook) |

Prints `OK` on success. On failure, prints a list of schema violations and/or a diff of
what `fix` would regenerate. The lefthook pre-commit gate runs `check --exit-code`
automatically on every commit.

**Example:**
```bash
uv run agent-toolkit-cli check --exit-code
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## fix

Regenerate auto-generated regions in `AGENTS.md` and/or reconcile MCP drift.

```
Usage: uv run agent-toolkit-cli fix [--only=<region>] [--to-stdout] [--harness] [--scope] [--mcps-only]
```

| Flag | Description |
|---|---|
| `--only=<region>` | Limit AGENTS.md regeneration to one named region (`component-table` or `submodule-table`) |
| `--to-stdout` | Print the regenerated AGENTS.md to stdout instead of writing to the file (skips MCP reconcile) |
| `--harness <harness>` | Harness for MCP reconcile (default: `codex`; one of `claude`, `codex`, `opencode`, `pi`) |
| `--scope <scope>` | Scope for MCP reconcile (default: `user`; one of `user`, `project`) |
| `--mcps-only` | Skip AGENTS.md region regen; reconcile MCPs only |

Regions are bounded by HTML comment markers:

```
<!-- BEGIN_AGENT_TOOLKIT:component-table — DO NOT EDIT — regenerated by `agent-toolkit fix` -->
...
<!-- END_AGENT_TOOLKIT:component-table -->
```

AGENTS.md output is byte-stable and sorted by path, so results are deterministic
across machines.

MCP reconcile brings on-disk config files (e.g. `~/.codex/config.toml`) into
sync with the canonical template render from the allow-list. Drift is detected
via structural comparison (toml parse, not string match), so formatting edits
are allowed. When nothing would change, file mtime is preserved.

**Examples:**
```bash
# Regenerate AGENTS.md component table:
uv run agent-toolkit-cli fix --only=component-table

# Reconcile MCPs for the current user/codex scope:
uv run agent-toolkit-cli fix --mcps-only

# Regenerate AGENTS.md AND reconcile MCPs in one go:
uv run agent-toolkit-cli fix
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## doctor

Run environment, harness, and asset health checks.

```
Usage: uv run agent-toolkit-cli doctor [SLUG] [--group GROUP] [--harness H] [--scope S] [--verbose]
```

| Argument | Description |
|---|---|
| `SLUG` (optional) | Diagnose one specific asset by slug (e.g. `journal`, `context7`). Overrides `--group`. |

| Flag | Description |
|---|---|
| `--toolkit-repo DIR` | Path to the agent-toolkit repo (resolves via the four-step order if omitted) |
| `--group <name>` | Run only one group: `environment`, `symlink-integrity`, `conventions`, `submodule-health`, `frontmatter`, `duplicates`, `harness-homes`, `allowlist-audit`, or `mcps` |
| `--harness <harness>` | Harness for group checks (default: `claude`; one of `claude`, `codex`, `opencode`, `pi`). Only affects symlink-integrity and mcps groups. |
| `--scope <scope>` | Scope for mcps group (default: `user`; one of `user`, `project`) |
| `--verbose` | Expand each group's evidence |
| `--exit-code` | Exit with code 1 if any group fails (default: always exit 0) |

Verifies toolkit setup (schema, AGENTS.md, git, gh, submodules), asset conventions,
symlink integrity, and MCP installation state. The `mcps` group reports:

- **Drift:** installed entry differs from canonical template (warn if mismatched)
- **Env vars:** required vars from `spec.mcp.env` present in shell (warn if missing)
- **Prerequisites:** tools from `spec.mcp.prerequisites` on `$PATH` (warn if missing)

The `mcps` group skips silently with an OK status if the harness has no adapter yet
(e.g. claude, opencode, pi await follow-up PRs).

**Examples:**
```bash
# Full health check with default harness (claude):
uv run agent-toolkit-cli doctor

# MCP-specific check for codex/user:
uv run agent-toolkit-cli doctor --group mcps --harness codex --scope user

# Diagnose a single asset:
uv run agent-toolkit-cli doctor context7

# Verbose output:
uv run agent-toolkit-cli doctor --group mcps --verbose
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## new

Scaffold a new asset with valid v1alpha2 frontmatter.

```
Usage: uv run agent-toolkit-cli new <kind> <slug>
```

| Argument | Description |
|---|---|
| `kind` | One of: `skill`, `agent`, `command`, `hook`, `mcp`, `plugin`, `pi-extension` |
| `slug` | Lowercase kebab-case name matching `^[a-z0-9][a-z0-9-]*$` |

Creates the asset at its canonical path with `lifecycle: experimental`, a TODO description
placeholder, and `spec.harnesses: [claude]` (`[pi]` for `pi-extension`). Edit the
description and harnesses, then run `check` before committing.

| Kind | Scaffolded path |
|---|---|
| `skill` | `skills/<slug>/SKILL.md` |
| `agent` | `agents/<slug>.md` |
| `command` | `commands/<slug>.md` |
| `hook` | `hooks/<slug>.meta.yaml` |
| `mcp` | `mcps/<slug>/mcp.json` |
| `plugin` | `plugins/<slug>/marketplace.json` |
| `pi-extension` | `extensions/<slug>/extension.meta.yaml` |

**Example:**
```bash
uv run agent-toolkit-cli new skill my-research-skill
$EDITOR skills/my-research-skill/SKILL.md
uv run agent-toolkit-cli check
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## Allow-list files

Both `link` scopes are opt-in via a YAML file with the same shape:

- `~/.agent-toolkit.yaml` — user scope, per-machine
- `<project>/.agent-toolkit.yaml` — project scope, in-repo

```yaml
# .agent-toolkit.yaml
skills:
  - aj-workflow
  - journal
  - conventions
agents:
  - scout
  - builder
hooks:
  - confirm-rm
commands: []
plugins: []
```

Section keys map to asset kinds: `skills`, `agents`, `commands`, `hooks`,
`plugins`, `pi_extensions`. The `mcps` kind is not yet scope-routed (MCPs
ship via per-harness JSON config files). Each section is a flat list of
slugs that must match `metadata.name` exactly. Empty file or empty sections
are valid.

The CLI accepts both inline (`skills: [a, b]`) and multi-line (one slug per
dash) forms when reading. The internal writer (used by `link <kind>:<slug>`
and `link --all`) emits the multi-line form so diffs are clean.

**Layering rule.** Scopes do not merge at link-time. Each scope projects into
its own directory (`~/<harness-target>/` vs `./<harness-target>/`); the
harness loads both at runtime. The intersection rule per scope is unchanged:
a symlink is created iff the slug is in the relevant allow-list AND the
asset's `spec.harnesses` contains the requested harness.

---

## Conventions projection

Projects `CONVENTIONS.md` and `conventions/` from the toolkit repo into the
neutral shared path (`~/.conventions/`) and then into each harness's config
directory — without embedding the harness or repo location in any skill or
agent prose.

```
Usage: agent-toolkit link|unlink|list|diff user conventions [--toolkit-repo DIR] [--dry-run]
```

| Flag | Description |
|---|---|
| `--toolkit-repo DIR` | Path to the agent-toolkit repo containing `CONVENTIONS.md` and `conventions/` (resolves via the four-step order if omitted) |
| `--dry-run` | Print what would change; make no changes (`link` and `diff` only) |

### Three-layer projection

```text
Layer 1 — source of truth (toolkit repo)
  <repo>/CONVENTIONS.md
  <repo>/conventions/

Layer 2 — neutral public path (single indirection)
  ~/.conventions/CONVENTIONS.md  → Layer 1 file
  ~/.conventions/conventions/    → Layer 1 dir

Layer 3 — per-harness slots (point at Layer 2)
  Claude:    ~/.claude/CONVENTIONS.md   → ~/.conventions/CONVENTIONS.md
             ~/.claude/conventions/     → ~/.conventions/conventions/
  Codex:     ~/.codex/AGENTS.md         → ~/.conventions/CONVENTIONS.md
  OpenCode:  ~/.config/opencode/AGENTS.md → ~/.conventions/CONVENTIONS.md
  Pi:        ~/.pi/agent/AGENTS.md      → ~/.conventions/CONVENTIONS.md
```

Layer 3 slots are created only when the harness directory already exists on
disk. Slots for absent harnesses are silently skipped.

`unlink user conventions` removes Layer 3 slots only; Layer 2 persists so
skills and agents that cite `~/.conventions/...` remain valid.

`list user conventions` prints the full chain for each active slot.

`diff user conventions` is an alias for `link user conventions --dry-run`.

### Bootstrap

```bash
# Fresh machine — run once after `agent-toolkit link user <harness>`:
agent-toolkit link user conventions
```

Idempotent: re-running self-heals stale or missing symlinks.

### Design reference

[`docs/superpowers/specs/2026-04-30-neutral-conventions-path-design.md`](../superpowers/specs/2026-04-30-neutral-conventions-path-design.md)

---

## See also

- [`schemas/asset-frontmatter.v1alpha2.json`](../../schemas/asset-frontmatter.v1alpha2.json) — JSON Schema source (2020-12 dialect)
- [`docs/agent-toolkit/schema.md`](schema.md) — field reference, cross-field rules, worked examples
- [`docs/superpowers/specs/2026-04-30-agent-toolkit-foundation-and-wiring-design.md`](../superpowers/specs/2026-04-30-agent-toolkit-foundation-and-wiring-design.md) — design spec (Sections 2, 3, 4, 6)
