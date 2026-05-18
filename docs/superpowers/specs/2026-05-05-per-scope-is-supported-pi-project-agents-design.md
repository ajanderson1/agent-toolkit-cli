# Spec — per-scope `is_supported` for pi project agents (#49)

Closes #49. Follow-up to #41.

## Problem

The `(harness, kind)` support matrix in `src/agent_toolkit_cli/_support.py` has one
key set, derived from `_USER_TARGETS`. To preserve the
`_USER_TARGETS.keys() == _PROJECT_TARGETS.keys()` parity invariant,
`_PROJECT_TARGETS[("pi", "agent")]` is set to `.pi/agent/agents` — a path **pi
never reads**. Pi only auto-discovers `extensions`, `skills`, `prompts`,
`themes` at project scope (per `pi-coding-agent dist/core/package-manager.js:1788-1794`),
not `agents`.

So we have a "dead drop" entry: legal under the current invariant, but
semantically wrong. The fix is to relax the invariant — `_USER_TARGETS` is the
union, `_PROJECT_TARGETS` is a subset — and teach the support API to answer
"supported at this scope?" rather than only "supported at all?".

## Goals

1. `is_supported` answers per-scope when asked, and back-compat (no scope arg)
   keeps current behaviour.
2. `_PROJECT_TARGETS[("pi", "agent")]` is removed.
3. Linker code paths that iterate kinds-per-scope check per-scope support
   *before* asking for a target dir, so a `(harness, kind, scope)` triple
   without a slot is a clean skip rather than a `RuntimeError`.
4. The list/TUI cell for `(pi, agent)` at project scope reports `unsupported`
   (no behaviour change here — the existing `slot is None → "unsupported"`
   branch in `_list_json._cell_status:50-52` already does this once
   `_PROJECT_TARGETS` loses the row).
5. Test invariant updated: `_PROJECT_TARGETS.keys() ⊆ _USER_TARGETS.keys()`.

## Acceptance criteria

From #49, verbatim:

1. `is_supported("pi", "agent")` returns `True` (back-compat).
2. `is_supported("pi", "agent", scope="user")` returns `True`.
3. `is_supported("pi", "agent", scope="project")` returns `False`.
4. `slot_dir("pi", "agent", "project", _)` returns `None` (and the
   `_PROJECT_TARGETS` entry is removed).
5. The linker pre-checks per-scope support and surfaces "unsupported
   (harness, kind, scope)" cleanly instead of raising `RuntimeError` or
   silently writing to a dead path.
6. `tests/test_support.py` parity test reflects subset, not equality.
7. The list/TUI cell for `(pi, agent)` at project scope shows `unsupported`.

## Design

### Support API surface (`src/agent_toolkit_cli/_support.py`)

`is_supported` gains an optional `scope` parameter:

```python
def is_supported(harness: str, kind: str, scope: str | None = None) -> bool:
    if scope is None:
        return (harness, kind) in SUPPORTED_PAIRS  # back-compat
    if scope == "user":
        return (harness, kind) in _USER_TARGETS
    if scope == "project":
        return (harness, kind) in _PROJECT_TARGETS
    return False
```

`SUPPORTED_PAIRS` continues to be derived from `_USER_TARGETS.keys()` — that's
the union by construction once `_PROJECT_TARGETS ⊆ _USER_TARGETS`. The
docstring note about "both tables MUST share the same key set" is replaced
with "`_PROJECT_TARGETS.keys()` MUST be a subset of `_USER_TARGETS.keys()`".

`slot_dir` already returns `None` when `_PROJECT_TARGETS.get((h, k))` misses —
no change needed. Removing the `("pi", "agent")` row makes acceptance #4 fall
out for free.

### Caller updates

Two iteration sites currently use the no-scope form of `is_supported` to
filter before calling `harness_target_dir`. Both iterate over kinds for a
fixed (harness, scope) pair, so both must pass `scope=scope`:

| Site | Current | After |
|---|---|---|
| `src/agent_toolkit_cli/commands/_link_lib.py:488` | `if not is_supported(harness, kind):` | `if not is_supported(harness, kind, scope=scope):` |
| `src/agent_toolkit_cli/commands/unlink.py:160` | `if not is_supported(harness, kind):` | `if not is_supported(harness, kind, scope=scope):` |

