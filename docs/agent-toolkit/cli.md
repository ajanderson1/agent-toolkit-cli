# agent-toolkit CLI reference

The `agent-toolkit` CLI wires assets from `~/GitHub/agent-toolkit/` into per-harness
directories on the current machine. Bash subcommands (`link`, `unlink`, `list`, `diff`)
run with zero dependencies. Python subcommands (`check`, `fix`, `doctor`, `new`) require
`uv` and the installed package.

The four supported harnesses and their per-harness skills directories:

| Harness | Skills target |
|---|---|
| `claude` | `~/.claude/skills/` |
| `codex` | `~/.codex/skills/` |
| `opencode` | `~/.config/opencode/skills/` |
| `pi` | `~/.pi/agent/skills/` |

Claude also supports `agents/`, `commands/`, `hooks/`, and `plugins/`. Codex and OpenCode
support MCPs via their own config files. The CLI silently skips asset-type / harness
combinations that have no target slot.

## Output conventions

Every command prints a short header to **stderr** before doing its work and a one-sentence summary to **stderr** after. The actual data the command produces (symlink listings, validation results, scaffolded files) goes to **stdout**, so pipes work the same as before:

```bash
bin/agent-toolkit list | awk '{print $1}'
```

If you need silence (CI, scripts, fixtures), set `AGENT_TOOLKIT_QUIET=1` or pass `--quiet` / `-q`:

```bash
AGENT_TOOLKIT_QUIET=1 bin/agent-toolkit list
bin/agent-toolkit link user claude --quiet
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
| `--repo-root DIR` | Path to the toolkit repo (default: `$PWD`) |
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

**Examples:**

```bash
# Bootstrap a fresh machine — opt every compatible asset in:
bin/agent-toolkit link user claude --all

# Or curate by hand:
$EDITOR ~/.agent-toolkit.yaml
bin/agent-toolkit link user claude

# Add one asset incrementally:
bin/agent-toolkit link user claude skill:figma

# Same shape at project scope:
bin/agent-toolkit link project claude skill:figma
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
| `--repo-root DIR` | Path to the toolkit repo (default: `$PWD`) |
| `--dry-run` | Print what would be removed; make no changes |

The bare form errors with a hint because its blast radius differs from `--all`.
The mental model: the YAML file is the user's *authored intent*; the symlinks
are the *projection of intent*. `unlink --all` resets the projection;
`unlink <kind>:<slug>` resets both. Neither form deletes the YAML file.

To rebuild after `unlink --all`, run `link <scope> <harness>` (re-projects the
existing file).

**Examples:**

```bash
bin/agent-toolkit unlink user claude --all              # blow away all claude symlinks
bin/agent-toolkit unlink user claude skill:figma        # opt one skill out
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
| `<kind>` | One of `skill`, `agent`, `command`, `hook`, `plugin`. Optional. |
| `<harness>` | One of `claude`, `codex`, `opencode`, `pi`. Optional. |

| Flag | Description |
|---|---|
| `--repo-root DIR` | Path to the toolkit repo (default: `$PWD`) |

Output is grouped by kind. Each row carries `[harnesses]` brackets (omitted
when filtering by harness) and two install-state columns:

- `user:✓` — the slug appears in `~/.agent-toolkit.yaml` AND a symlink exists
  in `~/<harness-target>/<kind>/`.
- `project:✓` — same logic against `<cwd>/.agent-toolkit.yaml` and
  `<cwd>/.<harness>/`. Outside a project (no `.agent-toolkit.yaml` in CWD),
  the column is always `—`.

Disambiguation: position-1 is `<kind>` if it matches a known kind, else
`<harness>` if it matches a known harness, else error. `list mcp` prints a
note (MCPs ship via the harness's `mcp.json`, not via symlinks).

**Examples:**

```bash
bin/agent-toolkit list                      # full inventory
bin/agent-toolkit list skill                # skills only
bin/agent-toolkit list claude               # claude-compatible assets
bin/agent-toolkit list skill claude         # both filters
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## diff

Preview what `link` would change without making any changes.

```
Usage: agent-toolkit diff <user|project> <harness>
```

| Flag | Description |
|---|---|
| `--repo-root DIR` | Path to the toolkit repo (default: `$PWD`) |

Alias for `link --dry-run`. Lines prefixed `+` would be created; lines prefixed `-` would
be removed.

