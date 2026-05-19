# Plan: rename `_translated_slot_filename` → `_slot_filename`

Implements the spec at
`docs/superpowers/specs/2026-05-19-rename-slot-filename-design.md`.

## Single task

Apply a global rename across the three files that reference the helper, then
update the docstring.

1. `src/agent_toolkit_cli/commands/_link_lib.py`
   - Rename the function definition.
   - Rewrite the docstring (drop the "translated"/"non-translated" framing).
   - Update all 4 internal call sites.

2. `src/agent_toolkit_cli/doctor/symlinks.py`
   - Update the `from ... import` line.
   - Update both call sites.

3. `src/agent_toolkit_cli/commands/_list_json.py`
   - Update the `from ... import` line.
   - Update the single call site.

## Acceptance

- `grep -rn _translated_slot_filename src/` returns nothing.
- `grep -rn '_slot_filename\b' src/` shows the new identifier at all 8 sites
  (1 def + 7 call sites).
- `pytest` passes unchanged.
- `ruff` / `mypy` (whatever the project runs) clean.

## Risk

None — no behaviour change, identifier-only.
