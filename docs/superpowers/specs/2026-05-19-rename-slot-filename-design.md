# Spec: rename `_translated_slot_filename` → `_slot_filename`

Closes #93.

## Why

After #92, the helper covers both translated (opencode|claude × agent|command) and
non-translated slot filenames. The `_translated_` prefix is now misleading — the
function is a generic slot-filename resolver, not specific to translation.

## Change

Mechanical rename across the three files that touch this helper:

- `src/agent_toolkit_cli/commands/_link_lib.py` — function definition (line 96)
  plus 4 internal call sites (lines 126, 349, 593, 620).
- `src/agent_toolkit_cli/doctor/symlinks.py` — import (line 9) plus 2 call sites
  (lines 45, 70).
- `src/agent_toolkit_cli/commands/_list_json.py` — import (line 30) plus 1 call
  site (line 93).

Update the docstring at `_link_lib.py:97` to drop the "translated"/"non-translated"
framing — the docstring should describe what the function does (resolve the slot
filename for a given harness+kind, appending `.md` only for file-slot
agent/command pairs), not allude to a translation pipeline that no longer maps
cleanly onto the call sites.

## Non-goals

- No behaviour change. The function body is unchanged.
- No reorganisation, no callable signature changes.
- No new tests — full existing `pytest` suite must pass unchanged.

## Verification

- `pytest` clean.
- `grep -rn _translated_slot_filename src/` returns nothing.
- `grep -rn _slot_filename src/` shows the new identifier at all 8 sites.
