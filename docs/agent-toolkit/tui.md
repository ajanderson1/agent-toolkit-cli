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
  per-harness cells). Press ++i++ to open the column-info panel for the active
  grid.
- **Scope toggle** — flips the whole view between **project** and **global**
  [scope](../glossary.md#scope). The grid re-reads at the new scope; pending
  edits queued in the other scope are kept, not discarded.

!!! note "📸 Screenshot — `tui-skill-grid.png`"

    The skill grid with several rows, a per-harness cell column, and a row
    selected — showing what a populated grid looks like in practice.

## Key bindings

| Key | Action | Notes |
|---|---|---|
| ++ctrl+s++ | **Apply** | Run every pending edit for the active asset type through the CLI facade. |
| ++ctrl+d++ | **Diff** | Preview the pending queue (`N would-link, M would-unlink`) without applying. |
| ++ctrl+r++ | **Refresh** | Re-read locks + filesystem for the active view. |
| ++ctrl+z++ | **Revert** | Clear the active grid's *entire* pending queue — both scopes. |
| ++slash++ | **Filter** | Focus the fuzzy filter box over the grid. |
| ++ctrl+g++ | **Scope toggle** | Switch project ⇄ global. |
| ++i++ | **Info** | Open the active grid's column-info panel. |
| ++q++ | **Quit** | Prompts to confirm if you have unapplied pending edits. |

!!! note "📸 Screenshot — `tui-pending-apply.png`"

    A grid with queued edits and the pending line populated, just before
    ++ctrl+s++ — the moment the TUI's edit-then-apply model is clearest.

## How edits flow

Toggling a cell **queues** a pending edit; nothing touches disk until you
**Apply** (++ctrl+s++). This mirrors a staged-changes model:

1. Toggle cells across rows (and across scopes) to build a pending queue.
2. ++ctrl+d++ to preview, or ++ctrl+z++ to throw the queue away.
3. ++ctrl+s++ to apply — the TUI calls the same install/uninstall facades the
   CLI uses, with the same lock-write-then-project-then-roll-back-on-failure
   contract. A failed apply rolls the lock back rather than leaving it lying
   about disk.

Quitting with unapplied edits raises a confirm-discard prompt.

!!! note "📸 Screenshot — `tui-scope-toggle.png`"

    The scope toggle mid-switch (or the `(N global, M project)` tag in the
    pending line) demonstrating that a single queue can span both scopes.

See also: [CLI reference](cli.md) · [Glossary](../glossary.md) ·
[Roadmap](roadmap.md)
