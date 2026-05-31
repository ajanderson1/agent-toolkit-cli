# Design: `agent uninstall` must be non-destructive (Issue #303)

**Issue:** [#303](https://github.com/ajanderson1/agent-toolkit-cli/issues/303) — `agent uninstall` is destructive: deletes library canonical + lock entry (inverts its own contract).
**Type:** `fix` · **Severity:** high (data loss + inverted contract).
**Mode:** `--auto`

## Problem

`agent uninstall <slug> -g` is supposed to detach an agent's harness projections while leaving
the library copy intact — exactly like `skill uninstall`. Instead it performs a **full removal**:
it `shutil.rmtree`s the library canonical (`~/.agent-toolkit/agents/<slug>/`) and drops the lock
entry, so `agent list -g` then reports "no agents found". The user who detaches from one harness
loses the whole library copy. This is `agent remove` behaviour wearing the `uninstall` name.

### Root cause (confirmed from source, not a path-resolution accident)

`src/agent_toolkit_cli/agent_install.py::uninstall()` is **deliberately** documented and coded as a
full remove:

```python
# agent_install.py:283  docstring
"""Full removal — every projected file + lock entry (+ canonical at global)."""
...
# agent_install.py:324-328   drops the lock entry at BOTH scopes
if slug in lock.skills:
    write_lock(lock_path, remove_entry(lock, slug))
...
# agent_install.py:334-339   global scope rmtree's the canonical
if canonical.exists():
    shutil.rmtree(canonical)
```

This **contradicts the CLI command's own docstring** (`commands/agent/uninstall_cmd.py:3-4`):

> *"Keeps the canonical library entry (global store copy, lock entry). Use `agent remove` to fully
> drop from the library."*

…and **diverges from the reference contract** set by `skill uninstall`
(`commands/skill/__init__.py:616`):

> *"Remove agent-visibility symlinks. Library/project canonical untouched."*

`skill uninstall` at global scope removes **only the requested agents' projections** via
`engine_apply` with `remove_agents=target_agents`; it does **not** touch the canonical and does
**not** drop the lock entry. Project scope removes projections and drops only the *project* lock
entry, preserving the external canonical. The agent kind must mirror this.

### Why CI was green (the test asserted the bug)

The destructive behaviour is **load-bearing for `agent remove`**:
`commands/agent/remove_cmd.py:63-69` calls `agent_install.uninstall(...)` and relies on its comment
*"already removes the lock entry and canonical at global scope — nothing more to do."* So `uninstall`
is doing double duty for two contracts (detach vs delete), and the existing round-trip tests were
written to assert the **destructive** direction:

- `tests/test_cli/test_agent_install_roundtrip.py:92-93` — `assert not canonical.exists()` +
  `assert "rt-agent" not in lock` after a global **uninstall**.
- `tests/test_cli/test_cli_agent_group.py:163` — `assert "demo-agent" not in lock` after a global
  **uninstall**.

Both bake the inverted contract in as "correct", which is exactly why green CI shipped a data-loss
bug ([[project_v3_install_machinery_roundtrip_gap]] class). `agent remove`'s own destructive test
(`test_cli_agent_group.py:346 test_remove_drops_projections_and_canonical`) is correct and must keep
passing.

## Goal

`agent uninstall` (both scopes) becomes **non-destructive**: it removes only harness projections and
adjusts only the harness set, **preserving the library canonical and the lock entry**. The canonical
+ lock deletion moves into a distinct path owned by `agent remove`. `uninstall` and `remove` end up
with **provably distinct effects**.

## Non-goals

- No change to `skill` / `instructions` / `pi-extension` kinds.
- No change to adapter `uninstall()` semantics (they already idempotently remove real files).
- No change to the `--harnesses` parsing or the CLI flags/UX surface (output lines may gain an
  `unlinked` line for parity, but the command signature is unchanged).
- Not addressing the companion minors in #304 (status scope-default, `agent add` slug-file
  validation, TUI `universal`→`general` label) — those are tracked separately.

## Design

### Contract split (the core change)

Split the conflated `agent_install.uninstall()` into two functions with single, honest contracts —
mirroring the `skill uninstall` / `skill remove` split:

1. **`agent_install.uninstall(...)` → non-destructive.**
   - Remove the requested harnesses' real projection files via each adapter's idempotent
     `uninstall()` (the existing loop — this part is already correct and fixes the original PR #268
     orphan bug; keep it).
   - **Keep the canonical** at both scopes.
   - **Keep the lock entry.** Do not call `remove_entry`. (Rationale below — the lock entry records
     library presence + provenance, which survives a detach. This matches `skill uninstall`, whose
     global path never drops the lock and whose project path drops only the *project* lock entry
     because the project lock *is* the projection record.)
   - Net effect: `agent list -g` still shows the agent; re-`install` re-projects from the intact
     canonical with no re-clone.

