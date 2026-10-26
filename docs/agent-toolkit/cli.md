# CLI reference

`agent-toolkit-cli [--project DIRECTORY] GROUP VERB ...` targets a consumer directory (default: current directory). Top-level `--project DIRECTORY` selects the directory; a verb's `-p/--project` selects **scope**, not a path. `--version` / `-V` prints the installed package version.

## Toolkit package updates

`atc` is a packaged executable equivalent to `agent-toolkit-cli`; `att` opens
`agent-toolkit-tui`. Both long names remain supported. No shell configuration is
required (an existing shell alias can still shadow an executable).

```bash
atc update --check          # Force a fresh stable-release check; no changes
atc update                 # Update both CLI and TUI to the latest stable release
att update                 # Same updater, without launching the TUI
atc update --main --check   # Compare the newest main commit with installed provenance
atc update --main           # Explicitly build the newest canonical main commit
```

`agent-toolkit-cli update` and `agent-toolkit-tui update` accept the same options.
This top-level command updates the **Toolkit package**, not library assets or
harness exposure. Stable checks use the canonical repository’s latest published,
non-prerelease GitHub release. Stable updates do not downgrade an equal/newer
installed version. `--main` compares commit SHAs, because development commits can
share a version number; unknown provenance is reported as unknown, not current.

### Automatic notices

Interactive CLI startup checks only when both stdout and stderr are terminals;
notices go to stderr. JSON/explicit formats (`--json`, `--format`), help/version, completion and explicit
update invocations suppress automatic checks. The TUI checks in a background
worker after mounting; a notification shows the version change and `atc update`.
Headless TUI runs never check. A CLI cache miss/stale entry uses a one-second
network socket timeout; the TUI uses the same checker without blocking its UI.

Results are cached for **six hours** in
`${XDG_CACHE_HOME:-~/.cache}/agent-toolkit/update.json`. Failed checks back off
for **15 minutes**, retaining any known release. Offline/rate-limit failures are
silent during automatic checks and do not prevent normal use. Explicit checks
always refresh, report failures with a nonzero exit status, and work even when
`AGENT_TOOLKIT_NO_UPDATE_CHECK=1` disables automatic checks. GitHub receives only
public repository metadata requests, not local asset information. No automatic
update or checkout modification occurs.

### Update safety and provenance

Self-update requires Git, uv, and a **non-editable `uv tool` installation**.
Other environments are refused with guidance; `update --check` works without
these requirements. Update editable development checkouts with their normal Git
workflow and `uv sync`, and other installations with their original manager.

The updater resolves the release tag (or explicit `main`) to a canonical commit,
fetches exactly that SHA into a temporary checkout, verifies it, and builds a
wheel using `uv build`. A stable wheel must match the selected release version.
Only then does it invoke `uv tool install` to replace the package. Build/fetch
failures leave the existing tool untouched; installation errors are reported,
not hidden. There is no automatic rollback of a failed package-manager operation.

The built wheel and `receipt.json` remain under
`${XDG_STATE_HOME:-~/.local/state}/agent-toolkit/updates/`, recording the canonical
repository, ref, full commit, wheel SHA-256 and build time. This is a **locally
built artifact**, not a claim that its hash matches a published release wheel.
Keep the wheel/receipt for provenance; `--main` checks only trust a receipt bound
to the installed wheel’s URL and hash. When uv omits a local archive hash, the
checker verifies the retained wheel hash and compares its contents with the
installed package (excluding installer-rewritten `RECORD`). Concurrent updates are refused. After a
hard interruption, the error identifies the stale `.update-lock` directory;
remove it only after confirming no updater is running.

Restart any running TUI after updating. Existing managed assets, configuration
and operator checkouts are not migrated or changed by package updates.

## Shell completion

Toolkit uses Click’s dynamic shell completion for command names, nested verbs,
flags, declared choice values (such as scopes/harnesses), and path arguments.
It supports `atc`, `att`, `agent-toolkit-cli`, and `agent-toolkit-tui`. Asset slug
and remote repository discovery are not completion sources; pressing TAB never
fetches Git repositories, checks for package updates, or authors asset state.

Like Worktrunk’s `wt config shell install`, an explicit setup command adds a
small, marked block to your shell startup file:

```bash
atc completion install --shell zsh
source ~/.zshrc
# Try: atc sk<TAB>, atc skills in<TAB>, atc update --<TAB>
# Or:  att up<TAB>
```

