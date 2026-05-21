# Spec: TUI SkillGrid — description + upstream-source columns

**Issue:** #182
**Date:** 2026-05-22
**Mode:** `--ship-it`

## Goal

Surface two more pieces of per-skill metadata in the TUI `SkillGrid`:

- A short **description** (from the skill's `SKILL.md` frontmatter) as the **second column** (immediately after `slug`).
- An **upstream source** column (the skill's installed-from URL / path, as recorded in the lock entry) as the **far-right column** (after `state`).

## Why

Today the grid is `slug | <agents…> | state`. To answer the two most common per-row questions — *"what does this skill do?"* and *"where did it come from?"* — the user has to leave the TUI and either open `SKILL.md` or read the lockfile. Inlining the data into the grid removes that round-trip without changing any interactive behaviour.

## Final column layout

```
| slug | description | <interactive agents…> | state | source |
  0      1             2..N+1                   N+2     N+3
```

- `slug` — unchanged.
- `description` — **new.** Short, single-line; from `SKILL.md` frontmatter `description:`. Empty string if unavailable (e.g. `state == "library"`).
- agent columns (`universal`, `claude-code`, `pi` from `INTERACTIVE_AGENTS`) — unchanged ordering, widths, and toggling.
- `state` — unchanged.
- `source` — **new.** The `LockEntry.source` string already on `SkillRow`. No truncation; column width chosen to fit common shapes (`owner/repo`, full URLs).

## Data model

- `SkillRow` already carries `source: str`. **Reused as-is** for the new column. No model change for source.
- `SkillRow` gains a new field: `description: str = ""`.
  - Populated in `build_skill_rows()` by parsing `<canonical>/SKILL.md` frontmatter. If the file is missing (e.g. `state == "library"` — skill is in lockfile but not yet installed at this scope), unreadable, or has no `description:` key, the field is `""`.
  - Frontmatter parsing mirrors the existing helper in `commands/skill/__init__.py` (`yaml.safe_load` on the `---`-delimited block). A small shared helper `_read_skill_description(canonical: Path) -> str` is introduced in `skill_state.py` to keep the read local to the model that needs it.

## SkillGrid changes

In `widgets/skill_grid.py`:

- `_rebuild()` adds two `table.add_column(...)` calls — `description` at position 1 (after `slug`), `source` at the end (after `state`).
- `_rebuild()` populates both new cells per row.
- `_column_index(agent_name)` adjusts: agent columns now start at index **2** (after `slug` and `description`).
- `_agent_for_column(col)`: agent columns map to indices `2..2+len(INTERACTIVE_AGENTS)-1`. Anything outside that range (slug, description, state, source) → `None` — the existing "non-agent → ignore toggle/info" branch then handles it unchanged.
- The cursor-restore math in `_rebuild()` uses the new max column index (`1 + 1 + len(INTERACTIVE_AGENTS) + 1` = state, plus the new source = `+1` more).

Widths (initial, easy to tune later):

- `description` — `width=40`.
- `source` — `width=30`.

## What deliberately doesn't change

- Bindings (`space`, `a`, `i`). Toggle and info still only act on agent columns; the helper functions short-circuit when the cursor is on a non-agent column, which is already the case today for `slug` and `state`.
- The `_pending` map, scope handling, drift detection, glyphs.
- The CLI surface. This is a TUI-only change.
- The lock schema. `source` already exists on `LockEntry`; `description` is read from disk, never written.
- The column-info modal registry (`COLUMN_INFO`). The two new columns are passive — no `ⓘ` info popup, no toggle target.

## Risks

1. **Per-row disk I/O.** Reading `SKILL.md` for each row on every rebuild is the only material cost. Today rebuild already calls `skill_git.status()` per row (a subprocess), so one extra small file read is well below that bar.
2. **Cursor / coordinate math.** Multiple tests (e.g. `test_skill_grid_apply.py`) construct or assert against `Coordinate(row, column)` values. Adding a column before the agent columns shifts every agent cell right by one. All affected tests need updating.
3. **Frontmatter parsing edge cases.** SKILL.md without frontmatter, or with non-dict frontmatter, or with no `description:` key → empty string, never raise.

## Definition of done

- `description` column appears as the second column (immediately after `slug`) in the SkillGrid.
- `source` column appears as the far-right column (after `state`) and shows the skill's installed-from URL / path.
- Existing columns (`slug`, agent columns, `state`) keep their current order, widths, and toggling behaviour.
- Column-info / cursor / toggle bindings keep working with the new column count.
- `uv run pytest -q` is green.
