# CLI reference

`agent-toolkit-cli [--project DIRECTORY] GROUP VERB ...` targets a consumer directory (default: current directory). Top-level `--project DIRECTORY` selects the directory; a verb's `-p/--project` selects **scope**, not a path. `--version` / `-V` prints the installed package version.

## Groups and verbs

Plural names are canonical; singular aliases remain accepted, including `instruction` → `instructions`.

| Group | Singular alias | Shipped verbs |
|---|---|---|
| `skills` | `skill` | add, install, uninstall, list, status, check, update, push, reset, remove, import, doctor, catalog |
| `agents` | `agent` | add, install, uninstall, list, status, update, push, reset, remove, import, doctor |
| `commands` | `command` | add, install, uninstall, list, status, update, push, reset, remove, import, doctor |
| `instructions` | `instruction` | install, uninstall, list, status, doctor |
| `pi-extensions` | `pi-extension` | add, install, uninstall, enable, disable, reset-selection, migrate-npm-records, list, status, update, push, reset, remove, import, doctor |
| `mcps` | `mcp` | add, install, uninstall, list, status, update, remove, import, migrate, doctor |
| `bundles` | `bundle` | install, validate |

Each group supports `list` as `ls` where list exists, **except Instructions**. Skills also accepts `rm` for remove. Bundles is a utility, not another asset kind. Flags and argument cardinality are deliberately nonuniform; use `GROUP VERB --help` for the exact surface.

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
