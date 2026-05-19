# Design: claude commands/agents linked with `.md` suffix

Closes #82.

## Problem

`agent-toolkit link` projects `command` and `agent` assets into the `claude`
harness using the bare slug as the symlink filename (e.g. `learn-for-me`).
Claude Code's command/agent discovery only picks up `*.md` files, so linked
commands never appear in the slash-command menu and linked agents never appear
in the agent picker.

For comparison, the same `command` linked into the `opencode` harness is
correctly named `learn-for-me.md` under `.opencode/commands/`.

## Root cause

Two layers:

1. `src/agent_toolkit_cli/commands/_link_lib.py:96-107`
   `_translated_slot_filename()` only returns `<slug>.md` for
   `(opencode, agent|command)`. Anything else returns the bare slug.

2. `src/agent_toolkit_cli/commands/_link_lib.py:347`
   `slot_filename = _translated_slot_filename(slug, kind, harness) if is_translated else slug`
   The `.md` suffix logic is only consulted when the cell has a translator
   registered in `TRANSLATORS`. Claude commands/agents have **no translator**
   (they're direct symlinks to the asset, not rendered), so the bare slug is
   used regardless of what `_translated_slot_filename` says.

So even if we extend the table inside `_translated_slot_filename`, the call
site at line 347 will skip it. The fix needs to make the file-slot naming a
property of `(harness, kind)`, independent of whether translation happens.

## Scope of affected cells

Slots whose harness reads `*.md` files from a slot directory and where the
linker currently produces bare slugs:

| Harness | Kind | Slot path | Discovery rule | Currently writes |
|---|---|---|---|---|
| claude | command | `.claude/commands/` (project), `~/.claude/commands/` (user) | `*.md` | bare slug — **bug** |
| claude | agent | `.claude/agents/` (project), `~/.claude/agents/` (user) | `*.md` | bare slug — **bug** |
| opencode | command | `.opencode/commands/` | `*.md` | `<slug>.md` — correct (translated) |
| opencode | agent | `.opencode/agents/` | `*.md` | `<slug>.md` — correct (translated) |

`claude` skills already work because they're directory-shaped (the slot itself
is a symlink to a directory). Same for `codex` skills and `pi` skills/agents
— directory-shaped, no `.md` filename required.

## Design

Promote the file-slot naming rule out of `_translated_slot_filename` and apply
it at the call site regardless of `is_translated`.

Concretely:

1. Rename `_translated_slot_filename` → `_slot_filename` (or keep the name —
   the docstring already describes a property of the slot, not the
   translation). Extend the rule:

   ```python
   def _slot_filename(slug: str, kind: str, harness: str) -> str:
       if kind in {"agent", "command"} and harness in {"opencode", "claude"}:
           return f"{slug}.md"
       return slug
   ```

2. At the call sites, drop the `if is_translated` gate:

   ```python
   slot_filename = _slot_filename(slug, kind, harness)
   ```

3. Audit the orphan-sweep code (`_link_lib.py:608-615`) — it already strips a
   trailing `.md` when comparing entry names against `discovered_slugs`, so
   sweeping should keep working. Verify with a test.

4. Audit `_translate_slot_layout` (line 121-126) — its current heuristic
   (`_translated_slot_filename("x", kind, harness).endswith(".md")`) is used
   only for **translated** cells, so widening the function won't accidentally
   reclassify claude commands as `"file"` layout (they remain non-translated,
   direct symlinks). Add a test asserting that claude commands link as a plain
   symlink (not through the cache), now with the `.md` suffix.

## Non-goals

- No changes to `codex` or `pi` — their command/agent slots either don't exist
  or are directory-shaped.
- No changes to how non-`md` kinds (hook, plugin, mcp, pi-extension) name
  their slot entries.

## Verification

- Reproduce the bug at HEAD: clone repro from issue, observe bare-slug symlink.
- After fix: same repro yields `learn-for-me.md`.
- Regression: opencode commands/agents still produce `<slug>.md`.
- Regression: claude/codex/pi skills still link as directory.
- Existing test suite (`pytest`) stays green.
- New tests covering claude command + claude agent slot filenames.
