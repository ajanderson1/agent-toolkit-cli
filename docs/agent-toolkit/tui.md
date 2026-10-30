# TUI reference

**`att`** (equivalently `agent-toolkit-tui`) is the interactive [Textual](https://textual.textualize.io/)
cockpit over the same surface the [CLI](cli.md) drives. It reads the lock files
and filesystem directly (Instructions uses filesystem pointers only) and applies your edits by calling the shipped CLI
facades in-process. Inventories are snapshots, not a guarantee against later
filesystem changes or partially failed operations; reload actual state after errors.

## Launch and shell utilities

[Install the package](installation.md) to get both applications and all four
short/long entry points. No shell alias is needed. Launch in the consumer directory:

```bash
cd /path/to/project
att
```

The TUI uses its launch directory and visible scope selector. It does **not**
accept the CLI's `--project DIRECTORY` option. These separate shell invocations
exit without opening the interface:

| Invocation | Effect |
|---|---|
| `att --help` | Launcher help and available shell utilities. |
| `att --version` or `att -V` | Installed package version. |
| `att update --check` | Fresh stable-release check, without package replacement. |
| `att update` | Update both CLI and TUI in a supported non-editable uv tool environment. |
| `att update --main --check` / `att update --main` | Explicit development-commit check/update. |
| `att completion ...` | The same completion utility as `atc completion ...`. |

[Shell completion](shell-completion.md) covers these commands and does not
launch the TUI when TAB is pressed. Completion setup is explicit; package
installation itself does not edit shell files.

## Startup update notification

After mounting, an interactive TUI checks stable release metadata in a background
worker. A newer version produces a **Toolkit update** notification, normally for
15 seconds, with the installed/latest versions and `Run atc update to update`.
The current version remains in the header. Checks are cached for six hours;
network failures silently back off for 15 minutes. They never replace the package
or run upstream asset updates. Headless sessions do not check.

Set `AGENT_TOOLKIT_NO_UPDATE_CHECK=1` in the environment to disable automatic
checks; this is not a TUI preference/command-palette setting. An explicit shell
`att update --check` still refreshes. An absent notification is not proof a fresh
network check succeeded. [Cache, privacy, channel and failure rules](updates.md).

Package replacement is a **shell command**, not a grid/Apply action. Save/apply
only intended asset drafts before closing, run the update, and restart any
already-running TUI. Updating the package does not apply, migrate or preserve
in-memory drafts across a restart; its processes do not hot-reload.

![Current TUI: expanded skill collection and queued changes in an isolated fixture](../assets/screenshots/tui-overview.png)

Seven real skills, one collection, mixed parent selection, two pending changes,
and global scope. Captured from the current source with disposable local Git/HOME;
[reproduction and visual verdict](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/docs/assets/screenshots/README.md).

## Layout

```text
Header
├─ Asset-type sidebar        Instructions · Commands · Skills · Agents · MCPs · Pi Extensions
└─ Content
   ├─ Content header + Scope toggle   (project ⇄ global)
   └─ One grid per asset type         (swapped as you change asset type)
Repository path
Status bar
Pending line
Footer (key hints)
```

- **Asset-type sidebar** — pick which [asset type](../glossary.md#asset-type)
  you're managing: Instructions, Commands, Skills, Agents, MCPs, or Pi Extensions.
  Labels have no number prefixes or separators. With the sidebar focused, keys
  **1–6** still select these types in order.
- **Grid** — one row per asset, columns vary by type (slug, source, ref, state,
  per-harness cells). The Source column fits its displayed values when terminal
  space permits. Press ++i++ for the selected asset; click a glyphed column
  header for column-level information.
- **Info panes** — asset and column Info lead with **At a glance** facts and then
  use labelled Description, Source & location, Availability, Update status and
  Available actions sections when those details apply. Long paths, refs and
  commands retain their full value in Technical details or a distinct command
  line after a compact summary. Warnings and manual file-removal guidance are
  separated from ordinary availability text. Use ++up++/++down++ or
  ++pageup++/++pagedown++ to scroll; the pane footer repeats these keys and its
  close keys (++esc++, ++q++ for assets, or ++i++).
- **Repository path** — the row above the status bar shows a bold **REPO:**
  label, a regular-weight parent path, and a bold final displayed directory.
  It shows the launch directory (including a repository subdirectory), not a
  substituted Git root. Spaces and markup characters remain literal. A warning
  triangle and red text still indicate a directory that is not itself a Git
  root; linked worktree roots do not warn. Filesystem root is shown once, in
  bold. Narrow terminals retain the existing single-row clipping behavior.
- **Scope toggle** — flips the whole view between **project** and **global**
  [scope](../glossary.md#scope). The grid re-reads at the new scope; pending
  edits queued in the other scope are kept, not discarded.

### Interaction responsiveness

Checkbox changes update changed table cells in place when the row and column
structure is unchanged. State badges, sources, global indicators and pending
markers are still recomputed; this does not cache inventory across refreshes or
delay freshness checks. Filtering and structural changes rebuild the table as needed.
Skill collection membership is indexed per view instead of scanning the entire
inventory for every collection cell. These changes preserve the existing
controls, Info panels, cursor and viewport behavior.

Skill discovery reuses the validated project lock, canonical paths, origin checks
and repository status within each scan. A clean shared checkout does not need a
separate Git status process for each child; dirty checkouts retain path-local
checks so sibling or root changes do not make every child dirty. Later scans
read fresh records and local state, and Apply keeps its existing fresh ownership
checks. Refresh avoids scanning the active kind twice.

Inventory reads and Apply still run synchronously, so slow filesystem, Git or
native Pi/npm operations can still delay navigation or refresh. Background
inventory loading is not implemented by these optimizations.

For a reproducible discovery benchmark from a development checkout, run
`uv run python scripts/benchmark_tui_inventory.py --skills 60 --samples 3`.
It creates a disposable HOME, library, local Git source and project; fixture
creation is excluded from timings. It reports global/project scan medians, Git
process counts and project-lock reads without inspecting your assets. The
renderer-only benchmark remains `scripts/benchmark_tui.py`.

### Library, catalogue, local and npm origins { #library-local-and-npm-origins }

Skills and Agents prefix the existing Source column with `library` or `local`;
Pi Extensions uses its existing Origin column. Git-change and health badges
(such as dirty, missing or drift) remain separate from origin.

| Origin | Meaning and controls |
|---|---|
| `library` | Toolkit-managed backing; central by default, with recorded private backing retained. Disable removes the connection, not the source. |
| `catalog` | Advertised, unacquired offer. Git offers can queue explicit acquisition/exposure; npm offers provide an explicit confirmed installation command instead. Browsing does not acquire either. |
| `local` | Existing files used in place, outside Toolkit library management. Skills/Agents stay outside toggle queues. Loose Pi extensions have settings-only Enable/Disable controls; local filesystem packages remain read-only. No TUI deletion, moving or registration. |
| `npm` | Native Pi/npm inventory, without Toolkit registration. Settings-only Enable/Disable works for native packages regardless of installer; Info separates installed files, selected version, scope policy and removal. |

Press ++i++ for the actual source path and linking/update behavior. For local
files, Info gives the exact manual removal command and warns when it
**permanently deletes files**. Removing a symlink keeps its target; remove only
the selected child, never a shared parent checkout. For a local package in Pi
settings, remove its string or structured `packages[]` reference in the shown
settings file; this does not delete package contents.

For loose Pi extensions, **Enabled globally** and **Enabled for this project**
follow native discovery and `extensions[]` selectors: existing resources are
enabled by default; project state includes global inheritance. **Space** queues
Enable/Disable in the selected scope; **Ctrl+S** writes exact selectors without
changing or registering source files. A mixed multi-entry directory shows **◐**;
Space queues Enable for all its entrypoints, listed in Info. Failed changes stay
pending, while successful changes clear. Refresh preserves loose-local and native npm
Pi intents and their original targets; **Ctrl+Z** discards them.

For npm packages, enabled follows native package resource filters and scope
precedence, not reference presence. Project scope inherits global selection unless
an explicit override or project installation replaces it. **R → Ctrl+S** resets
extension policy; for a global package's project delta this restores inheritance,
**not force-on**. If global policy is disabled, inheritance remains disabled.

In the normal project grid, npm cells label **inherit** (follow global), **on**
(explicit enable), or **block/off** (explicit disable); **policy** marks a mixed
explicit selection. Pending cells show the intended policy, and guidance below
the grid explains **Space** versus **R**. Unchecking an inherited package queues
a **persistent project block**, not removal of a duplicate/local selection.
Checking a blocked package instead queues explicit on; use **R** to follow global
policy again. For a separate project installation, R resets its own filter.

**Ctrl+S** requires review before applying any native npm project disable,
including an off policy replacing a prior override. The review lists every
affected npm package, the target project and `.pi/settings.json`, the persistent
consequence, and the inheritance recovery action. It appears even from another
asset tab or scope, after refresh, or if a drafted package is no longer visible.
A pending-project-block reminder remains in the shared footer. **Cancel** is
focused by default; Enter or Escape there retains every draft and writes nothing.
Repeated Ctrl+S does not confirm. Explicit **Apply all changes** saves the entire
cross-kind/cross-scope batch, not only the blocks. **Ctrl+Z** after cancelling
discards all drafts; it does not undo previously applied policies. Freshness
checks still reject changed native settings instead of overwriting them.

Mixed packages show **◐** and a separate mixed count. Missing/repair-needed or
ambiguous declarations are visible rather than falsely reported as enabled.
Local filesystem packages remain read-only.
Package-selected resources do not acquire duplicate loose controls. A loose row
can be package-controlled in one scope and configurable in the other; Info
identifies that boundary.
Library rows show **Linked** for their symlink connections and are counted
separately in the status bar. None of these states observes a running Pi session.

npm Enable/Disable retains the declaration and changes only extension filters;
package files and bundled resource policies remain intact. Enabling raw, previously
unconfigured files activates extensions only. A missing scope installation requires
explicit install/repair, never an automatic download from Space or Refresh.
Info gives scope- and origin-specific removal guidance through the CLI, with
confirmation for physical deletion and an explicit flag for external npm installs.
There is no second Toolkit unregister step. Another scope, a retained override or
global fallback can legitimately keep the row visible after removal. Updates use
Pi package handling, not Toolkit Git update. Running Pi sessions are unchanged.
See [native npm lifecycle and compatibility changes](../asset-types/pi-extensions.md#native-npm-packages).

Skill, agent, and command grids retain their existing lock/filesystem inventory.
Registered multi-skill sources group real children into collections; discovery
itself is observational, not incorporation. A scope-only locked asset may still
show `unlisted`; it is not a discovered local file and keeps its existing
controls. Proven project children derived from a retained library collection
are managed even without individual global records. Skill/Pi-extension doctor
does not register discovered local assets, even with `--repair`. Ordinary source
registration, lock-file import and unrelated repairs are unchanged.

## Key bindings

| Key | Action | Notes |
|---|---|---|
| ++ctrl+s++ | **Apply** | Run pending edits across all asset types through the CLI facade. |
| ++ctrl+d++ | **Diff** | Preview the pending queue (`N would-link, M would-unlink`) across all asset types without applying. |
| ++ctrl+r++ | **Refresh** | Re-read the active inventory; keep native npm/loose-local Pi drafts and targets, otherwise discard the active grid's drafts. Other kinds' queues survive. |
| ++r++ | **Reset npm policy** | In the Pi grid, queue reset of this scope's extension filter; Ctrl+S applies. An inherited package returns to global policy; owned installations remain. |
| ++ctrl+z++ | **Revert** | Clear the pending queue across all asset types — both scopes. |
| ++slash++ | **Filter** | Focus the fuzzy filter box over the grid. Escape clears it; Alt+Backspace deletes the preceding word. |
| ++esc++ | **Return to filter** | From the list or sidebar, focus the active grid's text search without clearing it. When search is focused, clear it; in dialogs, close the dialog instead. |
| ++ctrl+g++ | **Scope toggle** | Switch project ⇄ global. |
| ++ctrl+p++ | **Command palette** | Choose **Theme** or **Main harnesses** to customize themes or standalone columns. |
| ++i++ | **Info** | Open information for the selected asset, regardless of column. |
| ++q++ | **Quit** | Prompts to confirm if you have unapplied pending edits. |

Press ++space++ to toggle a cell, ++a++ for a column, and ++ctrl+w++ to focus the sidebar. Number shortcuts apply only when the sidebar has focus. Filters match asset identity; they do not narrow a collection parent's membership.

## Theme and Main Harness Preferences

Open ++ctrl+p++ and choose **Theme** or **Main harnesses**.

- **Theme** opens Textual's theme chooser; selecting a theme persists it to
  `tui-settings.json` and updates the app live.
- **Main harnesses** lists the compatibility harness catalog (not subscribed asset offers); selecting one toggles its
  presence as a standalone column across all supported asset grids. If unapplied
  pending edits are queued, a confirmation prompt asks before discarding them.

A harness preference hides or shows only standalone columns. Where an asset type
has Standard coverage, the preference does not change that coverage. For
Instructions, there is no Standard column: each Settings-selected harness with a
supported pointer at the active scope gets its own checkbox column.

See [TUI settings schema](tui-settings.md) for the JSON fields, environment
override, failure handling, and the explicit CLI boundary.

## Skill collections

Multi-skill repositories appear as an expandable **collection** with short child names. The header counts real skills and collections, not extra parent rows. Acquired children's clean/dirty badges inspect only their own directories. A parent with known local Git backing reports repository-wide clean/dirty state, including root files and filter-hidden children; advertisement-only parents retain the `collection` label without probing asset repositories. Clean describes uncommitted Git changes, not whether upstream has advanced. Collections start **collapsed**; newly discovered collections also start collapsed, while refreshes preserve your existing expand/collapse choices. In the first column, **Right** expands a collapsed parent without moving the cursor; press **Right again** to move to the second column. This is two successive presses, not a timed double-tap. Click the parent name (or press Space/Enter there) to toggle expansion; **Left** from the first column collapses the selected parent or its selected child’s parent. Filtering temporarily reveals matching children, and navigating directly to a child expands its collection. Info retains full source/ref/path identity.

Each available parent cell summarizes effective selection: unchecked = none, checked = all, **cyan `−` = mixed**. A mixed parent selects all when toggled. Child cells remain independent. The **yellow `-` on a child means pending removal**, not mixed selection. Parent actions include every member, even collapsed or filter-hidden children, and stay within that source/ref, harness and scope. A child filter keeps the parent visible for context. Column-wide toggles visit children once.

Catalogue-only and acquired children share these collection controls when their
normalized Git repository and configured ref match. Existing library rows retain
their identity and local content; advertisement expansion never acquires anything.
Apply acquires only selected missing children, then projects the desired selection
for the collection/scope across its requested harnesses in one transaction. A failed
child prevents exposure changes for that unit, but safe library acquisitions remain.
Failed intents retain their original identities for retry/Revert. Independent
collections can still succeed. Refreshes cannot silently broaden a queued All to
newly advertised children, and local-only controls do not need catalogue access.

Linked/broken counts reflect actual real-child payload health, not just link presence; pending controls represent desired selection. A missing referenced `SKILL.md` is unhealthy, and Apply refuses it instead of creating a false clean state.

Legacy whole-repo exposure is recognized without writing. The first selection-changing Apply targeting it replaces the owned wrapper with the complete desired set of child links, preserving active checkout contents and history. This happens inside normal Apply: there is no conversion button, setup step or extra confirmation. Read/refresh, filters, expansion, toggles, Revert, no-op Apply and unrelated Apply do not reconcile assets. Other harnesses/scopes remain unchanged. A real root skill can make independent nested isolation uncertain; unsupported root-on/nested-off selections fail before writes rather than pretending a nested skill is disabled.

Conflicts leave failed edits queued. A collection failure restores only its affected links/records against fresh locks, preserving unrelated work; failed recovery stays prominent with the remaining ownership conflict. Correct the conflict and retry, or Revert the queued request. Referenced backing checkouts remain preserved even after the final fake wrapper record is retired. A matching library-only rootless container does not reappear as a broken project skill after Apply, Refresh or restart. This presentation identity is separate from authority to mutate the active scope. Real missing child documents, foreign projections and distinct-copy ambiguity remain visible. If an unregistered wrapper projection still exists—even pointing to the retained backing—it remains a visible exposure warning and blocks unsafe collection changes; no library record authorizes silently retiring it.

## Shared catalogue rows

Skills, Agents, Commands and Pi extensions share one live Git catalogue snapshot.
A persistent **single-line status at the bottom right** shows the loaded catalogue
release, such as `Catalogue: v1.1.0`, without a commit ID or a success toast.
Release numbers come from stable Git version tags at the exact fetched commit,
not the manifest schema number or an older release. Without a verified tag the
label reads `Catalogue: unversioned`. During refresh it reads `refreshing…`;
failed reads show `unavailable`, and unsubscribing shows `not subscribed`.
The status stays visible across tabs and pending-change summaries. Refresh
failures still produce warnings; internal snapshot validation retains the full SHA.
Catalogue-only Git rows start unacquired and disabled; Space queues acquisition and
exposure, Apply revalidates the selected source/subscription, and Revert downloads
nothing. Npm catalogue-only rows are read-only; Info gives an explicit confirmed
native installation command. Once installed, native npm selection controls apply.

A failed catalogue refresh hides catalogue-only rows, not acquired assets. Removing
an entry or unsubscribing does not delete library content or disable exposure.
Info shows source/provenance and timestamped Git checks; there are no automatic
upstream updates. [Full catalogue behavior](catalog.md).

## How edits flow

Toggling an asset cell **queues** a pending edit; the requested asset/exposure
change does not run until you **Apply** (++ctrl+s++). This mirrors a staged-changes
model, not a promise of zero disk/network I/O elsewhere: catalogue refresh,
package-check metadata and explicitly saved presentation preferences are separate.

1. Toggle cells across rows, across scopes, and across asset types to build a pending queue.
2. ++ctrl+d++ to preview, or ++ctrl+z++ to throw the queue away.
3. ++ctrl+s++ to apply — the TUI calls shared CLI facades: npm uses the same
   settings-only enable/disable/reset backend as explicit CLI selection commands,
   not physical install/uninstall. Other kinds retain their projection facades. Failed operations retain pending edits
   for retry; completed unrelated operations remain completed. A legacy collection
   reconciles its complete sibling selection before ordinary per-skill work,
   with targeted rollback on failure. Source-backed kinds retain their
   lock/projection failure handling. Instructions sends explicit link/unlink
   requests without a lock and never prunes other links. If an I/O failure applies
   only part of an Instructions batch, the grid reloads actual state and retains
   only unsatisfied intents for retry. Canonical-source-chain removal guards run
   before any Instructions batch writes. Apply is not one atomic transaction
   across different asset types.

Same-named assets in different asset types remain separate edits in Diff,
Revert, and the quit-confirmation count. Each queued edit keeps its own scope
when applied, even if another asset type or the global scope is visible.

Quitting with unapplied edits raises a confirm-discard prompt.

## Limits and recovery

- Apply runs queued kinds in order: Instructions, Commands, Skills, Agents, MCPs, Pi Extensions. Completed work is not globally rolled back when another kind fails.
- Per-kind retry handling differs: Instructions retains only unsatisfied pointer intents; some source-backed grids retain a failed batch's queue, including already completed idempotent operations. Inspect actual state and diagnostics before retrying.
- Switching kinds/scopes preserves drafts. User **Refresh** also retains native npm and loose-local Pi drafts, including original snapshots; other active-grid drafts retain their discard policy. Revert clears all kinds/both scopes without undoing already applied work. Stale target/source/settings-pointer changes fail visibly rather than applying to a different configuration.
- Main-harness preference changes require confirmed discard of all queued edits; changing theme preserves them. Presentation preferences do not install adapters or change Standard coverage.
- Long paths retain existing single-row clipping; bold final directory is not a new truncation feature. Use Info for full source/ref/path identity.
- The grid shows supported main-harness columns; use the CLI for the long tail. Unavailable cells cannot be toggled. Collection control is bounded by actual harness/scope exposure, not a universal loader guarantee.

See also: [CLI reference](cli.md) · [TUI settings schema](tui-settings.md) ·
[Glossary](../glossary.md) · [Roadmap](roadmap.md)
