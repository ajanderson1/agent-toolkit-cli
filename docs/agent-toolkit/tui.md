# TUI reference

`agent-toolkit-tui` is the interactive [Textual](https://textual.textualize.io/)
cockpit over the same surface the [CLI](cli.md) drives. It reads the lock files
and filesystem directly (Instructions uses filesystem pointers only) and applies your edits by calling the shipped CLI
facades in-process. Inventories are snapshots, not a guarantee against later
filesystem changes or partially failed operations; reload actual state after errors.

It ships alongside the CLI from the same `uv tool install`, as a separate
binary:

```bash
agent-toolkit-tui
```

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
  per-harness cells). Press ++i++ for the selected asset; click a glyphed column
  header for column-level information.
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

### Library, local and npm origins

Skills and Agents prefix the existing Source column with `library` or `local`;
Pi Extensions uses its existing Origin column. Git-change and health badges
(such as dirty, missing or drift) remain separate from origin.

| Origin | Meaning and controls |
|---|---|
| `library` | Toolkit-managed central source connected through the existing installation mechanism. Disable removes the connection, not the source. |
| `local` | Existing files used where they are, outside Toolkit library management—even if discovered under a library directory. Visible and usable, but excluded from individual, collection and All/None toggle queues. No TUI enable/disable, deletion, moving or registration. |
| `npm` | Pi obtains the published package. Toolkit-registered references retain their toggle controls; references Toolkit did not register remain read-only with manual guidance in Info. |

Press ++i++ for the actual source path and linking/update behavior. For local
files, Info gives the exact manual removal command and warns when it
**permanently deletes files**. Removing a symlink keeps its target; remove only
the selected child, never a shared parent checkout. For a local package in Pi
settings, remove its string or structured `packages[]` reference in the shown
settings file; this does not delete package contents.

npm enable/disable adds/removes a reference in Pi settings—not an extension
symlink or package-file deletion. Updates use Pi package handling, not Toolkit
Git update. Removing a reference does not unload an already-running Pi session.

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
| ++ctrl+r++ | **Refresh** | Clear the active grid's pending edits (both scopes), then re-read its inventory; other kinds' queues survive. |
| ++ctrl+z++ | **Revert** | Clear the pending queue across all asset types — both scopes. |
| ++slash++ | **Filter** | Focus the fuzzy filter box over the grid. |
| ++ctrl+g++ | **Scope toggle** | Switch project ⇄ global. |
| ++ctrl+p++ | **Command palette** | Choose **Theme** or **Main harnesses** to customize themes or standalone columns. |
| ++i++ | **Info** | Open information for the selected asset, regardless of column. |
| ++q++ | **Quit** | Prompts to confirm if you have unapplied pending edits. |

Press ++space++ to toggle a cell, ++a++ for a column, and ++ctrl+w++ to focus the sidebar. Number shortcuts apply only when the sidebar has focus. Filters match asset identity; they do not narrow a collection parent's membership.

## Theme and Main Harness Preferences

Open ++ctrl+p++ and choose **Theme** or **Main harnesses**.

- **Theme** opens Textual's theme chooser; selecting a theme persists it to
  `tui-settings.json` and updates the app live.
- **Main harnesses** lists all catalogued harnesses; selecting one toggles its
  presence as a standalone column across all supported asset grids. If unapplied
  pending edits are queued, a confirmation prompt asks before discarding them.

A harness preference hides or shows only standalone columns. It never changes
Standard coverage, and it cannot render a harness an asset type does not support.

See [TUI settings schema](tui-settings.md) for the JSON fields, environment
override, failure handling, and the explicit CLI boundary.

## Skill collections

Multi-skill repositories appear as an expandable **collection** with short child names. The header counts real skills and collections, not extra parent rows. Click the parent name (or press Space/Enter there) to expand/collapse; Info retains full source/ref/path identity.

Each available parent cell summarizes effective selection: unchecked = none, checked = all, **cyan `−` = mixed**. A mixed parent selects all when toggled. Child cells remain independent. The **yellow `-` on a child means pending removal**, not mixed selection. Parent actions include every member, even collapsed or filter-hidden children, and stay within that source/ref, harness and scope. A child filter keeps the parent visible for context. Column-wide toggles visit children once.

Linked/broken counts reflect actual real-child payload health, not just link presence; pending controls represent desired selection. A missing referenced `SKILL.md` is unhealthy, and Apply refuses it instead of creating a false clean state.

Legacy whole-repo exposure is recognized without writing. The first selection-changing Apply targeting it replaces the owned wrapper with the complete desired set of child links, preserving active checkout contents and history. This happens inside normal Apply: there is no conversion button, setup step or extra confirmation. Read/refresh, filters, expansion, toggles, Revert, no-op Apply and unrelated Apply do not reconcile assets. Other harnesses/scopes remain unchanged. A real root skill can make independent nested isolation uncertain; unsupported root-on/nested-off selections fail before writes rather than pretending a nested skill is disabled.

Conflicts leave failed edits queued. A collection failure restores only its affected links/records against fresh locks, preserving unrelated work; failed recovery stays prominent with the remaining ownership conflict. Correct the conflict and retry, or Revert the queued request. Referenced backing checkouts remain preserved even after the final fake wrapper record is retired. A matching library-only rootless container does not reappear as a broken project skill after Apply, Refresh or restart. This presentation identity is separate from authority to mutate the active scope. Real missing child documents, foreign projections and distinct-copy ambiguity remain visible. If an unregistered wrapper projection still exists—even pointing to the retained backing—it remains a visible exposure warning and blocks unsafe collection changes; no library record authorizes silently retiring it.

## How edits flow

Toggling a cell **queues** a pending edit; nothing touches disk until you
**Apply** (++ctrl+s++). This mirrors a staged-changes model:

1. Toggle cells across rows, across scopes, and across asset types to build a pending queue.
2. ++ctrl+d++ to preview, or ++ctrl+z++ to throw the queue away.
3. ++ctrl+s++ to apply — the TUI calls the same install/uninstall facades the
   CLI uses across all queued asset types. Failed operations retain pending edits
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
- Switching kinds/scopes uses internal queue-preserving refreshes. User **Refresh** explicitly discards the active grid's queue; it is not equivalent to switching tabs. Revert clears all kinds/both scopes without undoing already applied filesystem work.
- Main-harness preference changes require confirmed discard of all queued edits; changing theme preserves them. Presentation preferences do not install adapters or change Standard coverage.
- Long paths retain existing single-row clipping; bold final directory is not a new truncation feature. Use Info for full source/ref/path identity.
- The grid shows supported main-harness columns; use the CLI for the long tail. Unavailable cells cannot be toggled. Collection control is bounded by actual harness/scope exposure, not a universal loader guarantee.

See also: [CLI reference](cli.md) · [TUI settings schema](tui-settings.md) ·
[Glossary](../glossary.md) · [Roadmap](roadmap.md)