2. **`agent_install.remove(...)` → destructive (new function).**
   - Call `uninstall(...)` first to clear all projections (idempotent).
   - Drop the lock entry (both scopes per existing `remove` semantics — global library lock).
   - `shutil.rmtree` the canonical at global scope; preserve the external canonical at project scope
     (matching today's project posture and `skill remove`'s dirty-survival rule, with `doctor`
     reclaiming orphans).
   - `commands/agent/remove_cmd.py` calls this new `remove()` instead of `uninstall()`. The dirty
     git-guard stays in `remove_cmd` (unchanged).

This keeps `agent remove` fully working while making `agent uninstall` honest.

### Lock-entry decision (the one real subtlety)

**Question:** should `agent uninstall -g` drop the lock entry, or keep it?

**Decision: keep it.** Rationale, grounded in the reference contract:
- `skill uninstall` global path **never** drops the lock entry — it only removes symlinks via
  `engine_apply`. The lock entry is the record that the slug lives in the library; that's still true
  after a detach. Keeping it makes `list`/`status`/`doctor` show the agent as present-but-unlinked,
  which is the truthful state and lets a later `install` recompute a correct delta.
- The CLI docstring we're restoring explicitly promises *"Keeps the canonical library entry (global
  store copy, **lock entry**)."* — so keeping the lock entry is the documented contract.
- `skill uninstall`'s *project* path drops the *project* lock entry only because for the project
  scope the lock entry **is** the projection record (there's no separate "library presence"). The
  agent project scope is analogous; however, to keep `uninstall` strictly non-destructive and
  symmetric across scopes for this fix, the agent project `uninstall` will **also keep** its lock
  entry (the external canonical is already preserved, and `doctor` reclaims orphans). This is a
  deliberate, documented divergence from skill-project for honesty; it is captured in the
  acceptance criteria so a reviewer can challenge it.

> If a reviewer prefers project-scope `uninstall` to drop the project lock entry (tighter skill
> parity), that is a one-line change in `remove`/`uninstall` and is called out explicitly in the
> plan as an open decision. Default chosen: **keep**, for non-destructive symmetry.

### Files touched

| File | Change |
|---|---|
| `src/agent_toolkit_cli/agent_install.py` | Rewrite `uninstall()` non-destructive; add `remove()` with the canonical/lock-deletion logic moved out of `uninstall()`. |
| `src/agent_toolkit_cli/commands/agent/remove_cmd.py` | Call `agent_install.remove(...)` instead of `uninstall(...)`. Comment updated. |
| `src/agent_toolkit_cli/commands/agent/uninstall_cmd.py` | Docstring already correct; no behaviour change (optionally print `unlinked` lines for parity). |
| `tests/test_cli/test_agent_install_roundtrip.py` | Flip the destructive assertions (l.92-93) to assert **canonical present + lock present** after uninstall. Keep the projection-gone assertions. |
| `tests/test_cli/test_cli_agent_group.py` | Flip l.163 (lock present after uninstall). Add a new test asserting `uninstall` vs `remove` have **distinct** effects. |

## Acceptance criteria

1. **`agent uninstall -g` is non-destructive:** after install→uninstall at global scope, the harness
   projections are GONE, **the canonical IS present**, and **the lock entry IS present**
   (`agent list -g` shows the agent).
2. **`agent uninstall -p` is non-destructive:** after install→uninstall at project scope, projections
   GONE, project canonical present, lock entry present.
3. **`agent remove` is still destructive:** after install→remove at global scope, projections GONE,
   canonical GONE, lock entry GONE (existing `test_remove_drops_projections_and_canonical` passes
   unchanged).
4. **`uninstall` and `remove` have distinct effects:** a single test installs the agent twice into
   two isolated HOMEs (or sequential install/reinstall), runs `uninstall` on one and `remove` on the
   other, and asserts the canonical survives the former but not the latter.
5. **Idempotency preserved:** double-`uninstall` and double-`install` remain safe (existing tests
   pass).
6. **Re-install after uninstall works with no re-clone:** install → uninstall → install re-projects
   from the intact canonical (lock entry still present ⇒ tool-owned refresh path).
7. Full suite + lint green; the two flipped assertions are the regression guard for #303.

## Risks

- **Breaking `agent remove`** if the canonical-deletion logic isn't faithfully moved. Mitigated by
  acceptance #3 (existing remove test must stay green) and #4 (distinct-effects test).
- **Project-scope lock decision** (keep vs drop) is a judgement call; flagged for reviewer challenge
  in the plan. Default is non-destructive (keep).
