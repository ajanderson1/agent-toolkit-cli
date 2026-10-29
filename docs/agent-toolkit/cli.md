# CLI reference

Use **`atc`** for the CLI and **`att`** for the terminal UI. They are packaged
entry points, not shell aliases; `agent-toolkit-cli` and `agent-toolkit-tui`
remain equivalent supported names. Examples below use the short CLI name.
[Install/verify the package](installation.md) before managing assets.

```text
atc [--project DIRECTORY] GROUP VERB ...
atc update [--check] [--main]
atc completion init SHELL
atc completion install|uninstall [--shell SHELL] [--rc-file PATH]
```

| Root option | Meaning |
|---|---|
| `--project DIRECTORY` | Consumer directory (default: current directory), **not** project scope or a package-update target. |
| `--version`, `-V` | Print the installed package version without a network check. |
| `--help` | Show read-only help; use `GROUP VERB --help` for kind-specific flags. |

A verb's `-p/--project`, where supported, selects **scope**, not a directory.
Options and defaults are deliberately nonuniform across kinds.

## Toolkit package updates

```bash
atc update --check         # Fresh stable-release metadata; no package changes
atc update                # Update both CLI and TUI in a supported uv tool environment
att update                # Same operation, without opening the TUI
atc update --main --check  # Explicit development-commit comparison
atc update --main          # Explicit development build/update
```

These root utilities update the **Toolkit package**, not library assets or
harness exposure. `--check` returns zero for a successful check even when a newer
version exists; errors return nonzero. Stable mode does not replace an equal or
newer installed version. `--main` compares commit provenance instead of relying
on version numbers. [Full commands, channel rules and recovery](updates.md).

### Automatic notices