Omit `--shell` to detect it from `$SHELL`. Supported shells: **Zsh**, **Bash
4.4+**, and **Fish**. Zsh setup initializes `compinit` only if needed and honors
`$ZDOTDIR/.zshrc` (otherwise `~/.zshrc`). Bash uses `~/.bashrc`; login Bash shells
must source that file from `~/.bash_profile`. Fish uses
`${XDG_CONFIG_HOME:-~/.config}/fish/conf.d/agent-toolkit-completion.fish`.
Use `--rc-file PATH` with install/uninstall for another configuration location.

Setup is idempotent and preserves unrelated text, existing file permissions,
and symlinked dotfile layouts. It does not add aliases or replace `wt` setup.
Incomplete/duplicated Toolkit markers cause a refusal rather than a guessed
edit. Shell files change **only** when you explicitly run install/uninstall.

```bash
atc completion uninstall --shell zsh  # Remove only Toolkit’s managed block
atc completion init zsh              # Print shell code; no file changes
```

Open a new shell after uninstalling to clear already-loaded functions. For
manual Zsh setup, initialize `compinit`, then evaluate
`eval "$(atc completion init zsh)"`; Bash uses
`eval "$(atc completion init bash)"`, and Fish uses
`atc completion init fish | source`. Do not add both manual and managed setup.
`att completion ...` also provides the same utility. Completions query the
current executable on each TAB, so new commands appear after a package update
without regenerating a static command list.

## Groups and verbs

Plural names are canonical; singular aliases remain accepted, including `instruction` → `instructions`.

