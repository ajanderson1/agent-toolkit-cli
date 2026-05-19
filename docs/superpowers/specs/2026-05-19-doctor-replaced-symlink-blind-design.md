# Spec — doctor symlink-integrity blind to replaced symlinks (claude)

Closes #121.

## Problem

`doctor --group symlink-integrity` silently drops a slot when its symlink is replaced by a regular file or directory. Branch 1 (missing) is skipped because `exists()` returns True; branch 2 (is_symlink) is skipped because it is not a symlink. Neither branch fires, so doctor reports neither a WARN nor a "linked" finding for that slot — silent gap.

Scope: confirmed claude-specific for `skill`, `agent`, `command`, `plugin` × `claude`. Other harnesses already catch this via different code paths (codex cache, opencode file-symlinks-in-real-dirs, pi).

## Goal

doctor must detect a slot that "exists but is not a symlink" and report it as a FAIL with a clear message. Detection holds for skill, agent, command, plugin under claude.

## Non-goals

- No change to codex/opencode/pi detection paths.
- No auto-fix here; existing `agent-toolkit link user <harness>` reconciliation guidance is preserved via `fix_hint`.
- No new CLI flags.

## Design

In `src/agent_toolkit_cli/doctor/symlinks.py`, after the existing two branches at lines 73-83, add:

```python
elif check_path.exists():
    fails.append(
        f"{kind}/{slug}: slot exists but is not a symlink: {check_path}"
    )
    continue
```

- Introduce a `fails: list[str]` collector alongside `findings` and `warns`.
- After the main loop, if `fails` is non-empty, return `GroupResult` with `status=Status.FAIL` and a summary that counts failures. WARN status is retained for the WARN-only case. OK only when both `fails` and `warns` are empty.
- `findings` returned to the caller includes `findings + warns + fails` so the user sees all of it.

## Tests

Add four tests in `tests/test_doctor_groups.py`, one per kind × claude:

1. `test_symlinks_group_fails_when_skill_slot_replaced_by_dir`
2. `test_symlinks_group_fails_when_agent_slot_replaced_by_file`
3. `test_symlinks_group_fails_when_command_slot_replaced_by_dir`
4. `test_symlinks_group_fails_when_plugin_slot_replaced_by_dir`

Each: build a fake repo with the right kind of asset (harness=claude), create the projected slot under fake `$HOME` as a real file/dir instead of a symlink, run `symlinks.run(tmp_path, harness="claude")`, assert `Status.FAIL` and that the finding mentions "not a symlink".

A helper `_make_asset_with_harnesses(tmp_path, kind, slug, harnesses)` extends the existing `_make_skill_with_harnesses` to cover agent / command / plugin.

## Risk

Low. Pure additive branch; existing OK/WARN paths unchanged. Upgrading some currently-silent slots from "not reported" to FAIL is the intended behaviour change.
