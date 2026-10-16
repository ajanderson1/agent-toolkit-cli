# TUI reference

`agent-toolkit-tui` is the interactive [Textual](https://textual.textualize.io/)
cockpit over the same surface the [CLI](cli.md) drives. It reads the lock files
and filesystem directly and applies your edits by calling the shipped CLI
facades in-process — so the TUI and CLI can never disagree about what is
installed.

It ships alongside the CLI from the same `uv tool install`, as a separate
binary:

```bash
agent-toolkit-tui
```

!!! note "📸 Screenshot — `tui-overview.png`"

    The full cockpit on launch: the **asset-type sidebar** on the left, the
    active grid filling the content pane, the scope toggle top-right, and the
    status / pending / footer rows along the bottom.

## Layout

```text
Header
├─ Asset-type sidebar        instruction · skill · command · pi-extension · agent · mcp
└─ Content
   ├─ Content header + Scope toggle   (project ⇄ global)
   └─ One grid per asset type         (swapped as you change asset type)
Status bar
Pending line
Footer (key hints)
```

- **Asset-type sidebar** — pick which [asset type](../glossary.md#asset-type)
  you're managing. `instruction` sits above a separator (it is whole-scope, not
  per-slug); `skill`, `command`, `pi-extension`, `agent`, and `mcp` follow.
- **Grid** — one row per asset, columns vary by type (slug, source, ref, state,
  per-harness cells). Press ++i++ for the selected asset; click a glyphed column
  header for column-level information.
- **Scope toggle** — flips the whole view between **project** and **global**
  [scope](../glossary.md#scope). The grid re-reads at the new scope; pending
  edits queued in the other scope are kept, not discarded.

!!! note "📸 Screenshot — `tui-skill-grid.png`"

    The skill grid with several rows, a per-harness cell column, and a row
    selected — showing what a populated grid looks like in practice.

| `unlisted` | Discovered on disk but absent from the active lock; visible for audit, not yet managed. |
| `local package · untracked` | Pi package declared by local filesystem path; read-only until explicitly imported by confirmed doctor repair. |

Skill, agent, and command grids union lock entries with bounded on-disk discovery. Skill bundles have separate stable `bundle:skill` rows. Filesystem discovery itself is observational; row cells retain existing per-harness behavior. For Pi, local-package rows carry `local package · untracked` and are non-interactive until managed.

## Key bindings

| Key | Action | Notes |
|---|---|---|
| ++ctrl+s++ | **Apply** | Run pending edits across all asset types through the CLI facade. |
| ++ctrl+d++ | **Diff** | Preview the pending queue (`N would-link, M would-unlink`) across all asset types without applying. |
| ++ctrl+r++ | **Refresh** | Re-read locks + filesystem for the active view. |
| ++ctrl+z++ | **Revert** | Clear the pending queue across all asset types — both scopes. |
| ++slash++ | **Filter** | Focus the fuzzy filter box over the grid. |
| ++ctrl+g++ | **Scope toggle** | Switch project ⇄ global. |
| ++ctrl+p++ | **Command palette** | Choose **Theme** or **Main harnesses** to customize themes or standalone columns. |
| ++i++ | **Info** | Open information for the selected asset, regardless of column. |
| ++q++ | **Quit** | Prompts to confirm if you have unapplied pending edits. |

!!! note "📸 Screenshot — `tui-pending-apply.png`"

    A grid with queued edits and the pending line populated, just before
    ++ctrl+s++ — the moment the TUI's edit-then-apply model is clearest.

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

Legacy whole-repo exposure is recognized without writing. The first selection-changing Apply targeting it replaces the owned wrapper with the complete desired set of child links, preserving active checkout contents and history. This happens inside normal Apply: there is no conversion button, setup step or extra confirmation. Read/refresh, filters, expansion, toggles, Revert, no-op Apply and unrelated Apply do not reconcile assets. Other harnesses/scopes remain unchanged. A real root skill can make independent nested isolation uncertain; unsupported root-on/nested-off selections fail before writes rather than pretending a nested skill is disabled.

Conflicts leave failed edits queued. A collection failure restores only its affected links/records against fresh locks, preserving unrelated work; failed recovery stays prominent with the remaining ownership conflict. Correct the conflict and retry, or Revert the queued request. Referenced backing checkouts remain preserved even after the final fake wrapper record is retired.

## How edits flow

Toggling a cell **queues** a pending edit; nothing touches disk until you
**Apply** (++ctrl+s++). This mirrors a staged-changes model:

1. Toggle cells across rows, across scopes, and across asset types to build a pending queue.
2. ++ctrl+d++ to preview, or ++ctrl+z++ to throw the queue away.
3. ++ctrl+s++ to apply — the TUI calls the same install/uninstall facades the
   CLI uses across all queued asset types. Failed operations retain pending edits
   for retry; completed unrelated operations remain completed. A legacy collection
   reconciles its complete sibling selection before ordinary per-skill work,
   with targeted rollback on failure. Apply is not one atomic transaction across
   different asset types.

Same-named assets in different asset types remain separate edits in Diff,
Revert, and the quit-confirmation count. Each queued edit keeps its own scope
when applied, even if another asset type or the global scope is visible.

Quitting with unapplied edits raises a confirm-discard prompt.

!!! note "📸 Screenshot — `tui-scope-toggle.png`"

    The scope toggle mid-switch (or the `(N global, M project)` tag in the
    pending line) demonstrating that a single queue can span both scopes.

See also: [CLI reference](cli.md) · [TUI settings schema](tui-settings.md) ·
[Glossary](../glossary.md) · [Roadmap](roadmap.md)