The `RuntimeError` guard at `_link_lib.py:495-499` ("`is_supported(...)` is
True but `harness_target_dir` returned None — SSOT invariant broken") was
written under the old assumption that the two key sets were equal. After this
change the invariant becomes:

> If `is_supported(harness, kind, scope=scope)` is True, `harness_target_dir(harness, kind, scope, project_root)` returns a `Path`.

The guard is rewritten to match (the new pre-check makes it unreachable on
known-good input; we keep it as a runtime invariant check).

### Direct-entrypoint call sites

`maybe_link` at `_link_lib.py:314` and `validate_pair` (used by
`commands/link.py:465` and `commands/unlink.py:282`) operate on user-supplied
`(harness, kind)` *before* a scope is in scope. They keep the no-scope
back-compat path: a pair that exists at *some* scope is still acceptable to
allow-list and to validate. The per-scope refusal happens later, at the
projection step, where it can produce a precise message.

That's a deliberate split:

- **Allow-list / validate** layer: "is this pair known at all?" → back-compat
  `is_supported(harness, kind)` with no scope.
- **Project to disk** layer: "is this pair known *at this scope*?" → new
  `is_supported(harness, kind, scope=scope)`.

### Doctor / list paths

- `src/agent_toolkit_cli/doctor/symlinks.py` and `doctor/allowlist_audit.py` both
  iterate `_USER_TARGETS` directly — unaffected.
- `src/agent_toolkit_cli/commands/_list_json.py:_cell_status` already returns
  `("unsupported", None)` when `_slot_dir` returns `None`. Removing
  `_PROJECT_TARGETS[("pi","agent")]` means the project cell for that pair
  becomes `unsupported` automatically — acceptance #7.

### Tests

`tests/test_support.py` changes:

| Existing test | Change |
|---|---|
| `test_supported_pairs_match_target_keys` | Replace equality assertion on the second line with subset: `assert frozenset(_PROJECT_TARGETS.keys()) <= frozenset(_USER_TARGETS.keys())` |
| New: `test_is_supported_back_compat_no_scope` | Pin acceptance #1: `is_supported("pi","agent")` is True. |
| New: `test_is_supported_user_scope_for_pi_agent` | Pin acceptance #2: `is_supported("pi","agent",scope="user")` is True. |
| New: `test_is_supported_project_scope_for_pi_agent_is_false` | Pin acceptance #3: `is_supported("pi","agent",scope="project")` is False. |
| New: `test_is_supported_unknown_scope_returns_false` | Defensive: any other string returns False. |
| New: `test_slot_dir_pi_agent_project_returns_none` | Pin acceptance #4. |

`tests/test_link_lib.py:test_project_from_file_skips_unsupported_kinds_silently`
still passes — codex/agent is missing from both tables, so per-scope and
no-scope checks both return False. Its docstring reference to "is_supported
filter ... → None → RuntimeError" is still accurate as the rationale, just
with the per-scope variant.

New test: `test_project_from_file_skips_pi_agent_at_project_scope_cleanly`
exercises the new path — pi/agent is allow-listed, harness=pi, scope=project,
and the loop must skip without RuntimeError or symlink creation.

## Out of scope

- Pi project-scope agent **discovery**: pi doesn't auto-discover them, so we
  don't need to either. This issue only fixes the dead `_PROJECT_TARGETS` row.
- The `_USER_TARGETS` entry for `("pi", "agent")` stays — pi *does* read user
  agents from `~/.pi/agent/agents`.
- Other matrix gaps tracked in `tests/test_support.py:test_supported_pairs_known_holes`
  (codex/agent, pi/command) are unchanged.

## Risks

- **Loud failures elsewhere.** Any caller that does
  `is_supported(h, k) → harness_target_dir(h, k, scope, …)` without scope-
  awareness can now hit `target_dir is None`. The RuntimeError guard catches
  this at `_link_lib.py:495-499`. Mitigation: the two known iteration sites
  are updated; we add a new test for pi/agent project scope that would have
  fired the old RuntimeError.
- **Silent mismatches between `_USER_TARGETS` and `_PROJECT_TARGETS`.** With
  the parity invariant relaxed, future entries could drift. Mitigation: the
  parity-subset test stays — anything in `_PROJECT_TARGETS` but not
  `_USER_TARGETS` fails the test.