| Group | Singular alias | Shipped verbs |
|---|---|---|
| `skills` | `skill` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `agents` | `agent` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `commands` | `command` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `instructions` | `instruction` | install, uninstall, list, status, doctor |
| `pi-extensions` | `pi-extension` | add, install, uninstall, enable, disable, reset-selection, migrate-npm-records, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `mcps` | `mcp` | add, install, uninstall, list, status, update, remove, import, migrate, doctor |
| `bundles` | `bundle` | install, validate |

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
| Instructions | Project; use `--scope global` (no `-g/-p`). |
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
agent-toolkit-cli skills add [SOURCE] [--source owner/repo] [--ref REF] [--slug SLUG] [--skill NAME | --path PATH] [--owned]
agent-toolkit-cli skills install [SLUG] [--source owner/repo] [--agents NAMES] [--scope global|project] [-p]
agent-toolkit-cli skills uninstall [SLUG] [--source owner/repo] [--agents NAMES] [--scope global|project] [-p]
agent-toolkit-cli skills list [-g|-p] [--agent NAME] [--json]
agent-toolkit-cli skills status [SLUGS]... [-g|-p]
agent-toolkit-cli skills check [SLUGS]... [-g|-p] [--json]
agent-toolkit-cli skills catalog subscribe URL [--ref REF]
agent-toolkit-cli skills catalog unsubscribe
agent-toolkit-cli skills catalog list [--json]
agent-toolkit-cli skills catalog add KEY
agent-toolkit-cli skills catalog enable KEY [--scope global|project] [--agents NAMES]
agent-toolkit-cli skills update [SLUGS]... [-g|-p]
agent-toolkit-cli skills push [SLUGS]... [-g|-p] [--direct]
agent-toolkit-cli skills reset SLUGS... [-g|-p] [--force]
agent-toolkit-cli skills remove [SLUGS]... [--source owner/repo] [--force]
agent-toolkit-cli skills import FILE [--latest]
agent-toolkit-cli skills doctor [SLUGS]... [-g|-p] [--no-fix] [--repair] [--repair-foreign]
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
agent-toolkit-cli agents add SOURCE [--slug SLUG] [--ref REF]
agent-toolkit-cli agents install SLUG [-g|-p] [--harnesses NAMES]
agent-toolkit-cli agents uninstall SLUG [-g|-p] [--harnesses NAMES]
agent-toolkit-cli agents list [-g|-p] [--json]
agent-toolkit-cli agents status|update|push [SLUGS]... [-g|-p]
agent-toolkit-cli agents reset SLUGS... [-g|-p] [--force]
agent-toolkit-cli agents remove SLUG [--force]
agent-toolkit-cli agents import FILE [--latest]
agent-toolkit-cli agents doctor [SLUGS]... [-g|-p] [--no-fix]
```

Push additionally accepts `--direct`; PR is the default. Standard is the shared `.claude/agents/<slug>.md` slot; `claude-code` normalizes to it. Covered readers vary by scope. Doctor distinguishes Standard drift, orphans, stale ownership sidecars, unmanaged files and Cursor shadows. Unmanaged Standard files are never auto-removed; a divergent sentinel-less Cursor file is report-only. Informational unmanaged/shadow findings do not fail doctor alone. See [Agents](../asset-types/agents.md).

## Commands

```text
agent-toolkit-cli commands add SOURCE [--slug SLUG] [--ref REF]
agent-toolkit-cli commands install SLUG [-g|-p] [--harnesses NAMES]
agent-toolkit-cli commands uninstall SLUG [-g|-p] [--harnesses NAMES]
agent-toolkit-cli commands list [-g|-p] [--json]
agent-toolkit-cli commands status [-g|-p]
agent-toolkit-cli commands update [SLUG] [-g|-p]
agent-toolkit-cli commands push [SLUGS]... [-g|-p] [--direct]
agent-toolkit-cli commands import [FILE] [--latest] [-g]
agent-toolkit-cli commands reset SLUG --force [-g|-p]
agent-toolkit-cli commands remove SLUG [-g|-p]
agent-toolkit-cli commands doctor [-g|-p]
```

`COMMAND.md` must be a regular file. Install projects the prompt, not adjacent support files. Standard aliases Claude Code's slot; Pi uses Markdown prompt templates and Gemini TOML commands. `list --json` reports harness metadata; doctor is read-only. `import` without FILE reads the global command lock; `-p` is rejected. [Targets and ownership safeguards](../asset-types/commands.md).

## Instructions

```text
agent-toolkit-cli instructions install [--scope project|global] [--harness NAME]...
agent-toolkit-cli instructions uninstall [--scope project|global]
agent-toolkit-cli instructions list [--scope project|global] [--format table|json]
agent-toolkit-cli instructions status [--scope project|global]
agent-toolkit-cli instructions doctor [--scope project|global] [--no-fix]
```

Canonical is user-authored `<project>/AGENTS.md` or `~/.agent-toolkit/AGENTS.md`, possibly itself a symlink. Install never authors canonical content or prunes unrequested links. Correct manual links count as installed; real files and foreign pointers conflict. Uninstall preflights the entire requested batch against canonical's source chain. Legacy locks are ignored/preserved. Doctor adoption requires explicit confirmation; `--no-fix` is read-only. [Pointer identity, conflicts and partial retry](../asset-types/instructions.md).

## Pi extensions

```text
agent-toolkit-cli pi-extensions add SOURCE [--slug GIT_SLUG] [-g|-p]
agent-toolkit-cli pi-extensions install SLUG_OR_NPM_SOURCE [-g|-p]
agent-toolkit-cli pi-extensions uninstall SLUG_OR_NPM_SOURCE [-g|-p] [--yes] [--external]
agent-toolkit-cli pi-extensions enable|disable NPM_ID [-g|-p]
agent-toolkit-cli pi-extensions reset-selection NPM_ID [-g|-p]
agent-toolkit-cli pi-extensions migrate-npm-records [-g|-p] [--apply]
agent-toolkit-cli pi-extensions list [-g|-p] [--json]
agent-toolkit-cli pi-extensions status|update|push [SLUGS]... [-g|-p]
agent-toolkit-cli pi-extensions reset SLUGS... [-g|-p] [--force]
agent-toolkit-cli pi-extensions remove SLUG_OR_NPM_SOURCE [-g|-p] [--force] [--yes] [--external]
agent-toolkit-cli pi-extensions import FILE [--latest]
agent-toolkit-cli pi-extensions doctor [SLUGS]... [-g|-p] [--no-fix] [--repair]
```

Push also accepts `--direct`. Git refs are part of SOURCE (`@ref`), not a `--ref` option. Inventory includes Git-backed sources, loose files and native Pi/npm facts—not Toolkit npm registration. npm add/install delegates to Pi and may download/activate package resources; enable/disable changes extension filters only. npm remove/uninstall physically removes the scoped installation and declaration, with confirmation (`--yes` for automation); `--external` explicitly selects external global npm removal. `--force` remains a Git dirty-source option, not an npm confirmation bypass. These are breaking npm lifecycle changes; use disable to retain files. Native project overrides support inheritance/on/off; reset-selection removes only extension overrides. Legacy npm lock records are ignored, explicit migration backs up/prunes them, and old npm imports are skipped. Git lifecycle behavior is unchanged. Local filesystem packages declared in Pi settings are visible as `local` in the TUI, with manual reference-removal guidance and no toggle/deletion action. Doctor does not register discovered local packages, even with `--repair`. Doctor does not rewrite settings or source. [Pi extensions](../asset-types/pi-extensions.md).

## MCP servers

```text
agent-toolkit-cli mcps add [--npx PACKAGE|--uvx PACKAGE|--docker IMAGE|--url URL|--local DIR] [--slug SLUG]
agent-toolkit-cli mcps migrate
agent-toolkit-cli mcps import FILE [--latest]
agent-toolkit-cli mcps install SLUG [-g|-p] [--harness NAME]... [--force]
agent-toolkit-cli mcps uninstall SLUG [-g|-p] [--harness NAME]... [--force]
agent-toolkit-cli mcps remove SLUG [-g|-p] [--force]
agent-toolkit-cli mcps update SLUG [--bearer-token-env NAME]
agent-toolkit-cli mcps list [-g|-p]
agent-toolkit-cli mcps status [SLUGS]... [-g|-p]
agent-toolkit-cli mcps doctor [-g|-p]
```

Add requires one source selector; `--local` needs `--command`. Other add options: repeatable `--env NAME`, `--description`, `--command`, `--bearer-token-env NAME` (URL only). Only variable **names**, not credential values, belong in these fields. Bearer authentication projects to Pi only; incompatible targets refuse rather than drop authentication.

`mcps-library.json` is global library authority; config/sidecar pairs are materializations. `migrate` explicitly adopts safe legacy files, never via implicit add/update backfill. Locks record projections, not library membership. Remove retracts recorded projections but **retains the library**. Doctor is read-only. `--force` bypasses the running-Claude guard, not arbitrary ownership/authentication checks. [MCP paths and adapter limits](../asset-types/mcp.md).

## Bundles

```text
agent-toolkit-cli bundles install MANIFEST [--global|--project]
agent-toolkit-cli bundles validate MANIFEST
```

Local JSON manifests support skills, agents and Pi extensions only. MCP is reserved but rejected before install; Instructions and Commands are unsupported. Validate checks structure/options, not source/ref reachability. Install attempts rollback of newly added members on failure; cleanup errors are reported and pre-existing members are not rolled back. It is not a universal filesystem transaction. [Schema and recovery limits](bundles.md).

## Moving to a new machine (cross-machine sync)

Copy the global source-backed locks or MCP manifest to the destination, then run the matching import:

```bash
agent-toolkit-cli skills import ~/sync/skills-lock.json
agent-toolkit-cli agents import ~/sync/agents-lock.json
agent-toolkit-cli commands import ~/sync/commands-lock.json
agent-toolkit-cli pi-extensions import ~/sync/pi-extensions-lock.json
agent-toolkit-cli mcps import ~/sync/mcps-library.json
```

Imports are additive and skip existing slugs; they do **not** install harness projections. Retired Pi npm records are skipped without recreating a Toolkit catalogue or installing packages; carry native Pi configuration separately and use explicit Pi/npm installation commands. Install separately with explicit scope/targets. Project-scoped state and local-only commits/uncommitted edits are not transported. Source-backed imports use recorded upstream SHAs by default (`--latest` selects ref HEAD); Commands currently attempts the recorded SHA but may fall back to the cloned ref if that checkout fails. Shared parent constraints can refuse incompatible pins. Per-entry failures are reported while other entries continue. MCP import skips local entries and quarantines secrets; `--latest` re-resolves versioned specs. Instructions has no import: move/version your canonical content yourself.

## Pre-v2 surface

The old top-level `check`, `diff`, `doctor`, `fix`, `ingest`, `inventory`, `link`, `list`, `migrate-skills`, `new`, `pi`, `unlink` commands were removed. Per-kind commands with some of these names are different APIs. The frozen v1 interface is available separately:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit
```

## Terminal UI

`agent-toolkit-tui` is a separate binary installed with the package. [TUI controls](tui.md) · [Preferences](tui-settings.md) · [Lock formats](lock-files.md).
