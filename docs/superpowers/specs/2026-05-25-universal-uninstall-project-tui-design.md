# Spec — Universal skills uninstallable from project-scope TUI grid (#232)

## Goal
Toggling a checked **Universal** cell at **project** scope in the TUI must queue an
uninstall (like any other cell), instead of silently no-opping.

## Background — what changed since the issue was filed
The issue (filed 2026-05-24) named two layers:
1. **TUI silent guard** — `skill_grid.py` early-returns on
   `agent == "universal" and scope == "project" and cell.linked`.
2. **Engine has no project-scope universal removal path.**

Layer 2 was **already fixed by PR #237** ("universal bundle toggle works at project
scope", commit `cffb49a`): `skill_install.apply()` now handles `universal` in
`remove_agents` at both `global` and `project` scope via `_project_universal_link`.

So the **only remaining gap is the TUI guard**.

## Physical layout (post-#235)
At project scope, `<project>/.agents/skills/<slug>` is a **symlink** into the external
store (`~/.agent-toolkit/projects/<id>/skills/<slug>/`), not a real directory. The
guard's comment ("removing the project canonical is destructive") describes the
**pre-#235** layout and is now factually stale. Removing the symlink is non-destructive;
the canonical in the external store is untouched.

## Change
Delete the guard block (the comment + the `if agent == "universal" and
self._scope == "project" and cell.linked: return`). A `space` press then queues
`("project", "universal", slug) -> "unlink"` in `_pending`, which the existing apply
path in `app.py` dispatches to `engine_apply(InstallPlan(remove_agents=("universal",)))`,
which calls `link.unlink()` on the symlink.

## Decisions
- **No `notify()`.** There is no established notify pattern in the TUI package; the TODO
  asked for one "once a notify pattern is established." The existing `#footer-pending`
  Static widget already reports apply results ("applied: N ok, M failed"), which satisfies
  the DoD's "no silent no-op" — the toggle now shows a pending op, and apply shows the
  outcome. Adding a bespoke notify for one cell type would introduce a new pattern for no
  benefit (rejected per "prefer simple defaults").
- **No canonical deletion.** DoD wording "removes the project canonical" reflects the old
  in-tree layout; post-#235 only the projection symlink is removed. This is correct and
  consistent with how every other project-scope cell behaves.

## Out of scope
- Global-scope universal (already works).
- Universal-vs-additional-agents semantics redesign.
- Adding a general TUI notify framework.

## Definition of done
- Toggling a checked Universal cell at project scope queues `unlink` (visible as
  "Pending: unlink" in the cell panel + footer count).
- Applying it removes the project projection symlink via the engine; no `InstallError`.
- Tests cover the grid toggle (link/unlink) at project scope and the engine unlink.