Interactive CLI notices go to stderr only when stdout **and** stderr are TTYs;
pipes, explicit formats, help/version and completion do not trigger checks.
Interactive TUI startup checks in a background worker. Results cache for six
hours; failures back off for 15 minutes and do not block normal use. Set
`AGENT_TOOLKIT_NO_UPDATE_CHECK=1` to opt out; explicit `update --check` still
refreshes. [Cache, timeout and privacy details](updates.md#startup-notices).

### Update safety and provenance

Replacement requires a non-editable `uv tool` installation, uv and Git. The
updater builds a verified canonical commit in a temporary checkout, retains its
wheel and source/hash receipt, then invokes uv. Other environments are refused;
read-only checks still work there. No operator checkout, asset backing, harness
settings or queued TUI intents are migrated. Fetch/build failures precede
replacement; package-manager failure has no automatic rollback. Restart running
TUIs afterward. [Provenance and retained files](updates.md#build-and-installation-provenance).

## Shell completion

```bash
atc completion install --shell zsh
source ~/.zshrc
```

Use the printed path for custom dotfiles. `install`/`uninstall` also accept
`--shell bash|fish` and `--rc-file PATH`; omitting `--shell` reads `$SHELL`.
`atc completion init zsh|bash|fish` only prints source. `att completion ...`
exposes the same utility. Bash requires 4.4+.

This registers all four executable names for dynamic command/flag/declared
choice/path completion. It does not discover asset slugs or remote repositories,
run application update checks, or launch the TUI on TAB. Only explicit
completion install/uninstall changes the marked shell configuration block;
package installation alone does not activate it. Setup preserves unrelated text,
permissions and symlinked layouts; it does not create an automatic backup.
[Shell-specific setup, internals, removal and troubleshooting](shell-completion.md).

## Groups and verbs

Plural names are canonical; singular aliases remain accepted, including `instruction` → `instructions`.

| Group | Singular alias | Shipped verbs |
|---|---|---|
| `skills` | `skill` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `agents` | `agent` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `commands` | `command` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `instructions` | `instruction` | pull, restore, install, uninstall, list, status, doctor |
| `pi-extensions` | `pi-extension` | add, install, uninstall, enable, disable, reset-selection, migrate-npm-records, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `mcps` | `mcp` | add, install, uninstall, list, status, update, remove, import, migrate, doctor |
| `bundles` | `bundle` | install, validate |

`update` and `completion` are package utilities, and `catalog` manages a shared
subscription; none is an additional asset kind. Bundles is also a utility.

Each group supports `list` as `ls` where list exists, **except Instructions**. Skills also accepts `rm` for remove. Bundles is a utility, not another asset kind. Flags and argument cardinality are deliberately nonuniform; use `GROUP VERB --help` for the exact surface.

## Shared catalogue utility

`catalog subscribe URL [--ref REF]`, `catalog unsubscribe`, and
`catalog list [--kind skills|agents|commands|pi-extensions] [--json]` manage one
shared subscription. Each kind has `catalog list`; Git catalogue acquisition uses
`catalog add KEY` or `catalog enable KEY`. New agent/command exposure commands
require `--scope global|project --harnesses NAMES`; new Git Pi exposure requires
`--scope`. Existing skills syntax is unchanged. Native npm instead uses
`pi-extensions catalog install KEY --scope global|project [--yes]`, with explicit
confirmation and no Toolkit npm registration.

`catalog validate FILE [--admission] [--base FILE] [--reviews DIR]` distinguishes
schema validation from revision-bound source/curator admission checks. This is a
publishing utility, not another asset kind. [Full format, safety and examples](catalog.md).

Agents, Commands and Git Pi also expose `check [SLUGS...] [-g|-p] [--json]` for
catalogue-associated backing. Native npm is excluded; use Pi package updates.

## Scope and target selection

There is **no blanket global default** and no rule that merely being in a Git repository chooses project scope.

| Commands | No-flag scope |
|---|---|
| Skills add/remove/import; agents add/remove/import; Pi extensions Git add/remove/import | Global library. Pi Git add/remove accept `-g` but reject `-p`; Git import has no scope flags. |
| Skills list/status/check/update/push/reset/doctor | Project if `skills-lock.json` exists in the consumer directory, otherwise global. A detected Paperclip company selects project even without that lock. |
| Skills install/uninstall | Global, except project inside a detected Paperclip company. Use `--scope project` or `-p`; global uses `--scope global` (not `-g`). |
| Agents list/status/update/push/reset/doctor; Pi extensions Git update/push/reset/doctor | Project if that kind's project lock exists, otherwise global. |
| Pi extensions list/status | Unified global/current-project discovery without requiring a Toolkit project lock; `-g` restricts discovery to global. |
| Agents install/uninstall; Pi extensions Git install/uninstall | Project. Pass `-g` for user-level projections. |
| Pi extensions npm add/install/remove/uninstall/enable/disable/reset-selection; migrate-npm-records | Global like Pi; `-p` selects project. No lock-based scope inference. |
| Commands scope-aware verbs | `_paths_core.default_scope`: project if **any** of skills/agents/commands/Pi extensions project locks exists in the consumer directory; otherwise global. |
| Instructions | Pointer verbs default to project; use `--scope global` (no `-g/-p`). Content `pull`/`restore` are global-only, without a scope flag. |
| MCP list/status/doctor | Project if `mcps-lock.json` exists, otherwise global. |
| MCP install/uninstall/remove | Project; use `-g` for global. MCP add/import/migrate are global-library operations; update has no scope flag and refreshes reachable locked projections. |
| Bundles install | Project if any source-backed project lock above exists, otherwise global. Explicit `--global` / `--project` overrides. |

Use explicit scope in automation. Most scope-aware verbs accept `-g/--global` and `-p/--project`; exceptions are called out above. TUI scope is its own visible selection, not an implicit CLI default.

Targets differ too:

- **Skills:** `--agents` is comma-separated; install defaults to `standard` (`.agents/skills`). `all` means detected harnesses, plus Paperclip only in an eligible company project, not every catalog entry. No-flag uninstall also includes Standard to remove its shared slot.
- **Agents:** comma-separated `--harnesses`; install defaults to Standard plus enabled adapters not covered by it at that scope. Uninstall defaults to Standard plus all enabled adapters to sweep legacy own-directory projections.
- **Commands:** comma-separated `--harnesses`; install defaults to `standard,pi,gemini-cli`; uninstall sweeps all concrete targets plus Standard. Deprecated Codex prompts are explicit and global-only.
- **Instructions:** repeatable `--harness`; omitted means all supported pointer slots, not every native reader. Uninstall has no harness selector; it removes owned pointers at that scope with whole-batch source-chain preflight.
- **MCP:** repeatable `--harness`; global defaults to Claude Code, Codex, OpenCode, Pi. Project defaults to Standard (Claude Code + Pi), Codex, OpenCode. Global Standard is refused.
- **Pi extensions:** Pi only; no harness selector.

## Skills

```text
atc skills add [SOURCE] [--source owner/repo] [--ref REF] [--slug SLUG] [--skill NAME | --path PATH] [--owned]
atc skills install [SLUG] [--source owner/repo] [--agents NAMES] [--scope global|project] [-p]
atc skills uninstall [SLUG] [--source owner/repo] [--agents NAMES] [--scope global|project] [-p]
atc skills list [-g|-p] [--agent NAME] [--json]
atc skills status [SLUGS]... [-g|-p]
atc skills check [SLUGS]... [-g|-p] [--json]
atc skills catalog subscribe URL [--ref REF]
atc skills catalog unsubscribe
atc skills catalog list [--json]
atc skills catalog add KEY
atc skills catalog enable KEY [--scope global|project] [--agents NAMES]
atc skills update [SLUGS]... [-g|-p]
atc skills push [SLUGS]... [-g|-p] [--direct]
atc skills reset SLUGS... [-g|-p] [--force]
atc skills remove [SLUGS]... [--source owner/repo] [--force]
atc skills import FILE [--latest]
atc skills doctor [SLUGS]... [-g|-p] [--no-fix] [--repair] [--repair-foreign]
```

`catalog` is optional and user-global: subscribe validates a live `catalog.json`
before saving configuration, without acquiring skills. Catalog enable defaults
to global/Standard; select project scope explicitly. Acquired skills keep working
after unsubscribe. `check` records timestamped, read-only upstream revision
observations for registered Git-backed library/scoped entries, without requiring
catalog provenance; failed checks exit
nonzero. `update` remains the explicit content-changing command. The TUI only
shows check results and commands. [Catalog behavior and format](../asset-types/skills.md#optional-shared-git-catalog).

`reset SLUG -g --force` discards local commits and tracked edits, restoring the configured commit pin, tag or latest fetched branch tip. It does not switch a pin to `main` or run `git clean`. A monorepo reset affects the **entire shared parent checkout**, including sibling skills. `status` scopes each child's clean/dirty result to its own directory, independently of read-only/owned status.

Use a positional source or `--source`, not both. Repository-wide add registers real skills including a genuine root; `--skill NAME`, an explicit source subpath, or `--path PATH` selects one child. `--path` names an exact safe repository-relative directory (including `.` for a real root) independently of its frontmatter name or custom slug; it is library-only and cannot be combined with another child selector or batch `--source`. `install --source` selects persisted children of the exact source across registered refs, whereas a TUI collection controls one source/ref group. It does not discover or autoactivate later upstream children. Remove without arguments opens an interactive selection.

Sources accept `owner/repo`, `owner/repo@ref`, subpaths, HTTPS/SSH URLs, local paths and skills.sh URLs. Combine ref+subpath using `--ref` or a GitHub `/tree/<ref>/<subpath>` URL; ambiguous `owner/repo@ref/subpath` is refused. Slash-containing refs require `--ref`. [Skill storage, ownership and update](skill-lock.md) · [Collections and legacy exposure](tui.md#skill-collections).

Doctor reports canonical/projection drift and bounded unmanaged discovery. Discovered local skills remain report-only even with `--repair`; doctor does not register them. Unrelated repairs, ordinary source registration and lock-file import are unchanged. `--no-fix` disables mutations. An externally owned global skill projection can be declared in `~/.agent-toolkit/external-skill-projections.json`:

```json
{"version": 1, "projections": [{"path": ".pi/agent/skills/example", "targetGlob": ".npm/_npx/*/node_modules/example/skills/example", "owner": "external installer"}]}
```

Paths are home-relative. Both exact link path and live resolved target must match; missing/changed targets remain findings. This registry does not add library membership. Old `general` / `universal` target tokens are not accepted; use `standard`.

## Agents

```text
atc agents add SOURCE [--slug SLUG] [--ref REF]
atc agents install SLUG [-g|-p] [--harnesses NAMES]
atc agents uninstall SLUG [-g|-p] [--harnesses NAMES]
atc agents list [-g|-p] [--json]
atc agents status|update|push [SLUGS]... [-g|-p]
atc agents reset SLUGS... [-g|-p] [--force]
atc agents remove SLUG [--force]
atc agents import FILE [--latest]
atc agents doctor [SLUGS]... [-g|-p] [--no-fix]
```

Push additionally accepts `--direct`; PR is the default. Standard is the shared `.claude/agents/<slug>.md` slot; `claude-code` normalizes to it. Covered readers vary by scope. Doctor distinguishes Standard drift, orphans, stale ownership sidecars, unmanaged files and Cursor shadows. Unmanaged Standard files are never auto-removed; a divergent sentinel-less Cursor file is report-only. Informational unmanaged/shadow findings do not fail doctor alone. See [Agents](../asset-types/agents.md).

## Commands

```text
atc commands add SOURCE [--slug SLUG] [--ref REF]
atc commands install SLUG [-g|-p] [--harnesses NAMES]
atc commands uninstall SLUG [-g|-p] [--harnesses NAMES]
atc commands list [-g|-p] [--json]
atc commands status [-g|-p]
atc commands update [SLUG] [-g|-p]
atc commands push [SLUGS]... [-g|-p] [--direct]
atc commands import [FILE] [--latest] [-g]
atc commands reset SLUG --force [-g|-p]
atc commands remove SLUG [-g|-p]
atc commands doctor [-g|-p]
```

`COMMAND.md` must be a regular file. Install projects the prompt, not adjacent support files. Standard aliases Claude Code's slot; Pi uses Markdown prompt templates and Gemini TOML commands. `list --json` reports harness metadata; doctor is read-only. `import` without FILE reads the global command lock; `-p` is rejected. [Targets and ownership safeguards](../asset-types/commands.md).

## Instructions

```text
atc instructions pull --source SOURCE --host HOST [--ref REF] [--replace] [--dry-run] [--yes]
atc instructions restore DEPLOYMENT [--replace] [--dry-run] [--yes]
atc instructions install [--scope project|global] [--harness NAME]...
atc instructions uninstall [--scope project|global]
atc instructions list [--scope project|global] [--format table|json]
atc instructions status [--scope project|global]
atc instructions doctor [--scope project|global] [--no-fix]
```

`pull`/`restore` explicitly deploy global instruction content on macOS/Linux. Older clients such as 7.3.1 need a Toolkit package update first. Pull reads one `AGENTS.<host>.md`, either at repository root (subtree export) or under `agents-instructions/` (workspace), refusing ambiguity if both exist. It fetches latest `main` by default; `--ref` is optional. No version numbers/tags are needed; Git revert/push and another pull provide shared rollback. The resolved commit is recorded for traceability. Preview first with `--dry-run`; replacement requires `--replace`, confirmation or `--yes`, and retains unique backups/provenance. Restore accepts the printed deployment ID and restores its previous bytes. Neither changes harness exposure. These content-writing commands refuse canonical symlinks; pointer verbs still support them.

Canonical is user-authored `<project>/AGENTS.md` or `~/.agent-toolkit/AGENTS.md`, possibly itself a symlink. Install never authors canonical content or prunes unrequested links. Correct manual links count as installed; real files and foreign pointers conflict. Uninstall preflights the entire requested batch against canonical's source chain. Legacy locks are ignored/preserved. Doctor adoption requires explicit confirmation; `--no-fix` is read-only. [Pointer identity, conflicts and partial retry](../asset-types/instructions.md).

## Pi extensions

```text
atc pi-extensions add SOURCE [--slug GIT_SLUG] [-g|-p]
atc pi-extensions install SLUG_OR_NPM_SOURCE [-g|-p]
atc pi-extensions uninstall SLUG_OR_NPM_SOURCE [-g|-p] [--yes] [--external]
atc pi-extensions enable|disable NPM_ID [-g|-p]
atc pi-extensions reset-selection NPM_ID [-g|-p]
atc pi-extensions migrate-npm-records [-g|-p] [--apply]
atc pi-extensions list [-g|-p] [--json]
atc pi-extensions status|update|push [SLUGS]... [-g|-p]
atc pi-extensions reset SLUGS... [-g|-p] [--force]
atc pi-extensions remove SLUG_OR_NPM_SOURCE [-g|-p] [--force] [--yes] [--external]
atc pi-extensions import FILE [--latest]
atc pi-extensions doctor [SLUGS]... [-g|-p] [--no-fix] [--repair]
```

Push also accepts `--direct`. Git refs are part of SOURCE (`@ref`), not a `--ref` option. Inventory includes Git-backed sources, loose files and native Pi/npm facts—not Toolkit npm registration. npm add/install delegates to Pi and may download/activate package resources; enable/disable changes extension filters only. npm remove/uninstall physically removes the scoped installation and declaration, with confirmation (`--yes` for automation); `--external` explicitly selects external global npm removal. `--force` remains a Git dirty-source option, not an npm confirmation bypass. These are breaking npm lifecycle changes; use disable to retain files. Native project overrides support inheritance/on/off; reset-selection removes only extension overrides. Legacy npm lock records are ignored, explicit migration backs up/prunes them, and old npm imports are skipped. Git lifecycle behavior is unchanged. Local filesystem packages declared in Pi settings are visible as `local` in the TUI, with manual reference-removal guidance and no toggle/deletion action. Doctor does not register discovered local packages, even with `--repair`. Doctor does not rewrite settings or source. [Pi extensions](../asset-types/pi-extensions.md).

## MCP servers

```text
atc mcps add [--npx PACKAGE|--uvx PACKAGE|--docker IMAGE|--url URL|--local DIR] [--slug SLUG]
atc mcps migrate
atc mcps import FILE [--latest]
atc mcps install SLUG [-g|-p] [--harness NAME]... [--force]
atc mcps uninstall SLUG [-g|-p] [--harness NAME]... [--force]
atc mcps remove SLUG [-g|-p] [--force]
atc mcps update SLUG [--bearer-token-env NAME]
atc mcps list [-g|-p]
atc mcps status [SLUGS]... [-g|-p]
atc mcps doctor [-g|-p]
```

Add requires one source selector; `--local` needs `--command`. Other add options: repeatable `--env NAME`, `--description`, `--command`, `--bearer-token-env NAME` (URL only). Only variable **names**, not credential values, belong in these fields. Bearer authentication projects to Pi only; incompatible targets refuse rather than drop authentication.

`mcps-library.json` is global library authority; config/sidecar pairs are materializations. `migrate` explicitly adopts safe legacy files, never via implicit add/update backfill. Locks record projections, not library membership. Remove retracts recorded projections but **retains the library**. Doctor is read-only. `--force` bypasses the running-Claude guard, not arbitrary ownership/authentication checks. [MCP paths and adapter limits](../asset-types/mcp.md).

## Bundles

```text
atc bundles install MANIFEST [--global|--project]
atc bundles validate MANIFEST
```

Local JSON manifests support skills, agents and Pi extensions only. MCP is reserved but rejected before install; Instructions and Commands are unsupported. Validate checks structure/options, not source/ref reachability. Install attempts rollback of newly added members on failure; cleanup errors are reported and pre-existing members are not rolled back. It is not a universal filesystem transaction. [Schema and recovery limits](bundles.md).

## Moving to a new machine (cross-machine sync)

Copy the global source-backed locks or MCP manifest to the destination, then run the matching import:

```bash
atc skills import ~/sync/skills-lock.json
atc agents import ~/sync/agents-lock.json
atc commands import ~/sync/commands-lock.json
atc pi-extensions import ~/sync/pi-extensions-lock.json
atc mcps import ~/sync/mcps-library.json
```

Imports are additive and skip existing slugs; they do **not** install harness projections. Retired Pi npm records are skipped without recreating a Toolkit catalogue or installing packages; carry native Pi configuration separately and use explicit Pi/npm installation commands. Install separately with explicit scope/targets. Project-scoped state and local-only commits/uncommitted edits are not transported. Source-backed imports use recorded upstream SHAs by default (`--latest` selects ref HEAD); Commands currently attempts the recorded SHA but may fall back to the cloned ref if that checkout fails. Shared parent constraints can refuse incompatible pins. Per-entry failures are reported while other entries continue. MCP import skips local entries and quarantines secrets; `--latest` re-resolves versioned specs. Instructions has no import: move/version your canonical content yourself.

## Pre-v2 surface

The old top-level `check`, `diff`, `doctor`, `fix`, `ingest`, `inventory`, `link`, `list`, `migrate-skills`, `new`, `pi`, `unlink` commands were removed. Per-kind commands with some of these names are different APIs. The frozen v1 interface is available separately:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit
```

## Terminal UI

`att` (or `agent-toolkit-tui`) opens the TUI in its launch directory. Its shell
commands are `att update [--check] [--main]` and `att completion ...`; `--help`
and `--version`/`-V` exit without opening the interface. It does not accept the
CLI's `--project DIRECTORY` option. [TUI controls](tui.md) ·
[Preferences](tui-settings.md) · [Lock formats](lock-files.md).