**Example:**
```bash
bin/agent-toolkit diff project opencode
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## check

Validate every asset's frontmatter against the v1alpha1 schema and detect AGENTS.md drift.

```
Usage: uv run agent-toolkit check [--exit-code]
```

| Flag | Description |
|---|---|
| `--exit-code` | Exit non-zero if any errors or drift are found (required for CI/lefthook) |

Prints `OK` on success. On failure, prints a list of schema violations and/or a diff of
what `fix` would regenerate. The lefthook pre-commit gate runs `check --exit-code`
automatically on every commit.

**Example:**
```bash
uv run agent-toolkit check --exit-code
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## fix

Regenerate auto-generated regions in `AGENTS.md`.

```
Usage: uv run agent-toolkit fix [--only=<region>] [--to-stdout]
```

| Flag | Description |
|---|---|
| `--only=<region>` | Limit regeneration to one named region (`component-table` or `submodule-table`) |
| `--to-stdout` | Print the regenerated content to stdout instead of writing to `AGENTS.md` |

Regions are bounded by HTML comment markers:

```
<!-- BEGIN_AGENT_TOOLKIT:component-table — DO NOT EDIT — regenerated by `agent-toolkit fix` -->
...
<!-- END_AGENT_TOOLKIT:component-table -->
```

Output is byte-stable and sorted by path, so results are deterministic across machines.

**Example:**
```bash
uv run agent-toolkit fix --only=component-table
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## doctor

Run an environment sanity check.

```
Usage: uv run agent-toolkit doctor [--repo-root DIR]
```

| Flag | Description |
|---|---|
| `--repo-root DIR` | Path to the toolkit repo (default: `$PWD`) |

Verifies that the schema file exists, `AGENTS.md` is present, `git` and `gh` are on
`$PATH`, and all submodules are initialised. Run after a fresh clone before any other
subcommand.

**Example:**
```bash
uv run agent-toolkit doctor --repo-root ~/GitHub/agent-toolkit
```

> _Header & summary go to stderr; suppress with `--quiet` or `AGENT_TOOLKIT_QUIET=1`._

---

## new

Scaffold a new asset with valid v1alpha1 frontmatter.

```
Usage: uv run agent-toolkit new <kind> <slug>
```

| Argument | Description |
|---|---|
| `kind` | One of: `skill`, `agent`, `command`, `hook`, `mcp`, `plugin` |
| `slug` | Lowercase kebab-case name matching `^[a-z0-9][a-z0-9-]*$` |

Creates the asset at its canonical path with `lifecycle: experimental`, a TODO description
placeholder, and `spec.harnesses: [claude]`. Edit the description and harnesses, then run
`check` before committing.

| Kind | Scaffolded path |
|---|---|
| `skill` | `skills/<slug>/SKILL.md` |
| `agent` | `agents/<slug>.md` |
| `command` | `commands/<slug>.md` |
| `hook` | `hooks/<slug>.meta.yaml` |
| `mcp` | `mcps/<slug>/mcp.json` |
| `plugin` | `plugins/<slug>/marketplace.json` |

**Example:**
```bash
uv run agent-toolkit new skill my-research-skill
$EDITOR skills/my-research-skill/SKILL.md
uv run agent-toolkit check
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
`plugins`. The `mcps` kind is not yet scope-routed (MCPs ship via per-harness
JSON config files). Each section is a flat list of slugs that must match
`metadata.name` exactly. Empty file or empty sections are valid.

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
Usage: agent-toolkit link|unlink|list|diff user conventions [--repo-root DIR] [--dry-run]
```

| Flag | Description |
|---|---|
| `--repo-root DIR` | Path to the toolkit repo containing `CONVENTIONS.md` and `conventions/` (default: `$PWD`) |
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

- [`schemas/asset-frontmatter.v1alpha1.json`](../../schemas/asset-frontmatter.v1alpha1.json) — JSON Schema source (2020-12 dialect)
- [`docs/agent-toolkit/schema.md`](schema.md) — field reference, cross-field rules, worked examples
- [`docs/superpowers/specs/2026-04-30-agent-toolkit-foundation-and-wiring-design.md`](../superpowers/specs/2026-04-30-agent-toolkit-foundation-and-wiring-design.md) — design spec (Sections 2, 3, 4, 6)
